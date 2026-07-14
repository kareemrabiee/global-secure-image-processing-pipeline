# Assumptions and Limitations

This document states, without embellishment, the assumptions underlying the current architecture and the limitations a reviewer should weigh when assessing its production-readiness. Transparency here is treated as part of the engineering deliverable, not a liability to be minimized.

---

## Assumptions

- **Traffic profile.** The architecture assumes a bursty, moderate-volume, user-driven upload pattern (portfolio/demo to light-production scale), not sustained high-throughput ingestion. On-demand billing choices (DynamoDB, Lambda) are optimal under this assumption and would need re-evaluation under sustained high-volume load.
- **Single primary account.** The architecture assumes deployment into a single AWS account. Multi-account segregation (e.g., separating workload and security-tooling accounts under AWS Organizations) is not implemented.
- **Trusted image content type.** The presigned upload policy restricts content type and size but does not perform deep content validation before processing begins; Rekognition-based moderation (optional) is a post-hoc classification, not a pre-upload gate.
- **English-language, non-regulated content.** No data residency, data sovereignty, or regulated-industry compliance framework (HIPAA, PCI-DSS, FedRAMP) is assumed or engineered for in the current design.
- **Operator-driven infrastructure changes.** Deployments are assumed to be run by an authorized human operator with appropriate AWS credentials via the Console/CLI, not by an automated pipeline.

---

## Current Limitations

- **Single-region compute in steady state.** Lambda functions execute in the primary region only; there is no active-active or automatically failed-over compute layer for the ingestion path. Regional resilience currently covers the data plane (S3, DynamoDB) and delivery plane (CloudFront) but not compute — see [`disaster-recovery.md`](./disaster-recovery.md) for the documented cutover procedure.
- **No active-active processing.** Even with DR flags enabled, image processing occurs in one region at a time; there is no simultaneous dual-region processing of a single upload.
- **No CI/CD pipeline for infrastructure changes.** Deployment is performed manually via the AWS Console/CLI following `docs/deployment-guide.md`; there is no automated change-gating, pull-request-triggered validation, or drift detection pipeline yet.
- **No AWS Config integration.** Continuous configuration-compliance evaluation against custom or managed rules is not yet implemented; Security Hub's Foundational Security Best Practices standard provides partial, but not equivalent, coverage.
- **DynamoDB Point-in-Time Recovery disabled by default.** Enabled as an opt-in control to minimize cost in the portfolio deployment; a production adoption should enable this unconditionally.
- **No automated Lambda performance tuning.** Function memory allocations are configured based on reasoned defaults, not empirical benchmarking (e.g., AWS Lambda Power Tuning) against the actual image-processing workload profile.
- **No WAF rate-based rules.** The current WAF configuration uses the AWS Managed Common Rule Set only; rate-based rules for application-layer flood mitigation are not yet configured.
- **No automated ingestion failover.** A full primary-region outage requires manually redeploying the ingestion stack (API Gateway + Lambda) to the secondary region; this is not yet a one-command or automatic operation.
- **GuardDuty/Security Hub findings are not yet automated into a response workflow.** Findings are currently reviewed manually in-console rather than routed through EventBridge into an automated triage or remediation pipeline.

---

## Future Improvements

Improvements are ordered by the sequence in which they would most plausibly be prioritized for a production adoption of this architecture:

1. **Formal Infrastructure-as-Code adoption** — move from manual Console/CLI deployment to a version-controlled infrastructure tool with remote state, enabling safe team-based collaboration.
2. **CI/CD pipeline (GitHub Actions)** — automate linting and validation of IAM policy/configuration changes on pull requests, with deployment gated behind manual approval on merge to the main branch.
3. **AWS Config** — introduce continuous compliance evaluation against both AWS-managed and custom Config rules, closing the gap left by Security Hub's standard-based (rather than rule-by-rule) posture assessment.
4. **AWS Backup** — layer policy-driven backup schedules over DynamoDB and S3 beyond native versioning, providing centrally managed retention and restore workflows.
5. **Lambda performance tuning** — apply AWS Lambda Power Tuning to empirically validate the memory/cost/duration curve for the image-processing function.
6. **EventBridge-driven security response automation** — route GuardDuty and Security Hub findings into an automated triage/quarantine workflow rather than manual console review.
7. **Multi-account segregation** — separate the workload account from a dedicated security-tooling account using AWS Organizations, aligning with AWS's recommended multi-account strategy for production workloads.
8. **Automated ingestion-path failover** — extend the current data/delivery-plane DR story to include a scripted or fully automated compute-layer cutover for the ingestion path during a full regional outage.

These items are deliberately not implemented in the current version of this repository; each represents a scoped, well-understood next increment rather than an open-ended aspiration.
