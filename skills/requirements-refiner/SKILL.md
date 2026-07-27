---
name: requirements-refiner
version: 1.0.0
role: design
domain: requirements-engineering
stage: architecture > requirements
description: >
  Refines BMad planning artifacts into detailed, quantified requirements with
  volumetry, scalability targets, and observability needs. Produces the foundation
  document that cloud and solution architects consume in parallel.
---

# Requirements Refiner

## Purpose

Transform high-level BMad planning artifacts (PRD, brief, UX designs) into
**detailed, quantified requirements** that include volumetry, scalability targets,
and observability needs. This document is the shared input for both cloud and
solution architecture skills.

## Inputs

- `state.work_item` — story/spec being implemented
- BMad planning artifacts:
  - `{planning-root}/prd.md` — Product Requirements Document
  - `{planning-root}/briefs/` — Product brief
  - `{planning-root}/ux-designs/` — UX design specs
  - `{planning-root}/architecture/` — Architecture spine (if exists)

## Output

- `{artifact-root}/architectures/requirements-{slug}.md`
- Stored in `state.artifacts.requirements`

## Document Structure

### 1. Functional Requirements (Detailed)

```markdown
## Functional Requirements

### User Journeys
- Complete user flow per feature (trigger → action → outcome)
- Authentication and authorization paths
- Data entry and validation flows
- Error recovery flows

### Feature Specifications
- Per-feature: description, actors, preconditions, postconditions
- Acceptance criteria (quantified where applicable)
- Non-functional constraints per feature (latency, availability, etc.)

### Integration Points
- External services and APIs consumed
- Data import/export requirements
- Third-party SDK dependencies
```

### 2. Volumetry

```markdown
## Volumetry

### User Scale
- Concurrent users (target, peak, projected 12-month)
- Active users per day/month
- Geographic distribution

### Data Volume
- Records per entity (users, vehicles, matches, etc.)
- Estimated data growth rate (monthly)
- Media storage (images, documents — size per item, items per day)
- Cache hit rate targets

### Traffic
- Requests per second (average, peak)
- API endpoint call frequency
- Background job throughput
- File upload/download bandwidth

### Storage
- Database size projection (30/90/365 days)
- Blob storage projection
- Log retention volume
- Backup storage requirements
```

### 3. Scalability Targets

```markdown
## Scalability

### Horizontal Scaling
- Auto-scaling triggers (CPU, memory, request count, queue depth)
- Minimum/maximum instance count per service
- Scaling cooldown periods

### Vertical Scaling
- Database connection pool limits
- Memory requirements per service
- CPU requirements per service

### Regional Strategy
- Single-region vs multi-region
- Data residency requirements
- Failover RTO/RPO targets

### Burst Handling
- Expected traffic spikes (marketing, events)
- Queue-based load leveling strategy
- Rate limiting thresholds
```

### 4. Observability Requirements

```markdown
## Observability

### Logging
- Log levels and structure (JSON, fields)
- Correlation IDs strategy
- Sensitive data redaction rules
- Log retention periods per environment

### Metrics
- Business metrics (sign-ups, matches, swap requests)
- Infrastructure metrics (CPU, memory, disk, network)
- Application metrics (request latency, error rate, throughput)
- Custom metrics per domain

### Tracing
- Distributed tracing strategy
- Trace sampling rate
- Propagation headers standard

### Alerting
- Critical alerts (immediate page)
- Warning alerts (slack/email)
- Dashboard requirements
- On-call rotation expectations

### Health Checks
- Liveness and readiness probe strategy
- Dependency health checks
- Synthetic monitoring targets
```

### 5. Security Requirements

```markdown
## Security Requirements

### Authentication & Authorization
- OAuth provider requirements
- Role-based access control matrix
- Session management strategy
- Token lifecycle

### Data Protection
- Encryption at rest (algorithm, key management)
- Encryption in transit (TLS version)
- PII handling and GDPR/LGPD compliance
- Data retention and deletion policy

### Infrastructure Security
- Network segmentation requirements
- IAM least-privilege model
- Secret management strategy
- Audit logging requirements
```

## Design Phase

1. **Load context:** Read all BMad planning artifacts.
2. **Extract quantifiable targets:** For every requirement, derive volumetry numbers. When exact numbers are unavailable, use reasoned estimates with explicit `[ESTIMATE]` tags and source rationale.
3. **Define scalability profile:** Map user scale to infrastructure scale.
4. **Specify observability needs:** Every operational concern must have a corresponding observability requirement.
5. **Enforce `max_artifact_size_lines`.**
6. **Store path** in `state.artifacts.requirements`.

## Validation Criteria

- [ ] Every PRD feature has detailed user journeys
- [ ] Volumetry includes user scale, data volume, traffic, and storage
- [ ] Scalability targets specify horizontal and vertical scaling
- [ ] Observability covers logging, metrics, tracing, alerting, and health checks
- [ ] Security requirements cover auth, data protection, and infrastructure
- [ ] All estimates are tagged with `[ESTIMATE]` and rationale
- [ ] No vague language ("high availability" → "99.9% uptime, <1s failover")

## High-Confidence Rules

1. **Quantify everything** — Replace qualitative terms with numbers. "Many users" → "5,000 MAU target, 500 concurrent peak."
2. **Tag estimates** — Every number not from the PRD is an `[ESTIMATE]` with source.
3. **Brazil context** — Consider LGPD compliance, Brazilian geographic distribution, and local infrastructure availability.
4. **MVP-scoped** — Volumetry reflects MVP scope, not v2.0 projections.
5. **Traceable** — Every requirement links to a PRD section or UX flow.
