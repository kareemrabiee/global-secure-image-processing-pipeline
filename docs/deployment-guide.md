# Deployment Guide

This guide provides a complete, reproducible deployment procedure for the
Global Secure Image Processing Pipeline via the **AWS Console and AWS CLI**,
from prerequisites through post-deployment security and DR verification.
Exact per-role permissions are documented in [`infrastructure/iam-policies/`](../infrastructure/iam-policies)
— use those as the authoritative reference when creating each IAM role below.

---

## Prerequisites

| Requirement | Version / Notes |
|---|---|
| AWS Account | With sufficient IAM permissions to create the full resource set (IAM, S3, Lambda, SQS, DynamoDB, API Gateway, CloudFront, KMS, and — for Phase 2 — WAF, CloudTrail, GuardDuty, Security Hub) |
| Python | 3.12 (must match the Lambda runtime exactly) |
| `pip`, `zip` | Required to build the Pillow Lambda layer |
| AWS CLI | Configured with credentials for the target account |

---

## Required AWS Services

**Phase 1 (always-on core):** IAM, Amazon S3, AWS Lambda, Amazon SQS, Amazon DynamoDB, Amazon API Gateway, Amazon CloudFront, AWS KMS, Amazon CloudWatch, Amazon SNS.

**Phase 2 (optional):** AWS WAF, AWS CloudTrail, Amazon GuardDuty, AWS Security Hub, Amazon Route 53 (health checks), Amazon Rekognition (content moderation), plus a secondary AWS region for S3 CRR and DynamoDB Global Tables.

---

## Deployment Steps

1. **Clone the repository and build the Lambda dependency layer.**
   ```bash
   git clone <this-repo-url> && cd Global-Secure-Image-Processing-Pipeline
   chmod +x infrastructure/scripts/*.sh
   ./infrastructure/scripts/build_lambda_layer.sh
   ```
   This builds the Pillow layer pinned to `--platform manylinux2014_x86_64 --python-version 3.12`, matching the Lambda runtime exactly — a mismatch here is the most common first-deployment failure (see [`lessons-learned.md`](./lessons-learned.md)).

2. **Create the KMS Customer Managed Key.** Create a symmetric CMK with
   annual rotation enabled; scope its key policy to the Lambda execution
   role created in step 4 (see `infrastructure/iam-policies/kms-us-east-1-policy.py`
   for the exact statements).

3. **Create the S3 buckets.** One upload bucket, one processed bucket —
   both with versioning enabled, Block Public Access fully **On**, and
   default encryption set to the CMK from step 2. Configure the upload
   bucket's Event Notifications to publish `s3:ObjectCreated:*` to the SQS
   queue created in step 5.

4. **Create the two Lambda functions and their execution roles.**
   `GenerateUploadURL` (see [`lambda/GenerateUploadURL`](../lambda/GenerateUploadURL))
   and `ImageProcessor` (see [`lambda/ImageProcessor`](../lambda/ImageProcessor)),
   attaching the Pillow layer from step 1 to `ImageProcessor`. Create each
   function's execution role using the exact permission boundaries in
   `infrastructure/iam-policies/lambda-generate-url-role-policy.py` and
   `infrastructure/iam-policies/lambda-processor-role-policy.py` — no broader managed
   policy should be attached to either role.

5. **Create the SQS queue and Dead Letter Queue.** Set the main queue's
   redrive policy to point at the DLQ with `maxReceiveCount = 3` and
   `visibility_timeout_seconds = 60`; attach `ImageProcessor` as the
   queue's Lambda trigger. Reference `infrastructure/iam-policies/sqs-access-policy.py`
   for the queue policy allowing the S3 event source to publish.

6. **Create the DynamoDB metadata table.** On-Demand (`PAY_PER_REQUEST`)
   billing mode, partition key `ImageId`.

7. **Create the API Gateway HTTP API.** A single route (e.g.
   `POST /upload-url`) integrated with the `GenerateUploadURL` Lambda.

8. **Create the CloudFront distribution.** Origin = the processed S3
   bucket, using an **Origin Access Control (OAC)** (not a public bucket
   and not the legacy OAI); `viewer_protocol_policy` = redirect HTTP to
   HTTPS. Update the processed bucket's policy to grant `s3:GetObject`
   only to this distribution's OAC principal, conditioned on this exact
   distribution's ARN (`infrastructure/iam-policies/s3-processed-primary-policy.py`).

9. **Create the CloudWatch Alarms and SNS topic.** Three alarms —
   Processor Errors, Queue Backlog Age, DLQ Has Messages — each subscribed
   to a single SNS topic with an email subscription. See
   [`monitoring.md`](./monitoring.md) for exact thresholds.

10. **(Optional) Enable Phase 2 controls for validation/screenshots** — WAF,
    CloudTrail, GuardDuty, Security Hub, S3 CRR, DynamoDB Global Tables,
    Route 53 health check — one capability at a time, per the cost
    governance model in [`cost-analysis.md`](./cost-analysis.md). Disable
    each again once validation/evidence capture is complete.

---

## Validation Steps

1. **Install the test client dependency and run the smoke test.**
   ```bash
   pip install requests --break-system-packages
   python3 infrastructure/scripts/test_upload.py "<api_gateway_invoke_url>" ./sample-image.jpg
   ```
2. **Confirm processing completed.**
   - Check the `ImageProcessor` function's CloudWatch Log group for a successful invocation record.
   - Confirm a new item exists in the DynamoDB metadata table for the uploaded image.
   - Confirm the processed variants exist in the processed S3 bucket.
3. **Confirm CloudFront delivery.**
   ```
   https://<cloudfront_domain_name>/processed/<your-file>.jpg
   ```
   Expect an HTTP 200 response served over HTTPS.

---

## Post-Deployment Checks

- Confirm both S3 buckets show `Block Public Access: On` at the bucket level in the console.
- Confirm the processed bucket's bucket policy references the deployed CloudFront distribution's exact ARN.
- Confirm the KMS key shows `Key rotation: Enabled` in the console.
- Confirm the SQS main queue's redrive policy correctly references the DLQ's ARN, and that `maxReceiveCount` is set to `3`.
- Confirm CloudWatch Alarms (`processor-errors`, `queue-backlog-age`, `dlq-has-messages`) are in the `OK` state after a clean test run.

---

## Security Verification

1. **Attempt direct S3 object access**, bypassing CloudFront, against a known processed object key. Expect an HTTP 403 (`AccessDenied`) response, confirming OAC enforcement.
2. **(With WAF enabled) Submit a request containing a known XSS or SQLi payload pattern** against the CloudFront distribution. Expect an HTTP 403 response and a corresponding entry in the WAF sampled request log.
3. **Review IAM roles** for the two Lambda functions in the console or via `aws iam list-attached-role-policies`, confirming no `*FullAccess` managed policy is attached to either role.
4. **(With GuardDuty/Security Hub enabled) Review findings** in the respective console dashboards to confirm the detectors are active and reporting.

![WAF Blocked Request](../screenshots/01-security/waf-blocked-request.png)
![S3 Direct Access Denied](../screenshots/05-validation/s3-direct-access-denied.png)

---

## Monitoring Verification

1. Confirm the SNS topic has an active, confirmed email subscription (check the subscriber's inbox for the AWS subscription-confirmation email as soon as the topic is created).
2. Deliberately trigger the DLQ alarm by submitting a malformed payload (see [`testing-results.md`](./testing-results.md), Test 8) and confirm an SNS notification is received.
3. Review the CloudWatch dashboard to confirm all configured metrics are populating with recent data points.

---

## Disaster Recovery Verification

1. Enable S3 CRR and DynamoDB Global Tables (Phase 2, step 10 above).
2. Upload a test image and confirm the processed object's replication status shows `COMPLETED` in the secondary-region bucket.
3. Confirm the corresponding DynamoDB metadata item is readable from the secondary-region table replica.
4. Review the CloudFront distribution configuration to confirm it is serving from an **Origin Group** (both origins present, correct failover status codes configured).
5. Disable CRR and Global Tables once validation is complete, unless a persistent DR posture is intended for the deployment.

Full recovery procedures for an actual regional disruption are documented in [`disaster-recovery.md`](./disaster-recovery.md).

---

## Teardown

Manually remove resources in reverse dependency order (CloudFront →
S3 bucket policies/OAC → S3 buckets → Lambda triggers → SQS → DynamoDB →
API Gateway → KMS → IAM roles), or use the AWS CLI/console directly.

Before confirming teardown is complete:
- [ ] Empty both S3 buckets, including all non-current (versioned) objects, then delete the buckets.
- [ ] Confirm the CloudFront distribution is disabled, then deleted (this can take 15–20 minutes after being disabled).
- [ ] Confirm the KMS key(s) show `Pending Deletion` in the console.
- [ ] Confirm any Phase 2 controls (WAF, CloudTrail, GuardDuty, Security Hub, CRR, Global Tables, Route 53 health check) have been independently disabled/removed.
- [ ] Confirm no CloudWatch Alarms remain in a non-`OK` state referencing deleted resources.
