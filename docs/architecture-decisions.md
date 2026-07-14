# Architecture Decision Records (ADR)

This document records the significant architectural decisions made in the design of the Global Secure Image Processing Pipeline. Each ADR follows a consistent format — **Decision, Problem, Reason, Benefits, Trade-offs** — to support future architecture review, onboarding, and audit.

---

## ADR-001: Amazon API Gateway (HTTP API) as the Ingestion Entry Point

**Decision**
Use Amazon API Gateway HTTP API (not REST API) as the single public entry point for presigned upload URL issuance.

**Problem**
Clients need a way to initiate an upload without ever being issued long-lived AWS credentials, while the entry point itself must be resilient to abuse, cheap at low-to-moderate volume, and support CORS for browser-based clients.

**Reason**
HTTP APIs provide the subset of REST API functionality required here — Lambda proxy integration, CORS configuration, and route-based dispatch — at roughly 70% lower cost per request and lower baseline latency. REST API's additional features (request validation models, usage plans, private VPC endpoints) are not required for this workload's threat model.

**Benefits**
- Lower cost per million requests than REST API.
- Native CORS configuration without a Lambda-based OPTIONS handler.
- Reduced latency due to a simplified request-processing pipeline.
- Sufficient throttling and integration capabilities for a single-route ingestion API.

**Trade-offs**
- No built-in request validation models (schema validation must be enforced in Lambda).
- No native usage plans / API key tiering if per-client rate limiting becomes a requirement — would require migration to REST API or a custom authorizer-based quota system.
- Fewer integration types than REST API (sufficient here, but a constraint for more complex routing needs).

---

## ADR-002: AWS Lambda as the Compute Model for Both Processing Functions

**Decision**
Implement both `GenerateUploadURL` and `ImageProcessor` as independently deployed AWS Lambda functions rather than containerized services on ECS/Fargate or a persistent EC2 fleet.

**Problem**
The workload is bursty and unpredictable (user-driven upload volume), and any persistent compute layer would carry idle cost and require its own patching, scaling, and availability management.

**Reason**
Lambda's pay-per-invocation model and native integration with API Gateway, SQS, and IAM eliminates idle-capacity cost and infrastructure management overhead, while `reserved_concurrent_executions` provides a deterministic cost/blast-radius ceiling on the processing function.

**Benefits**
- Zero cost during idle periods — critical given unpredictable, spiky upload patterns.
- Automatic horizontal scaling driven directly by the SQS event source mapping, with no capacity planning.
- Function-level IAM roles enable precise least-privilege scoping per responsibility (issuing URLs vs. processing images), rather than one shared service identity.
- No OS-level patching or runtime management burden.

**Trade-offs**
- Cold-start latency exists, though bounded by function size and the Pillow layer's packaging.
- 15-minute maximum execution duration constrains any future move toward very large batch/video processing — would require Step Functions orchestration or Fargate for that class of workload.
- Reserved concurrency (`5` on the processor) caps throughput under extreme load by design; this is treated as a deliberate cost/blast-radius control rather than a hidden constraint, but must be revisited if sustained throughput requirements increase.

---

## ADR-003: Amazon SQS with a Dead Letter Queue for Ingestion-to-Processing Decoupling

**Decision**
Route S3 upload events through an SQS main queue with a dedicated Dead Letter Queue, rather than invoking the processing Lambda synchronously from the S3 event notification.

**Problem**
Direct S3-to-Lambda invocation ties ingestion throughput directly to processing throughput and provides no durable buffer if the processing function is throttled, degraded, or failing for a subset of messages.

**Reason**
SQS decouples the two concerns: ingestion succeeds independently of processing health, batch-based polling smooths invocation concurrency, and a bounded retry policy (3 attempts) with automatic DLQ redirection prevents both silent data loss and infinite retry loops on permanently malformed inputs.

**Benefits**
- Ingestion path remains available even during processing-side incidents.
- `ReportBatchItemFailures` isolates a single bad record within a batch instead of failing (and re-processing) the entire batch.
- DLQ provides an explicit, monitorable signal (`ApproximateNumberOfMessagesVisible`) for operator triage rather than losing failed jobs.
- Message retention (4 days main queue, 14 days DLQ) provides operational recovery windows during extended incidents.

**Trade-offs**
- Introduces eventual consistency between upload and processing completion — the client cannot assume synchronous processing.
- Adds an additional component to reason about during failure analysis (queue depth, visibility timeout tuning against Lambda timeout).
- DLQ messages require an explicit operational runbook and redrive process; without one, DLQ growth is a silent liability rather than a resolved incident.

---

## ADR-004: Amazon DynamoDB (On-Demand) as the Metadata Store

**Decision**
Use DynamoDB in on-demand (`PAY_PER_REQUEST`) capacity mode, with DynamoDB Streams enabled to support optional Global Tables replication, as the sole metadata store.

**Problem**
Upload volume is spiky and difficult to forecast; a provisioned-capacity relational or NoSQL store would require either over-provisioning (wasted cost) or capacity-planning overhead and throttling risk during bursts.

**Reason**
On-demand capacity mode eliminates capacity planning entirely and scales automatically with traffic, which matches the workload's access pattern (simple key-based writes/reads keyed on `ImageId`, no complex joins or transactions). Stream enablement is a prerequisite for Global Tables and costs nothing unless replication is activated.

**Benefits**
- No capacity planning or throttling risk under bursty load.
- Serverless operational model consistent with the rest of the stack (no instances, no patching).
- Native, near-zero-configuration path to multi-region active-active replication via Global Tables when DR requirements demand it.
- Point-in-time recovery available as an opt-in control without architectural change.

**Trade-offs**
- On-demand pricing per request is higher than well-utilized provisioned capacity at sustained high volume — a cost/predictability trade-off that should be revisited if traffic patterns stabilize.
- DynamoDB's key-value/single-table access model constrains complex relational querying; any future requirement for ad hoc analytical queries would need a separate read path (e.g., export to S3 + Athena) rather than direct DynamoDB queries.
- Global Tables (when enabled) introduce last-writer-wins conflict resolution semantics that must be accounted for in any future multi-writer scenario.

---

## ADR-005: Amazon CloudFront with Origin Access Control (OAC) for Asset Delivery

**Decision**
Serve all processed image assets exclusively through CloudFront, using Origin Access Control to authorize CloudFront as the only principal permitted to read from the private S3 processed bucket.

**Problem**
Serving assets directly from S3 (public bucket or public object ACLs) would violate the zero-public-storage security requirement and forfeit edge caching, HTTPS termination, and geographic performance benefits.

**Reason**
OAC (the modern replacement for Origin Access Identity) supports SigV4 signing for all request types, including custom headers, and allows the S3 bucket policy to scope access to a specific distribution ARN via a `StringEquals` / `AWS:SourceArn` condition — closing the OAI-era gap where a bucket policy could not fully prevent access from other distributions.

**Benefits**
- S3 buckets remain fully private (Block Public Access enforced) while still serving global traffic.
- Edge caching and compression reduce latency and origin load.
- HTTPS enforced at the edge (`viewer_protocol_policy = "redirect-to-https"`) without requiring per-object TLS handling in Lambda.
- Origin Group failover (Phase 2) is a natural extension of the same distribution when cross-region resilience is required.

**Trade-offs**
- Cache invalidation adds operational overhead when processed assets are updated in place (mitigated here by treating each processed key as immutable).
- CloudFront's default certificate is used to avoid ACM/custom-domain cost, which means the delivery domain is a CloudFront-assigned hostname rather than a branded domain — an explicit cost/branding trade-off for a portfolio deployment.
- `PriceClass_100` limits edge locations to the lowest-cost tier, which is a deliberate cost optimization but would need reconsideration for latency-sensitive global audiences outside North America/Europe.

---

## ADR-006: AWS WAF (Managed Rule Groups) Bound to the CloudFront Distribution

**Decision**
Attach an AWS WAFv2 Web ACL, using the AWS-managed Common Rule Set, to the CloudFront distribution as a feature-flagged Phase 2 control.

**Problem**
CloudFront alone provides transport security and caching but no payload-level inspection; the edge is otherwise exposed to common web exploitation techniques (XSS, SQL injection patterns, known-bad request signatures) with no compensating control.

**Reason**
AWS Managed Rule Groups provide continuously updated, AWS-curated protection against the OWASP-class threats most relevant to a public HTTP(S) surface, without the operational burden of authoring and maintaining custom rule logic. Gating the control behind a boolean flag reflects its non-trivial recurring cost relative to the platform's otherwise near-zero baseline.

**Benefits**
- Mitigates common injection and cross-site scripting patterns at the edge, before requests reach any origin.
- Rule groups are maintained and updated by AWS, reducing the team's ongoing security-engineering burden.
- CloudWatch metrics and sampled request logging provide visibility into blocked traffic without custom instrumentation.

**Trade-offs**
- Non-trivial recurring cost (Web ACL base fee + per-rule fee + per-request charge) relative to the rest of the stack's near-zero baseline — the explicit reason this control is feature-flagged rather than always-on in this portfolio deployment.
- WAF Web ACLs scoped to `CLOUDFRONT` must be provisioned in `us-east-1` regardless of the primary region — an easy-to-miss operational detail worth flagging in any deployment runbook.
- Managed rule groups can produce false positives against legitimate traffic patterns; production adoption requires a monitoring/tuning period before moving from `Count` to full blocking mode.

---

## ADR-007: AWS KMS Customer Managed Keys (CMKs) for All At-Rest Encryption

**Decision**
Encrypt all S3 objects with a Customer Managed KMS Key rather than the AWS-managed `aws/s3` key, with key policies scoped explicitly to the IAM roles that require cryptographic operations.

**Problem**
The AWS-managed `aws/s3` key applies a fixed, AWS-controlled key policy that cannot be scoped to specific IAM principals, undermining the least-privilege objective — any principal with generic S3 permissions can decrypt/encrypt without a corresponding, auditable grant on the key itself.

**Reason**
A Customer Managed Key allows the key policy to explicitly enumerate which IAM roles may call `kms:Decrypt` / `kms:GenerateDataKey`, making the cryptographic boundary an explicit, reviewable part of the least-privilege design rather than an implicit side effect of bucket permissions. Automatic annual key rotation is enabled to satisfy standard cryptographic hygiene requirements without manual key lifecycle management.

**Benefits**
- Key policy becomes an explicit, auditable least-privilege control surface, independent of IAM policy.
- Automatic key rotation without operational intervention.
- `bucket_key_enabled = true` reduces per-request KMS API call volume and associated cost.
- Supports clean separation of cross-region key material — a dedicated, region-local CMK is provisioned for the secondary region when Cross-Region Replication is enabled, since KMS keys cannot be referenced across regions.

**Trade-offs**
- Customer Managed Keys carry a flat monthly cost (~$1/month/key) with no Free Tier, unlike the AWS-managed key — the sole non-Free-Tier line item in the otherwise near-zero Phase 1 cost baseline.
- Requires deliberate key policy maintenance as IAM roles evolve; an omitted grant manifests as an opaque `KMS.AccessDeniedException` rather than an IAM-level error, which lengthens troubleshooting cycles for engineers unfamiliar with the key policy layer.
- Cross-region replication of KMS-encrypted objects requires explicit `source_selection_criteria` and a destination `replica_kms_key_id` — a non-obvious S3/KMS interaction that silently no-ops replication if omitted.
