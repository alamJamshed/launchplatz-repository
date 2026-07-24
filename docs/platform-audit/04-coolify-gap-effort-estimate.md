# Coolify Gap Engineering-Effort Estimate

Estimate date: 2026-07-23  
Units: one engineering week = 5 engineering days; one person-month = 20 engineering days.

## Executive estimate

Production-capable broad Coolify-like coverage is estimated at **6331–10431 engineering days**, approximately **317–522 person-months**. This includes implementation, infrastructure, QA, security hardening, documentation, release preparation and architecture/technical-debt removal—not UI completion alone.

The lower bound assumes a constrained support matrix and strong use of mature open-source components. The upper bound reflects hostile multi-tenant isolation, an agent/fleet redesign, broad compatibility matrices and reliability/security rework.

### Repository assumptions revalidated

- Project is fixed to Django/React, one server and one Django service (projects/models.py:16-41).
- One Celery task holds a blocking SSH session without durable lease/reconciliation (deployments/tasks.py:7-20; deployments/services.py:70-127,336-403).
- Only per-project active deployment uniqueness coordinates work (deployments/models.py:74-90).
- SSH host identity uses trust on first use (servers/services.py:94-113; projects/git_services.py:103-127).
- Tenant ownership, application ingress/ACME, managed databases/backups, telemetry and templates are absent or disconnected.

## Estimation assumptions

- Broad Coolify-like group coverage, not identical behavior or UX.
- Production-capable includes recovery, security, tests, documentation and release work.
- One person-month is 20 engineering days; one week is 5 days.
- Django/React code is retained where useful but major domain/orchestration refactoring is allowed.
- Initial targets are Linux and Docker/Compose; Kubernetes/Swarm are excluded.
- Database/provider/template breadth is constrained initially and expands the estimate if widened.
- Mature open-source proxy, ACME, build, telemetry, backup and scanning components are integrated.
- External penetration testing, compliance certification and 24x7 support staffing are excluded.

Discipline columns are additive engineering days. QA covers automation and exploratory validation. Security covers design/review/hardening by the team; independent penetration testing is recommended but not included.

## Feature-group estimates

| ID | Feature group | Coverage | Maturity | Required work | Prerequisites | Backend | Frontend | DevOps | QA | Security | Docs | Total days | Uncertainty | Key risks | Parallelization | Milestone |
|---:|---|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|---|---|---|
| 1 | Architecture refactoring | 10% | prototype foundation | Separate orchestration, execution, resources and releases | None | 90–140 | 15–25 | 20–35 | 25–40 | 20–35 | 10–15 | **180–290** | high | cross-cutting migrations | serial core design; tests parallel | M1 |
| 2 | Generalized application model | 20% | Django/React-specific | Application, Service, Source, Image, Release and strategy models | 1 | 65–105 | 30–50 | 10–15 | 25–40 | 15–25 | 10–15 | **155–250** | high | wrong abstractions force remigration | UI after model contract | M2 |
| 3 | Generic Dockerfile deployment | 25% | incidental via Compose | First-class context, target, args, artifacts and runtime | 1, 2, 9 | 40–65 | 20–35 | 25–40 | 20–35 | 15–25 | 8–12 | **128–212** | medium | unsafe builds | API/UI/security can split | M2 |
| 4 | Docker Compose deployment | 55% | functional but unsafe | Explicit naming, policy, labels, inventory, compatibility and cleanup | 1, 2, 9 | 45–75 | 20–35 | 30–55 | 30–45 | 20–35 | 8–12 | **153–257** | high | host-control surface | policy/runtime/UI split | M2 |
| 5 | Existing Docker image deployment | 15% | incidental | Image digest, registry auth, pull/update and provenance | 1, 2, 9 | 30–50 | 15–25 | 25–40 | 15–25 | 15–25 | 6–10 | **106–175** | medium | mutable tags and credentials | registry and UI split | M2 |
| 6 | Automatic buildpacks | 0% | absent | Integrate Nixpacks/buildpacks with cache and diagnostics | 1, 2, 9, 32 | 35–55 | 15–25 | 35–60 | 25–40 | 15–25 | 8–12 | **133–217** | high | upstream matrix and sandboxing | adapter/UX/tests split | M4 |
| 7 | Git-provider integrations | 20% | generic Git only | Provider apps, discovery, tokens, statuses and lifecycle | 1, 2, 23, 24 | 65–105 | 35–60 | 15–25 | 35–55 | 25–40 | 10–15 | **185–300** | high | API drift and OAuth security | providers parallel behind adapter | M3 |
| 8 | Webhook-based continuous deployment | 0% | absent | Signed ingestion, replay defense, mapping, dedupe and dispatch | 7, 9, 24, 28 | 35–60 | 10–20 | 10–15 | 20–35 | 20–30 | 6–10 | **101–170** | medium | duplicate/replayed events | provider fixtures parallel | M3 |
| 9 | Deployment queue and state machine | 45% | MVP without recovery | Leases, retries, reconciliation, priorities, quotas and stale recovery | 1 | 85–140 | 20–35 | 35–60 | 40–65 | 25–40 | 10–15 | **215–355** | high | distributed failure semantics | state model first | M1 |
| 10 | Real-time build and deployment logs | 10% | step status only | Streaming, cursors, retention, redaction, auth and reconnect | 1, 9, 23, 24 | 45–75 | 30–50 | 35–60 | 30–50 | 20–35 | 8–12 | **168–282** | high | secret leakage and backpressure | transport/storage/UI split | M2 |
| 11 | Health checks | 60% | strict Compose gate | Per-service probes, timing, readiness/liveness and periodic state | 2, 9 | 25–40 | 15–25 | 15–25 | 20–30 | 10–15 | 5–8 | **90–143** | medium | false health results | engine/UI parallel | M1 |
| 12 | Zero-downtime deployment | 0% | absent | Stage release, readiness, atomic traffic switch and drain | 9, 11, 13, 14 | 55–90 | 20–35 | 55–95 | 35–55 | 20–35 | 8–12 | **193–322** | high | proxy/runtime races | runtime/proxy tracks overlap | M2 |
| 13 | Rollbacks | 30% | best-effort rebuild | Immutable rollback, retention, route switch and data-risk policy | 2, 9, 11 | 40–65 | 15–25 | 30–50 | 30–45 | 15–25 | 7–10 | **137–220** | high | irreversible migrations | retention and UX split | M1 |
| 14 | Reverse proxy and routing | 5% | SPA proxy only | Managed proxy controller, atomic reload, WebSockets and discovery | 1, 2, 9 | 45–75 | 25–40 | 60–100 | 35–55 | 25–40 | 10–15 | **200–325** | high | global outage/exposure | controller/lab/UI split | M2 |
| 15 | Domain management | 10% | stored inert field | Domain/route model, uniqueness, ownership and DNS lifecycle | 2, 14, 24 | 35–55 | 25–40 | 20–35 | 20–35 | 15–25 | 8–12 | **123–202** | medium | collision and takeover | DNS and UI parallel | M2 |
| 16 | Automatic SSL | 0% | absent | ACME orders/challenges, renewal, wildcard/custom cert and alerts | 14, 15, 25 | 30–50 | 15–25 | 45–75 | 30–45 | 25–40 | 8–12 | **153–247** | high | renewal outage/key handling | engine/UX/tests split | M2 |
| 17 | Multi-server management | 25% | static assignment | Enrollment, capability, capacity, placement, drain and reconciliation | 1, 2, 9, 18, 23, 24 | 80–130 | 30–50 | 75–130 | 45–75 | 30–50 | 10–15 | **270–450** | high | fleet identity and scheduler | agent/scheduler/UI tracks | M3 |
| 18 | Server monitoring and cleanup | 15% | manual reachability | Heartbeats, resources, capabilities, breakers, GC and alerts | 9, 17, 25, 27 | 40–65 | 20–35 | 50–85 | 30–50 | 15–25 | 8–12 | **163–272** | high | unsafe data cleanup | telemetry/cleanup split | M3 |
| 19 | Persistent storage | 10% | incidental volumes | Storage model, mounts, capacity, ownership, migration and deletion | 2, 4, 9, 17 | 55–90 | 30–50 | 55–95 | 35–60 | 25–40 | 10–15 | **210–350** | high | data loss and locality | model/UI/drivers split | M2 |
| 20 | Managed databases | 0% | absent | DB lifecycle, engines, credentials, networks, upgrades and logs | 2, 9, 17, 19, 23 | 85–140 | 40–65 | 80–135 | 55–90 | 35–60 | 15–25 | **310–515** | high | stateful compatibility matrix | engine adapters parallel | M2 |
| 21 | Database backups and restore | 0% | absent | Scheduled/manual encrypted backup, retention and verified restore | 19, 20, 23, 25, 26, 27 | 55–90 | 30–50 | 65–110 | 55–90 | 35–60 | 15–25 | **255–425** | high | unverified recovery | adapters/scheduler/tests split | M2 |
| 22 | Projects and environments | 35% | implicit environment | Explicit environments, grouping, clone, promotion and movement | 1, 2, 24 | 60–95 | 45–75 | 15–25 | 35–55 | 20–35 | 10–15 | **185–300** | high | data migration semantics | backend/UI overlap | M2 |
| 23 | Shared variables and secret management | 35% | encrypted project values | Scopes, masking, import, history, rotation and KMS/vault | 1, 2, 22, 24, 32 | 55–90 | 35–55 | 35–60 | 35–55 | 40–65 | 10–15 | **210–340** | high | rotation and exposure | vault/API/UI tracks | M2 |
| 24 | Teams and RBAC | 10% | global Admin | Organizations, membership, invitations, policy, scoping and tokens | 1 | 75–120 | 45–75 | 15–25 | 50–80 | 45–75 | 12–18 | **242–393** | high | IDOR and global-resource migration | policy core first | M3 |
| 25 | Notifications | 5% | disconnected models | Outbox, preferences, delivery history/retries and channels | 9, 22, 24 | 35–55 | 25–40 | 15–25 | 25–40 | 15–25 | 8–12 | **123–197** | medium | storms and secret payloads | channels parallel | M3 |
| 26 | Scheduled tasks | 0% | absent | Cron schedules, history/logs, cancellation and concurrency | 9, 10, 22, 24 | 40–65 | 25–40 | 20–35 | 30–45 | 15–25 | 8–12 | **138–222** | medium | duplicate arbitrary execution | engine/UI split | M3 |
| 27 | Monitoring and metrics | 5% | on-demand status | Metrics, uptime, history, alert rules, retention and dashboards | 17, 18, 22, 24, 25 | 45–75 | 35–60 | 70–120 | 45–75 | 20–35 | 10–15 | **225–380** | high | cardinality and storage cost | collector/storage/UI tracks | M3 |
| 28 | Public API | 55% | Admin REST API | Tenant API, versioning, idempotency, limits, tokens and contracts | 2, 9, 22, 24, 32 | 45–75 | 10–20 | 15–25 | 35–55 | 25–40 | 15–25 | **145–240** | medium | compatibility and token scope | governance parallel | M3 |
| 29 | One-click service templates | 0% | absent | Versioned signed catalog, schemas, variables, updates and marketplace | 2, 4, 5, 14, 19, 20, 23, 28, 32 | 55–90 | 45–75 | 25–45 | 40–65 | 25–45 | 15–25 | **205–345** | high | supply chain and upgrades | catalog/templates/UI split | M4 |
| 30 | Platform backup and restore | 0% | absent | Encrypted DB/config/key backup and full restore drills | 23, 26, 32 | 35–55 | 15–25 | 50–85 | 40–65 | 30–50 | 12–18 | **182–298** | high | key loss and false backups | mechanism/lab overlap | M4 |
| 31 | Platform upgrade mechanism | 0% | absent | Versioned releases, preflight, migration, compatibility and rollback | 17, 30, 32, 33 | 45–75 | 20–35 | 60–100 | 45–70 | 25–40 | 15–25 | **210–345** | high | bricked control plane/fleet | tooling/tests split | M4 |
| 32 | Security hardening | 20% | basic app controls | Threat model, isolation, MFA, limits, audit, KMS, scanning | 1, 24 | 65–105 | 25–40 | 50–85 | 50–85 | 75–125 | 15–25 | **280–465** | high | cross-cutting security debt | continuous workstream | M1 |
| 33 | Automated integration testing | 20% | mock-heavy tests | Real DB/queue/Docker/SSH/proxy/ACME/provider labs and faults | 1, 9, 14, 17, 32 | 30–50 | 15–25 | 70–115 | 90–145 | 30–50 | 10–15 | **245–400** | high | flaky privileged CI | early continuous workstream | M1 |
| 34 | End-to-end testing | 5% | no browser suite | Browser deploy/domain/DB/backup/recovery/accessibility flows | 22, 24, 28, 33 | 20–35 | 30–50 | 20–35 | 65–105 | 20–35 | 8–12 | **163–272** | medium | long flaky scenarios | harness early | M2 |
| 35 | Documentation and operational runbooks | 25% | setup/API docs | User/admin/security/incident/upgrade/restore/release documentation | 30, 31, 33 | 10–15 | 5–10 | 20–35 | 20–30 | 15–25 | 80–140 | **150–255** | medium | unvalidated runbooks | continuous documentation | M1 |

### Aggregate by discipline

| Discipline | Days |
|---|---:|
| backend | 1695–2760 |
| frontend | 850–1425 |
| devops | 1270–2155 |
| qa | 1260–2030 |
| security | 840–1400 |
| documentation | 416–661 |
| **Total** | **6331–10431** |

## Team scenarios

| Scenario | Team | Overall calendar range | Critical-path range | Scaling qualification |
|---|---|---:|---:|---|
| A | one full-stack engineer | **352–652 months** | **250–420 months** | Serial work, specialist learning and context switching dominate; severe key-person risk. |
| B | backend/platform + frontend + DevOps/infrastructure | **148–282 months** | **96–160 months** | Effective throughput about 2.0–2.4 FTE after dependencies; QA/security compete with delivery. |
| C | 2 backend/platform + frontend + DevOps + QA/automation | **87–169 months** | **54–90 months** | Effective throughput about 3.4–4.0 FTE; architecture and integration prevent linear scaling. |

These are not person-days divided by headcount. Dependencies, specialization, review, integration and stabilization prevent linear scaling. Scenario A is organizationally unsafe for this blast radius and duration.

## Critical path

### Foundation

Groups 1, 9, 32, 33. This phase must happen first; blocks public production. security/testing parallel with architecture.

### Tenant/resource model

Groups 2, 22, 24, 23. This phase blocks multi-user production. UI can follow stable contracts.

### Release/runtime

Groups 3, 4, 5, 10, 11, 13. This phase blocks general-purpose production. build modes/logs/health split.

### Ingress and stateful data

Groups 12, 14, 15, 16, 19, 20, 21. This phase blocks public general-purpose production. proxy/ACME and data tracks parallel.

### Fleet and operations

Groups 17, 18, 25, 26, 27, 28, 34, 35. This phase blocks broad production operations. agent, observability and API tracks parallel.

### Breadth

Groups 6, 7, 8, 29, 30, 31. This phase defer after narrower production release. providers/buildpacks/catalog parallel.

Critical-path duration is **250–420 months (A)**, **96–160 months (B)** and **54–90 months (C)** after team-capacity constraints are applied. Foundation → tenant/resource model → release runtime → ingress/stateful data → fleet/operations is the blocking sequence. Provider breadth, buildpacks and marketplace scale can be deferred.

## Milestone plans

### Milestone 1: Reliable current scope

**Scope:** Production-capable Django/React deployment on one server with durable state, logs, health, bounded rollback, security, tests and runbooks.

**Excluded:** generic apps, managed ingress/databases, teams and fleet scheduling.

**Prerequisites:** groups 1, 9, 11, 13, 32, 33, 35.

**Effort:** 1150–1850 incremental days; 1150–1850 cumulative days.

**Calendar:** A 64–116 months; B 27–50 months; C 16–30 months.

**Acceptance criteria:**

- no stale deployment after interruption.
- integration-tested deploy/cancel/rollback/recovery.
- retained redacted logs.
- documented recovery.

**Major risks:** orchestration design; data-unsafe rollback; Compose isolation.

### Milestone 2: General-purpose single-server platform

**Scope:** Dockerfile/image/Compose apps, environments, proxy, domains, SSL, storage, databases and verified backups.

**Excluded:** teams, multi-server placement, broad catalog and self-upgrade.

**Prerequisites:** groups 2, 3, 4, 5, 10, 12, 14, 15, 16, 19, 20, 21, 22, 23, 34.

**Effort:** 2800–4300 incremental days; 3950–6150 cumulative days.

**Calendar:** A 220–384 months cumulative; B 92–166 months cumulative; C 55–100 months cumulative.

**Acceptance criteria:**

- three framework-neutral deploy modes.
- automatic route/certificate reconciliation.
- verified database backup/restore.
- owned storage/release lifecycle.

**Major risks:** proxy consistency; stateful recovery; build-mode breadth.

### Milestone 3: Multi-user and multi-server platform

**Scope:** Organizations, RBAC, tenant isolation, fleet placement/drain, notifications, monitoring, schedules and public API.

**Excluded:** large template marketplace, full buildpack/provider breadth and self-upgrade.

**Prerequisites:** groups 7, 8, 17, 18, 24, 25, 26, 27, 28.

**Effort:** 1700–2850 incremental days; 5650–9000 cumulative days.

**Calendar:** A 314–563 months cumulative; B 132–244 months cumulative; C 78–146 months cumulative.

**Acceptance criteria:**

- negative tenant-isolation tests.
- pinned server identity and offline recovery.
- capacity-aware routing.
- metrics/audit/scoped tokens.

**Major risks:** tenant migration; scheduler correctness; telemetry cost.

### Milestone 4: Broad Coolify feature coverage

**Scope:** Buildpacks, provider/webhook breadth, templates, platform backup/restore, safe upgrades and remaining automation.

**Excluded:** low-demand parity may remain intentionally omitted.

**Prerequisites:** groups 6, 29, 30, 31.

**Effort:** 681–1431 incremental days; 6331–10431 cumulative days.

**Calendar:** A 352–652 months cumulative; B 148–282 months cumulative; C 87–169 months cumulative.

**Acceptance criteria:**

- tested support matrix.
- upgrade/rollback from supported versions.
- isolated full restore.
- security/release gates.

**Major risks:** long-tail compatibility; upstream churn; template supply chain.

## Final conclusions

### 1. Total person-month range

**317–522 person-months** (6331–10431 engineering days).

### 2. Calendar-time range

- Scenario A: **352–652 months**.
- Scenario B: **148–282 months**.
- Scenario C: **87–169 months**.

### 3. Earliest realistic production milestone

Milestone 1: **16–30 months (C)**, **27–50 months (B)** or **64–116 months (A)**. It remains a trusted one-server Django/React product. A narrower risk-accepted internal release may be possible sooner, but would not meet this estimate's production-capable acceptance criteria.

### 4. Broad feature coverage

Approximately **87–169 months (C)**, **148–282 months (B)** or **352–652 months (A)**. These ranges demonstrate that the specified teams are undersized for timely parity; use milestone funding, reduce scope, or staff multiple specialist workstreams.

### 5. Five largest uncertainty factors

- Trusted single-owner versus hostile multi-tenant workload model.
- Breadth of database engines, providers, channels, templates and buildpacks.
- SSH hardening versus a new managed-server agent and migration requirements.
- RPO/RTO, HA and compliance targets.
- Supported Docker/Compose/Linux and upgrade compatibility matrix.

### 6. Ten hardest engineering challenges

1. secure build/runtime isolation.
2. durable idempotent orchestration.
3. tenant resource/authorization migration.
4. immutable releases and data-safe rollback.
5. managed-server identity/placement.
6. atomic proxy/domain/certificate control.
7. storage/database backup and upgrade safety.
8. KMS-backed secret/credential lifecycle.
9. scalable redacted telemetry.
10. fault-injected infrastructure test lab.

### 7. Features requiring demonstrated demand

- large community template marketplace.
- every database/cache engine and historic version.
- all notification channels.
- obscure-language buildpacks.
- PR previews for every provider.
- advanced wildcard/path middleware combinations.
- external build farm before measured demand.
- automatic image updates for every resource.

### 8. Prefer open-source integration

| Capability | Recommendation |
|---|---|
| Proxy | Traefik or Caddy; build controller, not proxy |
| ACME | proxy ACME or lego/certbot |
| Builds | BuildKit and Nixpacks/buildpacks |
| Telemetry | OpenTelemetry, Prometheus/VictoriaMetrics and Loki-compatible storage |
| Backups | engine tools plus restic/rclone and S3 |
| Workflows | evaluate Temporal versus hardened Celery state machine |
| Secrets | Vault or KMS envelope encryption |
| Scanning | Trivy/Grype and Syft/SBOM |

### 9. Build versus integrate

Build the product-specific tenant/resource model, authorization, desired-state controllers, workflow semantics, migrations and UX. Integrate mature proxy, ACME, build, telemetry, backup, secrets and scanning components behind versioned adapters. Own reconciliation and safety policy; do not recreate commodity infrastructure.

### 10. Confidence

**Low-to-medium.** Repository evidence strongly supports a multi-year architecture-led program, but Coolify scope moves and the trust model, support matrix, RPO/RTO and compatibility commitments are unspecified. Re-estimate after architecture spikes and each milestone.
