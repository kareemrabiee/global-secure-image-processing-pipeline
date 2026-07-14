# Risk Register

Architectural risks identified for this pipeline, and the mitigation
implemented for each. Cross-reference with
[threat-model.md](./threat-model.md) (security-focused threats) and
[disaster-recovery.md](./disaster-recovery.md) (regional-failure detail).

| Risk | Impact | Mitigation |
|---|---|---|
| Lambda concurrency spike (burst of uploads exceeding account concurrency limits) | Throttled invocations, delayed processing | SQS buffers ingestion ahead of Lambda, absorbing bursts; reserved concurrency can be set on the processor function if a hard per-function ceiling is needed |
| Region outage (primary AWS region unavailable) | Full ingestion/processing outage; read availability depends on DR posture | Documented multi-region DR path — S3 CRR, DynamoDB Global Tables, CloudFront Origin Group failover (see `disaster-recovery.md` for exact RTO/RPO and current limitations) |
| Public access exposure (accidental bucket/object public grant) | Full recursive image dump exposure | S3 Block Public Access enforced on every bucket; CloudFront OAC is the only read path to processed content |
| Excessive API requests (abuse or unintentional load against the presigned-URL endpoint) | Cost spike, degraded availability for legitimate users | CloudFront absorbs volumetric traffic at the edge; API Gateway default account-level throttling; WAF rate-based rules available when enabled |
| Poison message / repeatedly failing upload | Stuck processing, silent data loss if unmonitored | SQS redrive policy (`maxReceiveCount = 3`) isolates failures to a Dead Letter Queue; CloudWatch Alarm + SNS surfaces it immediately |
| KMS key misconfiguration or over-broad key policy | Unauthorized decryption of stored images | Key policy scoped to a single named Lambda role; no blanket account-wide grant beyond AWS's required root-account administrative statement |
| Cost drift from forgotten optional services | Unexpected recurring charges | Every non-Free-Tier capability (WAF, CloudTrail, GuardDuty, Security Hub, CRR, Global Tables, Route 53 health check) is explicit and independently toggleable — see `cost-analysis.md` |
| Dependency vulnerability in the Pillow Lambda layer | Potential remote code execution via a crafted image | Not currently automated — documented as an open gap in `assumptions-and-limitations.md`; Amazon Inspector or `pip-audit` would close it |
| Credential/role compromise (Lambda execution role) | Lateral movement within the account | Least-privilege IAM scoping limits blast radius to exactly this pipeline's named resources — see `least-privilege-review.md` |
| Manual, non-automated deployment process | Human error during configuration, configuration drift over time | Deployment steps fully documented in `deployment-guide.md`; formal infrastructure/CI-CD adoption listed as a near-term future enhancement |
