# AWS Well-Architected Framework Mapping

This document maps the Global Secure Image Processing Pipeline against all six pillars of the AWS Well-Architected Framework, with explicit design decisions cited as evidence for each assessment rather than general statements of intent.

---

## Security

| Design Element | Well-Architected Alignment |
|---|---|
| Customer Managed KMS keys with per-role key policy scoping | Implements the principle of protecting data at rest with encryption keys under explicit, auditable access control rather than a broad, AWS-managed default |
| Presigned, time-bound S3 upload policies | Eliminates standing/long-lived credentials from the client-facing trust boundary — a core identity-and-access-management best practice |
| Per-function IAM roles scoped to explicit resource ARNs | Enforces least privilege structurally, not procedurally |
| S3 Block Public Access + CloudFront OAC | Enforces a "private by default, access via explicit trust" posture on all data at rest |
| AWS WAF managed rule groups | Provides edge-layer protection against common web exploitation classes |
| CloudTrail (multi-region, log file validation) | Provides a tamper-evident audit trail supporting incident investigation and compliance evidencing |
| GuardDuty + Security Hub | Layers continuous detective controls (behavioral threat detection, posture-against-standard aggregation) over the architecture's preventive controls |

**Assessment:** Strong alignment. The architecture treats security as a structural property (resource-based policies, key policy scoping, zero standing credentials) rather than a configuration checklist, consistent with the Security Pillar's design principles of implementing a strong identity foundation, enabling traceability, and applying security at all layers.

---

## Reliability

| Design Element | Well-Architected Alignment |
|---|---|
| SQS main queue + DLQ decoupling | Isolates ingestion availability from processing availability; bounded retries prevent both silent loss and infinite retry loops |
| `ReportBatchItemFailures` on the event source mapping | Prevents a single malformed record from causing unnecessary reprocessing of an entire batch |
| S3 Versioning (both buckets) | Provides recovery from accidental overwrite/deletion independent of any DR activation |
| Multi-AZ-native managed services throughout (S3, Lambda, SQS, DynamoDB, API Gateway, CloudFront) | Removes single-AZ failure as an architectural concern without any additional configuration |
| CloudWatch Alarms (Lambda errors, queue backlog age, DLQ depth) + SNS | Provides automated detection of degradation before it becomes a full incident |
| Feature-flagged multi-region DR (S3 CRR, DynamoDB Global Tables, CloudFront Origin Group) | Provides a defined, tested path to regional resilience, explicitly documented rather than assumed |

**Assessment:** Strong alignment at the AZ level (inherent to the managed-service choices) and a well-defined, if not always-on, regional resilience story. The primary gap — no automatic failover for the ingestion compute path during a full regional outage — is explicitly documented in [`disaster-recovery.md`](./disaster-recovery.md) rather than left implicit.

---

## Performance Efficiency

| Design Element | Well-Architected Alignment |
|---|---|
| Event-driven Lambda concurrency scaling | Matches compute capacity to actual demand automatically, without manual intervention |
| CloudFront edge caching and compression | Reduces latency for global consumers and reduces origin load |
| Lambda memory allocation tuned per function (128 MB for URL issuance, 512 MB for image processing) | Reflects each function's actual compute profile rather than a one-size-fits-all default |
| DynamoDB on-demand capacity | Automatically matches read/write throughput to actual load without manual capacity management |

**Assessment:** Solid alignment for the current workload profile. Lambda memory allocation is a starting configuration rather than a benchmarked optimum; a documented future step (see [`assumptions-and-limitations.md`](./assumptions-and-limitations.md)) is running AWS Lambda Power Tuning to empirically validate the memory/cost/duration curve for the image-processing function specifically.

---

## Cost Optimization

| Design Element | Well-Architected Alignment |
|---|---|
| Fully serverless compute and storage primitives | Eliminates idle-capacity cost across the entire core stack |
| S3 lifecycle tiering (Standard → Standard-IA → Glacier Instant Retrieval) | Matches storage cost to actual access-frequency patterns over an object's lifetime |
| DynamoDB on-demand billing | Removes the cost risk of both over- and under-provisioned capacity |
| Phase-gated advanced/security tooling behind explicit boolean flags | Makes recurring cost exposure an explicit, reviewable decision rather than an implicit default |
| CloudFront `PriceClass_100` | Excludes higher-cost edge regions not required by the current user base |

**Assessment:** Strong alignment. The phase-gating pattern in particular reflects mature cost governance — every cost-generating capability beyond the always-on core is a named, auditable, reversible decision.

---

## Operational Excellence

| Design Element | Well-Architected Alignment |
|---|---|
| Documented, repeatable deployment procedure | Infrastructure changes follow a reviewed, version-controlled runbook (`docs/deployment-guide.md`) rather than undocumented ad-hoc console changes |
| CloudWatch Logs with bounded retention per function | Supports operational troubleshooting without unbounded log-storage cost accumulation |
| CloudWatch Alarms + SNS notification | Provides proactive operational awareness rather than relying on reactive incident discovery |
| DLQ-based failure isolation | Converts silent failures into a visible, actionable operational signal |
| Documented runbooks (deployment, DR recovery, testing) | Reduces reliance on tacit/undocumented operational knowledge |

**Assessment:** Good foundational alignment via infrastructure and monitoring. The most significant gap — no CI/CD pipeline for validating and applying infrastructure changes — is explicitly tracked as a near-term roadmap item rather than left unaddressed.

---

## Sustainability

| Design Element | Well-Architected Alignment |
|---|---|
| Serverless-first architecture | Avoids the energy and resource footprint of always-on, underutilized infrastructure |
| S3 lifecycle tiering to colder storage classes | Colder storage tiers are generally associated with more energy-efficient, higher-density storage infrastructure |
| Event-driven, on-demand compute scaling | Compute resources are provisioned and released precisely in proportion to actual demand, minimizing wasted resource allocation |
| `PriceClass_100` CloudFront configuration | Reduces the number of edge locations actively serving traffic to only those required, indirectly limiting the infrastructure footprint engaged per request |

**Assessment:** Reasonable alignment as an emergent property of the serverless, on-demand design rather than sustainability-specific engineering. A more rigorous sustainability assessment would require workload-level carbon-impact tooling (e.g., the AWS Customer Carbon Footprint Tool) rather than architectural inference alone.

---

## Overall Posture

The architecture demonstrates disciplined alignment with Security, Cost Optimization, and Reliability at the availability-zone level, with Performance Efficiency and Operational Excellence well-supported but carrying clearly documented, prioritized next steps (Lambda performance tuning, CI/CD). Regional-outage-level Reliability and organization-wide Sustainability measurement are the two areas with the most room for further maturity, and both have explicit, non-hand-wavy paths forward documented in this repository rather than being left as unstated gaps.
