# Security Review

This document is a professional security assessment of the Global Secure Image Processing Pipeline, structured against the domains most relevant to a serverless, edge-delivered, multi-region-capable architecture. It is intended to be reviewable by a security engineering or cloud audit function without requiring narrative explanation of basic AWS concepts.

---

## Encryption

**At rest.** Every S3 bucket in the architecture (upload, processed, and — when Cross-Region Replication is enabled — the secondary-region replica and CloudTrail log bucket) enforces SSE-KMS using a Customer Managed Key. No bucket relies on the AWS-managed `aws/s3` key, because that key's policy cannot be scoped to specific IAM principals. `bucket_key_enabled` is set on all encrypted buckets to reduce KMS API call volume without weakening the encryption guarantee.

**In transit.** CloudFront enforces `viewer_protocol_policy = "redirect-to-https"`, and API Gateway HTTP APIs are TLS-only by default. No component in the request path accepts plaintext HTTP for data in motion.

**Key management.** Automatic annual key rotation (`enable_key_rotation = true`) is enabled on every CMK. Key deletion is gated by a 7-day mandatory waiting window, preventing irreversible, accidental data loss from a key deletion action.

**Cross-region encryption.** When Cross-Region Replication is active, a dedicated, region-local CMK is provisioned in the secondary region. This is a hard AWS constraint, not a design preference — KMS key material cannot be referenced across regions, so replicating an SSE-KMS object requires the destination to re-encrypt with a key that exists in that region.

---

## Identity and Access Management

- No IAM principal in this architecture is attached to a managed `*FullAccess` policy.
- Every Lambda function has its own dedicated execution role, scoped to only the actions and resource ARNs that function requires.
- The one documented exception to ARN-level scoping is `rekognition:DetectModerationLabels`, which AWS does not support scoping by resource ARN (`Resource: "*"` is the only supported form for this action). This exception is isolated into its own IAM policy, attached to the processing role only when content moderation is explicitly enabled — the permission does not exist at all when the feature is off.
- The S3 replication role (used only when Cross-Region Replication is active) is scoped to exactly the source bucket (read replication-eligible object versions) and destination bucket (write replicated objects), plus the two region-specific KMS keys required to decrypt the source and re-encrypt the destination.

---

## Least Privilege

Least privilege is enforced structurally, not just documented as intent:

- IAM policies reference specific resource ARNs (bucket, queue, table, key) rather than wildcarded resource patterns.
- Read and write permissions are separated by function: the URL-issuance function can only `s3:PutObject` into the upload bucket; the processing function can only `s3:GetObject` from the upload bucket and `s3:PutObject` into the processed bucket. Neither function holds both read and write on both buckets.
- DynamoDB access is scoped to `dynamodb:PutItem` on the specific table ARN — no `Scan`, `Query`, `UpdateTable`, or administrative actions are granted to either Lambda role.

A conceptual walkthrough of every role's exact permission boundary is provided in [`least-privilege-review.md`](./least-privilege-review.md).

---

## Resource-Based Policies

Resource-based policies are used deliberately at every trust boundary where a principal outside the account's IAM role set needs access:

- **S3 bucket policy (processed bucket):** grants `s3:GetObject` exclusively to the CloudFront service principal, conditioned on `AWS:SourceArn` matching the specific distribution ARN — not any CloudFront distribution in the account, and not any other AWS account.
- **SQS queue policy:** grants `sqs:SendMessage` exclusively to the S3 service principal, conditioned on `aws:SourceArn` matching the specific upload bucket ARN.
- **KMS key policy:** grants cryptographic operations only to the root account (administrative recovery path) and the specific IAM role(s) requiring them — no account-wide or service-wide grant.

This pattern ensures that even a misconfigured IAM policy elsewhere in the account cannot independently grant access to these resources; the resource itself enforces its own trust boundary.

---

## CloudFront Origin Access Control (OAC)

OAC replaces the legacy Origin Access Identity (OAI) mechanism and is the AWS-recommended control for this architecture because it:

- Supports SigV4 request signing for all HTTP methods and headers, not just GET.
- Allows the origin bucket policy to scope trust to an exact distribution ARN via a `StringEquals` condition, closing a class of cross-distribution access issues that OAI could not fully prevent.
- Applies identically to both the primary and (when CRR is enabled) secondary-region processed buckets, ensuring the Origin Group failover path is protected by the same trust model as the primary origin.

---

## WAF Protection

The AWS Managed Common Rule Set is bound to the CloudFront distribution as a Phase 2 control. It is deployed with `override_action { none {} }` at the rule-group level — a deliberate configuration choice, since leaving this at the default `count` action would sample and log matching requests without actually blocking them, giving a false impression of active enforcement. CloudWatch metrics and sampled request logging are enabled for ongoing visibility into blocked traffic patterns.

---

## Security Hub

AWS Security Hub is subscribed to the **AWS Foundational Security Best Practices** standard, providing continuous, automated evaluation of the account's configuration against an industry-recognized baseline rather than relying solely on manual review.

---

## GuardDuty

Amazon GuardDuty is enabled with a 6-hour finding publication frequency, providing continuous, ML-driven analysis of CloudTrail management events, VPC flow logs (where applicable), and DNS query logs for indicators of compromise, reconnaissance, and anomalous account behavior.

---

## CloudTrail

CloudTrail is configured as a multi-region trail with `include_global_service_events = true` and `enable_log_file_validation = true`. Log file validation provides cryptographic proof that trail logs have not been altered or deleted after delivery, which is a prerequisite for treating CloudTrail output as forensically reliable evidence during an incident investigation.

---

## Security Monitoring

Security-relevant signals are surfaced through the same CloudWatch/SNS alerting path used for operational monitoring, rather than existing as a separate, disconnected system:

- GuardDuty and Security Hub findings are queryable directly in-console and exportable to EventBridge for further automation (a documented future enhancement — see [`assumptions-and-limitations.md`](./assumptions-and-limitations.md)).
- CloudTrail logs are the authoritative source for any post-incident forensic timeline reconstruction.
- WAF sampled request logs provide near-real-time visibility into blocked malicious traffic without requiring a separate log aggregation pipeline.

---

## Summary Assessment

The architecture demonstrates a defense-in-depth security posture appropriate for a public-facing, user-generated-content ingestion pipeline: no standing client credentials, no public storage, encryption enforced end-to-end with auditable key scoping, edge-layer payload inspection, and continuous detective controls layered over preventive ones. The primary residual risk accepted at Phase 1 is regional concentration of compute and storage, which is explicitly documented and has a defined, tested activation path (Phase 2 DR controls) rather than being an unaddressed gap.
