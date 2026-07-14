# Security Control Matrix

A quick-reference mapping of each security control to the AWS service that
implements it. For the reasoning behind each choice, see
[architecture-decisions.md](./architecture-decisions.md); for the threats
each control addresses, see [threat-model.md](./threat-model.md); for the
full narrative assessment, see [security-review.md](./security-review.md).

| Control | Service | Scope |
|---|---|---|
| Encryption at rest | AWS KMS (Customer Managed Key) | Both S3 buckets (primary + secondary region), key policy scoped to the processing Lambda role |
| Encryption in transit | CloudFront (HTTPS redirect) + TLS (SDK calls) | All client and internal service traffic |
| Edge threat protection | AWS WAF | AWS Managed Common Rule Set at the CloudFront edge (XSS, SQLi, known bad inputs) |
| Threat detection | Amazon GuardDuty | Continuous analysis of CloudTrail, VPC Flow Logs, and DNS query logs |
| Security findings aggregation | AWS Security Hub | CIS AWS Foundations / AWS Foundational Security Best Practices scoring |
| Audit logging | AWS CloudTrail | Multi-region trail, log file validation enabled |
| Least privilege | IAM (custom, per-role policies) | Every role scoped to specific bucket/queue/table ARNs — no `*FullAccess` managed policies |
| Object access control | CloudFront Origin Access Control (OAC) | Only path by which processed images are readable; direct S3 access denied |
| Public access prevention | S3 Block Public Access | Enforced on every bucket, all four settings |
| Alerting / incident signal | CloudWatch Alarms + SNS | Processor Errors, Queue Backlog Age, DLQ Has Messages |
| Content safety (optional) | Amazon Rekognition | `DetectModerationLabels`, fails safe rather than blocking the pipeline on error |
| Key rotation | AWS KMS | Annual automatic rotation enabled on every CMK |
