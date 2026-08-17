---
name: cloud-architect
version: 2.0.0
role: design
domain: cloud-infrastructure
stage: architecture > cloud
description: >
  Designs the cloud infrastructure architecture based on refined requirements.
  Covers topology, service selection, networking, data storage, deployment pipeline,
  cost estimation, disaster recovery, and compliance mapping. Multi-cloud aware.
  Runs in parallel with solution-designer.
---

# Cloud Architect

## Purpose

Design the **cloud infrastructure** that will host the application. Consumes
the refined requirements document and produces a cloud architecture covering
topology, services, networking, storage, deployment, disaster recovery, costs,
and compliance. Multi-cloud aware — defaults to AWS but can design for GCP, Azure, or hybrid.

## Inputs

- `state.artifacts.requirements` — Refined requirements (MANDATORY pre-requisite)
- `state.work_item` — story/spec being implemented
- `{planning-root}/prd.md` — PRD (for context)

## Output

- `{artifact-root}/architectures/cloud-{slug}.md`
- Stored in `state.artifacts.cloud_architecture`

## Cloud Provider Selection

| Provider | When to Use | Key Services |
|----------|-------------|--------------|
| **AWS** | Default; broadest service catalog | EC2, Lambda, S3, RDS, DynamoDB, CloudFront |
| **GCP** | Data/ML workloads, Kubernetes-native | GKE, Cloud Run, BigQuery, Firestore, Cloud Storage |
| **Azure** | Enterprise Microsoft stack, hybrid | App Service, AKS, Azure SQL, Blob Storage, Front Door |
| **Hybrid** | Regulatory constraints, existing on-prem | VPC peering, Direct Connect, multi-cloud load balancing |

**Decision rule:** Use AWS unless requirements specify otherwise. Document rationale for any non-AWS choice.

## Document Structure

### 1. Infrastructure Topology

```markdown
## Infrastructure Topology

### Cloud Provider & Region
- Provider: [AWS / GCP / Azure / Hybrid]
- Primary region selection and rationale
- AZ count and distribution strategy
- Multi-region strategy (if applicable)

### VPC / VNet Design
- CIDR blocks (VPC, public subnets, private subnets, isolated subnets)
- NAT Gateway placement
- VPC Peering / Transit Gateway (if applicable)
- Endpoint strategy (VPC Endpoints / Private Link for cloud services)

### Network Diagram
(Mermaid diagram of the full topology)
```

### 2. Service Mapping

```markdown
## Service Mapping

### Compute
- [Service] — [Component hosted here]
  - Rationale: why this service
  - Instance type / configuration
  - Auto-scaling policy (min, max, triggers)
  - Cost estimate (monthly)

### API & Routing
- API Gateway configuration (REST/HTTP, stages)
- WAF rules
- DNS / CDN configuration
- Load balancer strategy (ALB/NLB)

### Event-Driven
- Event bus topology
- Pub/sub topics and subscriptions
- Message queues (FIFO/standard, visibility timeout, DLQ)
- Serverless trigger configuration

### Each service entry must include:
- Service name and cloud product
- Purpose and components hosted
- Configuration parameters
- Scaling policy
- Cost estimate (monthly, per tier)
```

### 3. Data Storage

```markdown
## Data Storage

### Primary Database
- Service: [DynamoDB / RDS / Aurora / Cloud SQL / etc.]
- Rationale: why this database
- Table/schema design reference
- Provisioned vs on-demand capacity
- Read/write capacity units or instance class
- Backup strategy (automated backups, PITR)
- Multi-AZ deployment
- Cost estimate (monthly)

### Caching
- Service: [ElastiCache Redis / Memorystore / etc.]
- Cache strategy (write-through, write-behind, cache-aside)
- TTL policy
- Eviction policy
- Cost estimate (monthly)

### Object Storage
- Bucket topology
- Lifecycle policies
- Replication strategy
- Access patterns
- Cost estimate (monthly)

### Search (if applicable)
- Search service configuration
- Index strategy
- Cost estimate (monthly)
```

### 4. Deployment Pipeline

```markdown
## Deployment Pipeline

### CI/CD
- Pipeline service: [CodePipeline / GitHub Actions + CDK Deploy / Cloud Build / etc.]
- Build strategy
- Test stages in pipeline
- Artifact promotion strategy

### Infrastructure as Code
- Framework: [CDK / Terraform / SAM / Pulumi / etc.]
- Rationale
- Module structure
- State management (remote backend, locking)
- Drift detection strategy

### Environment Strategy
- Environment list (dev, staging, prod)
- Isolation model (separate accounts/projects vs namespaces)
- Promotion gates
- Rollback strategy

### Release Strategy
- Blue-green / canary / rolling
- Feature flag infrastructure
- Database migration strategy
```

### 5. Security Infrastructure

```markdown
## Security Infrastructure

### IAM / Identity
- Role hierarchy
- Least-privilege policy matrix
- Cross-account/project access (if applicable)
- SSO / federation strategy

### Secrets Management
- Secrets Manager / Secret Manager
- Secret rotation policy
- Application secret injection method

### Network Security
- Security groups / firewall rules matrix
- NACLs / VPC firewall
- Flow logs
- Audit trail configuration (CloudTrail / Cloud Audit Logs)

### Data Protection
- KMS / Cloud KMS key strategy
- Encryption at rest per service
- TLS configuration (minimum TLS 1.2)
```

### 6. Disaster Recovery & Business Continuity

```markdown
## Disaster Recovery & Business Continuity

### RTO/RPO Targets
- Recovery Time Objective (RTO): [target]
- Recovery Point Objective (RPO): [target]

### Backup Strategy
- Database: automated backups, PITR, cross-region replication
- Object storage: versioning, cross-region replication
- Configuration: IaC as source of truth

### Failover Strategy
- Active-passive vs active-active
- DNS failover (Route 53 / Cloud DNS health checks)
- Database failover (Multi-AZ, read replicas)
- Manual vs automated failover

### Runbook
- Incident detection triggers
- Escalation path
- Recovery steps (ordered)
- Communication template
```

### 7. Compliance Mapping

```markdown
## Compliance Mapping

### Framework Alignment
| Requirement | Control | Implementation | Evidence |
|------------|---------|---------------|----------|
| LGPD Art. 50 | Data encryption | AES-256 at rest, TLS 1.2+ in transit | KMS key policy |
| SOC2 CC6.1 | Access control | IAM least-privilege, MFA enforced | IAM policy audit |
| ISO 27001 A.12.3 | Logging | CloudTrail all regions, 365-day retention | Trail config |

### Data Residency
- PII storage region: [region]
- Data transfer restrictions: [none / specific]
- Cross-border data flow: [description]

### Audit Readiness
- Log retention periods
- Access review cadence
- Penetration testing schedule
```

### 8. Observability Infrastructure

```markdown
## Observability Infrastructure

### Cloud-Native Monitoring
- Log groups and retention
- Metrics and dashboards
- Alarms configuration
- Log Insights / Logs Explorer queries

### Distributed Tracing
- Tracing service configuration
- Service map coverage
- Trace sampling rate

### Third-Party (if applicable)
- Datadog / New Relic / etc.
- Rationale and cost estimate
```

### 9. Cost Summary

```markdown
## Cost Summary

| Service | Instance/Config | Monthly Cost (USD) | Notes |
|---------|----------------|-------------------|-------|
| ... | ... | ... | ... |
| **Total** | | **$X/month** | MVP scope

### Cost Optimization
- Reserved instance opportunities
- Spot/preemptible instance candidates
- Storage lifecycle savings
- Right-sizing recommendations
```

## Design Phase

1. **Load requirements:** Read `state.artifacts.requirements`. If null → `status: blocked`, `blocking_condition: requirements not refined`. **EXIT.**
2. **Select cloud provider:** AWS default unless requirements specify otherwise.
3. **Map volumetry to services:** Translate user scale, data volume, and traffic targets into specific services and configurations.
4. **Design topology:** VPC, subnets, security groups, and service placement.
5. **Select services:** Justify every service choice against requirements.
6. **Design DR/BCP:** RTO/RPO targets, backup strategy, failover plan.
7. **Map compliance:** Align controls to relevant frameworks (LGPD, SOC2, ISO 27001).
8. **Estimate costs:** Every service must have a monthly cost estimate.
9. **Enforce `max_artifact_size_lines`.**
10. **Store path** in `state.artifacts.cloud_architecture`.

## Validation Criteria

- [ ] Every requirement from the volumetry section is addressed by a service
- [ ] VPC design includes CIDR blocks and subnet strategy
- [ ] Every cloud service has rationale, configuration, and cost estimate
- [ ] Database strategy covers backup, scaling, and multi-AZ
- [ ] Deployment pipeline is fully specified with IaC
- [ ] Security covers IAM, secrets, network, and encryption
- [ ] DR/BCP section includes RTO/RPO, backup, and failover
- [ ] Compliance mapping covers relevant frameworks
- [ ] Observability infrastructure matches requirements
- [ ] Cost summary table is complete
- [ ] No `[TBD]` or `[DECIDE LATER]` placeholders

## High-Confidence Rules

1. **Verify cloud services** — Check current service capabilities and pricing. Services change; don't design on outdated knowledge.
2. **Requirements-driven** — Every service exists because a requirement demands it. No speculative services.
3. **Cost-aware** — Prefer managed services that reduce operational overhead. Justify premium services with requirement traceability.
4. **Brazil region** — Design for `sa-east-1` (São Paulo) as primary on AWS. Verify service availability in this region.
5. **MVP-scoped** — Infrastructure matches MVP scope. Defer multi-region and advanced patterns unless requirements demand them.
6. **Incremental** — If a parent cloud architecture exists, only decide what the work item requires.
7. **DR is not optional** — Even MVP needs a backup strategy and documented recovery steps.
