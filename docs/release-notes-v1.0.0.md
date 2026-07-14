# Release Notes

## v1.0.0 — Initial Production Portfolio Release

> **How to publish this as a GitHub Release:** push a tag (`git tag v1.0.0 && git push origin v1.0.0`), then on GitHub go to **Releases → Draft a new release**, select the `v1.0.0` tag, and paste the content below as the release description.

### Highlights

- **Serverless Architecture** — API Gateway, Lambda, SQS, DynamoDB, S3, and CloudFront working as a fully event-driven pipeline with no idle standing infrastructure
- **Security-First Design** — Customer Managed KMS encryption, least-privilege IAM on every role, CloudFront OAC with zero public storage exposure, AWS WAF at the edge
- **Disaster Recovery** — documented, flag-gated multi-region path: S3 Cross-Region Replication, DynamoDB Global Tables, CloudFront Origin Group failover
- **Global Content Delivery** — CloudFront edge caching for low-latency image delivery worldwide
- **Monitoring & Alerting** — CloudWatch Alarms + SNS covering processing errors, queue backlog age, and Dead Letter Queue activity

### Documentation included

Executive Summary, 7 Architecture Decision Records, full Threat Model,
Security Review, Least-Privilege Review, Security Control Matrix, Risk
Register, Disaster Recovery Strategy, Cost Analysis, Well-Architected
Framework Mapping, 11-test Validation Matrix, Assumptions & Limitations,
Lessons Learned, Monitoring design, and a full Deployment Guide.

### Known limitations at this release

See [`docs/assumptions-and-limitations.md`](../docs/assumptions-and-limitations.md)
— most notably: compute is single-region (DR covers data and delivery, not
yet ingestion), and deployment is currently manual (Console/CLI) rather
than automated via CI/CD.
