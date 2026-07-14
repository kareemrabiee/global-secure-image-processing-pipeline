# Lessons Learned

This document captures the substantive technical challenges encountered while engineering this architecture, and the durable insights each produced. It is written for a reader evaluating engineering judgment, not just final-state correctness.

---

## Challenges Faced

| Challenge | Root Cause | Resolution |
|---|---|---|
| S3 Cross-Region Replication silently failed to replicate any objects | S3 does not replicate SSE-KMS-encrypted objects by default; the replication rule must explicitly enable `source_selection_criteria.sse_kms_encrypted_objects` | Added explicit source-selection criteria and a destination `replica_kms_key_id`, matching S3's documented (but easy to miss) requirement for encrypted-object replication |
| `enable_waf = true` failed with `InvalidParameterException ... CLOUDFRONT scope` | WAFv2 Web ACLs scoped to `CLOUDFRONT` must be created in `us-east-1` regardless of the stack's primary region | Introduced a dedicated `aws.us_east_1` provider alias used exclusively for the CloudFront-scoped Web ACL resource |
| WAF appeared configured but was not actually blocking malicious requests | `override_action` at the rule-group level defaulted to `count` (log-only) rather than `none` (enforce) | Explicitly set `override_action { none {} }` on the managed rule group; verified enforcement via a deliberate XSS test request returning HTTP 403 |
| CloudFront returned `AccessDenied` (403) on legitimate processed-image requests | The S3 bucket policy's `AWS:SourceArn` condition did not match the distribution, or OAC was not attached to the origin | Confirmed `origin_access_control_id` was set on the origin block and that the bucket policy condition referenced the exact `aws_cloudfront_distribution.cdn.arn` |
| Environment variable names referenced in Lambda code did not match what was configured in the console during early manual testing | Manual console configuration and code expectations drifted independently | Every environment variable is now defined once in each Lambda function's configuration and read via `os.environ[...]`, which fails loudly (rather than silently defaulting) if a variable is missing |
| Object keys containing spaces or special characters broke downstream S3 GET calls | S3 event notification payloads URL-encode object keys; the processing code did not account for this | Applied `urllib.parse.unquote_plus()` to every object key extracted from an event payload before use |
| A single malformed image in an SQS batch caused the entire batch to be retried | The event source mapping's default failure handling treats a batch as atomic unless configured otherwise | Implemented per-record `try/except` handling combined with `function_response_types = ["ReportBatchItemFailures"]`, isolating retries to only the failed record |
| The Pillow Lambda layer built on a local development machine failed at runtime | The layer was built for the local machine's Python version/architecture rather than the Lambda execution environment | Pinned the build to `--platform manylinux2014_x86_64 --python-version 3.12` in the layer build script to exactly match the Lambda runtime |
| IAM roles initially used broad managed policies during early prototyping | Managed policies (`AmazonS3FullAccess`, etc.) are the path of least resistance during rapid prototyping | Replaced every managed policy attachment with a custom policy scoped to specific bucket/queue/table/key ARNs before considering the architecture complete |
| Watermark text rendered as unreadable placeholder glyphs in some Lambda executions | The expected TrueType font path was not guaranteed to be present in the Lambda base runtime image | Implemented an automatic fallback to `ImageFont.load_default()`; documented that bundling the specific font file into the Pillow layer is the fix if exact typography is required |

---

## Lessons Learned

- **Encryption interacts with almost every other AWS feature in non-obvious ways.** SSE-KMS is not a drop-in replacement for default encryption when replication, cross-account access, or cross-region operations are involved — each of those features has its own, separately documented KMS interaction that must be explicitly satisfied.
- **A feature that "looks" configured is not the same as a feature that is enforcing.** The WAF `override_action` issue is the clearest example: the Web ACL existed, was attached to the distribution, and appeared correctly configured in the console, yet was not blocking anything until the enforcement action was explicitly set.
- **Region-scoped exceptions to otherwise region-agnostic patterns need to be handled explicitly, not assumed away.** WAF-for-CloudFront's mandatory `us-east-1` requirement is a good example of an AWS platform quirk with no error-prevention hint in the console itself — it simply fails at creation time if not anticipated.

---

## Operational Insights

- Structured, per-function environment variables read via a fail-loud pattern (`os.environ[...]` rather than `os.environ.get(..., default)`) surface misconfiguration immediately at first invocation rather than producing a silently wrong result days later.
- Isolating failure handling to the individual record level (rather than the batch level) is a small implementation change with an outsized reliability payoff — it is the difference between "one bad image delays nothing" and "one bad image blocks an entire batch's worth of legitimate uploads."
- DLQ depth is a leading indicator worth alarming on independently of Lambda error rate — a function can have a healthy error rate while still accumulating unresolved DLQ messages if retries are exhausted just below the error-rate alarm threshold's evaluation window.

---

## Security Insights

- Least privilege is easiest to get right at the start of a project and progressively harder to retrofit — the earlier managed-policy prototyping phase, though quickly replaced, is a reminder that "temporary" broad permissions have a way of persisting if not deliberately revisited before considering a component complete.
- Resource-based policies (S3 bucket policy, SQS queue policy, KMS key policy) are a distinct and complementary control from IAM identity-based policies, not a redundant one — several of the controls in this architecture (OAC bucket policy scoping, SQS `SourceArn` conditions) have no IAM-side equivalent and must be reasoned about separately.
- An AWS-documented exception to least-privilege scoping (Rekognition's `Resource: "*"` requirement) is best handled by isolating it into its own narrowly-attached policy rather than treating it as precedent for looser scoping elsewhere.

---

## Architecture Insights

- Decoupling ingestion from processing via SQS is valuable even at low volume — the resilience and failure-isolation benefits (DLQ, per-record retry) are not scale-dependent; they matter as much at ten uploads a day as at ten thousand.
- Designing the DR mechanisms (CRR, Global Tables, Origin Group failover) as flag-gated capabilities — rather than deploying them unconditionally or documenting them as a purely theoretical future step — produced a materially more credible and testable disaster recovery story than either extreme would have.
- CloudFront's Origin Group is a genuinely elegant mechanism for failover: the failover logic lives entirely at the CDN layer, requiring no application-side awareness of which region is currently serving traffic.

---

## Cloud Cost Insights

- The single largest cost lever in this entire architecture is not any individual service choice — it is the decision to phase-gate every advanced/security/DR capability behind an explicit boolean flag. This converts "what is this costing me right now" from a resource-by-resource audit into a single, glanceable set of variable values.
- Customer Managed KMS Keys are the one Free-Tier-ineligible line item in an otherwise near-zero-cost core stack — a useful reminder that strong encryption-key governance is a deliberate, small, and worthwhile cost to accept rather than a reason to fall back to a less-scoped default key.
- Storage lifecycle tiering only pays off if retrieval-latency requirements are respected — choosing Glacier Instant Retrieval over standard Glacier for the processed-image bucket was a direct consequence of remembering that these objects are still being served live through CloudFront, not archived.
