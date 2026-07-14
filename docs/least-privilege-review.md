# Least Privilege Review

This document explains, conceptually, the permission boundary granted to every identity in the architecture. No policy JSON is reproduced here by design — the objective is to demonstrate the reasoning behind each grant, not to publish a copy/paste-able policy document. Actual policy definitions are maintained under version control in `infrastructure/iam-policies/`.

---

## GenerateUploadURL Lambda

**Purpose:** Issue short-lived, scoped presigned S3 upload policies in response to an API Gateway request.

**Permission boundary:**
- May write objects **only** into the upload bucket — it has no read, delete, or list permission on any bucket.
- May perform the specific KMS operations required to generate a presigned request for an SSE-KMS-encrypted destination (`GenerateDataKey`, `Decrypt`) — scoped to the single CMK used by the upload bucket, not any key in the account.
- May write its own execution logs to a log group scoped to its own function name — it cannot write to or read another function's log group.

**What it explicitly cannot do:** read any object, list any bucket, write to the processed bucket, access DynamoDB, access SQS, or invoke any other Lambda function. Its entire capability surface is "generate a signed policy" and "log its own execution" — nothing else.

---

## ImageProcessor Lambda

**Purpose:** Consume SQS-buffered upload events, transform images, and persist results.

**Permission boundary:**
- May read objects **only** from the upload bucket (never write, delete, or list there).
- May write objects **only** into the processed bucket (never read back from it — it has no need to).
- May consume messages **only** from the main processing queue (receive, delete, read attributes) — it has no permission on the DLQ, because messages are moved to the DLQ automatically by the queue's redrive policy, not by any action the function itself performs.
- May write **only** new items (`PutItem`) to the metadata table — it cannot query, scan, update, or delete existing items, and has no table-management permissions.
- May perform the specific KMS operations required to decrypt source objects and encrypt destination objects, scoped to the single CMK in use.
- When content moderation is enabled, may call the Rekognition moderation-detection action. This is the one permission in the entire architecture that AWS does not support scoping to a specific resource ARN — it is isolated into its own policy attachment, present only when the moderation feature flag is active, so the permission does not exist in the account at all when the feature is disabled.
- May write its own execution logs, scoped to its own function's log group.

**What it explicitly cannot do:** write to the upload bucket, read from the processed bucket, touch the DLQ directly, modify or query existing DynamoDB records, or access any resource outside its own processing path.

---

## CloudFront Origin Access Control (OAC)

**Purpose:** Serve as the sole authorized reader of the processed bucket's contents (and the secondary-region replica, when Cross-Region Replication is enabled).

**Permission boundary:**
- The bucket, not IAM, grants this access: the bucket policy authorizes the `cloudfront.amazonaws.com` service principal to perform `s3:GetObject`, conditioned on the request originating from this exact distribution's ARN.
- This means even if another CloudFront distribution existed in the same account, it could not read from this bucket unless a bucket policy statement explicitly named its ARN.
- OAC never has write, delete, or list permission on the bucket — it is read-only by design, matching its role as a content delivery mechanism, not a management interface.

---

## S3 Buckets

**Upload bucket:**
- No principal outside the `GenerateUploadURL` role (write) and `ImageProcessor` role (read) has any standing access.
- Block Public Access is enforced at all four control levels (ACLs, bucket policy, account settings inheritance), removing public exposure as a possible misconfiguration path entirely, independent of any IAM policy.
- A lifecycle rule expires objects after a bounded retention window, limiting the data footprint (and therefore blast radius) of the ingestion bucket over time.

**Processed bucket:**
- Read access is granted exclusively to CloudFront via OAC, as described above.
- Write access is granted exclusively to the `ImageProcessor` role.
- When Cross-Region Replication is active, a dedicated replication role is granted the minimum permissions required to read replication-eligible object versions from this bucket and write them to the secondary-region bucket — it has no other permission on either bucket.

---

## KMS Key

**Purpose:** Provide the sole encryption/decryption path for all data at rest.

**Permission boundary:**
- The key policy — not IAM alone — determines who may use the key. This is a deliberate double-gate: a principal must be granted the relevant `kms:*` action **both** in its IAM policy **and** in the key's policy for the operation to succeed.
- Only the root account (for administrative/break-glass recovery) and the specific Lambda execution roles requiring cryptographic operations are named in the key policy.
- The secondary-region CMK (Cross-Region Replication only) grants its operations exclusively to the replication role — no other principal, including the primary-region Lambda roles, has any grant on it, since KMS keys and their policies are strictly region-scoped.

---

## SQS

**Main queue:**
- The queue policy grants `sqs:SendMessage` exclusively to the `s3.amazonaws.com` service principal, conditioned on the request originating from the upload bucket's ARN — no other account or service can enqueue messages.
- The `ImageProcessor` role is granted only the specific consume-side actions (`ReceiveMessage`, `DeleteMessage`, `GetQueueAttributes`) required for event-source-mapping-driven consumption — it cannot send messages to the queue, and it has no permission on the queue's configuration (redrive policy, visibility timeout, etc.).

**Dead Letter Queue:**
- No IAM principal in the architecture is explicitly granted send or receive permissions on the DLQ. Messages arrive there exclusively via the main queue's redrive policy, which is an SQS-native mechanism, not an IAM-mediated action. Operator access for triage is expected to occur through a separately governed operational role, not through any application identity.

---

## DynamoDB

**Purpose:** Store structured metadata for each processed image.

**Permission boundary:**
- The `ImageProcessor` role is granted `dynamodb:PutItem` only — no `Query`, `Scan`, `UpdateItem`, `DeleteItem`, `GetItem`, or table-administration actions.
- This reflects the function's actual data-access pattern: it writes a new metadata record once per successfully processed image and never needs to read back or modify existing records as part of its own execution.
- No principal in the architecture holds standing read access to the table via application-layer IAM; any reporting or analytics access is expected to be provisioned separately, under its own least-privilege grant, if and when that requirement emerges.

---

## Summary

Every permission in this architecture answers a specific, narrow question: *does this identity need this exact action, on this exact resource, to perform its one documented responsibility?* Where AWS itself does not support that level of scoping (Rekognition's `DetectModerationLabels`), the exception is isolated, documented, and feature-flagged rather than silently broadening the surrounding role's blast radius.
