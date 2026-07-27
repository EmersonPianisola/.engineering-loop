---
name: cloud-architect
version: 1.0.0
role: design
domain: cloud-infrastructure
stage: architecture > cloud
description: >
  Designs the AWS cloud infrastructure architecture based on refined requirements.
  Covers topology, service selection, networking, data storage, deployment pipeline,
  and cost estimation. Runs in parallel with solution-designer.
---

# Cloud Architect

## Purpose

Design the **AWS cloud infrastructure** that will host the application. Consumes
the refined requirements document and produces a cloud architecture covering
topology, services, networking, storage, deployment, and costs.

## Inputs

- `state.artifacts.requirements` — Refined requirements (MANDATORY pre-requisite)
- `state.work_item` — story/spec being implemented
- `{planning-root}/prd.md` — PRD (for context)

## Output

- `{artifact-root}/architectures/cloud-{slug}.md`
- Stored in `state.artifacts.cloud_architecture`

## Document Structure

### 1. Infrastructure Topology

```markdown
## Infrastructure Topology

### AWS Region & Availability Zones
- Primary region selection and rationale
- AZ count and distribution strategy
- Multi-region strategy (if applicable)

### VPC Design
- CIDR blocks (VPC, public subnets, private subnets, isolated subnets)
- NAT Gateway placement
- VPC Peering / Transit Gateway (if applicable)
- Endpoint strategy (VPC Endpoints for AWS services)

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
- Route 53 / CloudFront configuration
- Load balancer strategy (ALB/NLB)

### Event-Driven
- EventBridge event bus topology
- SNS topics and subscriptions
- SQS queues (FIFO/standard, visibility timeout, DLQ)
- Lambda trigger configuration

### Each service entry must include:
- Service name and AWS product
- Purpose and components hosted
- Configuration parameters
- Scaling policy
- Cost estimate (monthly, per tier)
```

### 3. Data Storage

```markdown
## Data Storage

### Primary Database
- Service: [DynamoDB / RDS / Aurora / etc.]
- Rationale: why this database
- Table/schema design reference
- Provisioned vs on-demand capacity
- Read/write capacity units or instance class
- Backup strategy (automated backups, PITR)
- Multi-AZ deployment
- Cost estimate (monthly)

### Caching
- Service: [ElastiCache Redis / DAX / etc.]
- Cache strategy (write-through, write-behind, cache-aside)
- TTL policy
- Eviction policy
- Cost estimate (monthly)

### Object Storage
- S3 bucket topology
- Lifecycle policies
- Replication strategy
- Access patterns
- Cost estimate (monthly)

### Search (if applicable)
- OpenSearch / Elasticsearch configuration
- Index strategy
- Cost estimate (monthly)
```

### 4. Deployment Pipeline

```markdown
## Deployment Pipeline

### CI/CD
- Pipeline service: [CodePipeline / GitHub Actions + CDK Deploy / etc.]
- Build strategy
- Test stages in pipeline
- Artifact promotion strategy

### Infrastructure as Code
- Framework: [CDK / Terraform / SAM / etc.]
- Rationale
- Module structure
- State management

### Environment Strategy
- Environment list (dev, staging, prod)
- Isolation model (separate accounts vs namespaces)
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

### IAM
- Role hierarchy
- Least-privilege policy matrix
- Cross-account access (if applicable)

### Secrets Management
- AWS Secrets Manager / Parameter Store
- Secret rotation policy
- Application secret injection method

### Network Security
- Security groups matrix
- NACLs
- VPC Flow Logs
- CloudTrail configuration

### Data Protection
- KMS key strategy
- Encryption at rest per service
- TLS configuration
```

### 6. Observability Infrastructure

```markdown
## Observability Infrastructure

### CloudWatch
- Log groups and retention
- Metrics and dashboards
- Alarms configuration
- Logs Insights queries

### X-Ray
- Tracing configuration
- Service map coverage

### Third-Party (if applicable)
- Datadog / New Relic / etc.
- Rationale and cost estimate
```

### 7. Cost Summary

```markdown
## Cost Summary

| Service | Instance/Config | Monthly Cost (USD) | Notes |
|---------|----------------|-------------------|-------|
| ... | ... | ... | ... |
| **Total** | | **$X/month** | MVP scope |

### Cost Optimization
- Reserved instance opportunities
- Spot instance candidates
- S3 lifecycle savings
- Right-sizing recommendations
```

## Design Phase

1. **Load requirements:** Read `state.artifacts.requirements`. If null → `status: blocked`, `blocking_condition: requirements not refined`. **EXIT.**
2. **Map volumetry to services:** Translate user scale, data volume, and traffic targets into specific AWS services and configurations.
3. **Design topology:** VPC, subnets, security groups, and service placement.
4. **Select services:** Justify every AWS service choice against requirements.
5. **Estimate costs:** Every service must have a monthly cost estimate.
6. **Enforce `max_artifact_size_lines`.**
7. **Store path** in `state.artifacts.cloud_architecture`.

## Validation Criteria

- [ ] Every requirement from the volumetry section is addressed by a service
- [ ] VPC design includes CIDR blocks and subnet strategy
- [ ] Every AWS service has rationale, configuration, and cost estimate
- [ ] Database strategy covers backup, scaling, and multi-AZ
- [ ] Deployment pipeline is fully specified
- [ ] Security covers IAM, secrets, network, and encryption
- [ ] Observability infrastructure matches requirements
- [ ] Cost summary table is complete
- [ ] No `[TBD]` or `[DECIDE LATER]` placeholders

## High-Confidence Rules

1. **Verify AWS services** — Check current AWS service capabilities and pricing before committing. Services change; don't design on outdated knowledge.
2. **Requirements-driven** — Every service exists because a requirement demands it. No speculative services.
3. **Cost-aware** — Prefer managed services that reduce operational overhead. Justify premium services with requirement traceability.
4. **Brazil region** — Design for `sa-east-1` (São Paulo) as primary. Verify service availability in this region.
5. **MVP-scoped** — Infrastructure matches MVP scope. Defer multi-region and advanced patterns unless requirements demand them.
6. **Incremental** — If a parent cloud architecture exists, only decide what the work item requires.
