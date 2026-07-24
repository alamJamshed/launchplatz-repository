# Production Readiness and Expansion Challenges

Audit date: 2026-07-23  
Perspective: platform engineering, DevOps/SRE, product security, and software architecture.

This review read the two prior Markdown audits and JSON inventory, then revalidated material claims against the current source. The central conclusion is that LaunchPlatz is not a smaller Coolify architecture awaiting more screens. It is a useful, narrow workflow whose current domain model and execution boundary must be redesigned for a general-purpose, multi-tenant platform.

The strongest reusable pieces are Django/DRF CRUD, PostgreSQL persistence, Celery integration, encrypted credential helpers, SSH connectivity, Git operations, Compose discovery, and deployment history. The current product boundary—one `Project`, one `Server`, one repository branch, one Django service, one mutable remote checkout—does not provide the abstractions or safety boundaries needed for environments, applications, managed services, releases, routing, storage, tenancy, scheduling, or distributed reconciliation.

## 1. Architecture limitations

### Capability assessment

| Capability | Current support and limitation | Repository evidence | Change class |
|---|---|---|---|
| Arbitrary frameworks | Not supported as a product abstraction. `Project.Framework` contains only `DJANGO_REACT`; every deployment executes `python manage.py migrate` and `collectstatic` in `django_service_name`. Compose can technically contain other workloads, but the mandatory Django steps make them unsupported. | `projects/models.py:16-27,39-41`; `deployments/services.py:197-202,358-370` | **Architectural redesign**: introduce pluggable build/deploy strategies and remove framework steps from the core runner. |
| Arbitrary Docker images | Incidental only. User Compose may reference an image, but the pipeline always invokes `docker compose build`; there is no image resource, tag/digest policy, registry credential, pull/update workflow, or provenance. | `deployments/services.py:185-195`; absence of image/registry models and APIs | **Moderate refactoring** for basic image deploys; **major subsystem replacement** for secure registry/provenance/update support. |
| Docker Compose | Functionally supported for repository-provided Compose files. The platform validates the path, runs build/up/restart/ps, and exposes service controls. It does not normalize project naming, validate dangerous directives, own networks/volumes, or handle Compose-version compatibility. | `projects/models.py:34-41`; `projects/validators.py:48-60,86-88`; `deployments/services.py:138-255`; `containers/services.py:135-271` | **Moderate refactoring** for reliable single-tenant use; **major subsystem replacement** for policy-controlled multi-tenancy. |
| Multiple services per project | Runtime discovery supports multiple declared Compose services and health requires all of them. Services are strings, not persisted resources; only one service is designated for Django commands. There is no service-specific domain, environment, scale, storage, or deployment policy. | `deployments/services.py:226-255`; `containers/services.py:135-207`; `projects/models.py:39-41` | **Architectural redesign** of Project/Application/Service/Environment resources. |
| Multiple managed servers | Multiple `Server` rows and project-to-server assignment work. There is no scheduler, capacity model, server-level lock, maintenance/drain state, capability inventory, health loop, or migration between hosts. | `servers/models.py:7-73`; `projects/models.py:20-22`; `servers/api/views.py`; no scheduling models/tasks | **Major subsystem replacement** of server management and placement. |
| Deployment queues | Celery/Redis queues a deployment and stores a task ID. There is one generic worker configuration, no routing, priority, fair scheduling, rate control, retry policy, late acknowledgement, or dead-letter/reconciliation process. | `projects/api/views.py:126-185`; `deployments/tasks.py:7-20`; `Config/celery.py:1-9` | **Major subsystem replacement** of orchestration, while retaining Celery only if its delivery model is made explicit. |
| Concurrent builds | Celery may run jobs concurrently and only one active deployment per project is database-constrained. Projects sharing a server can build simultaneously without server capacity/advisory locks; worker concurrency and build quotas are unconfigured. | `deployments/models.py:74-90`; `compose.yml:51-58`; absence of server/build locks | **Major subsystem replacement**: scheduler, leases, quotas, per-host concurrency and isolated builders. |
| Background workers | Celery worker exists and is appropriate for asynchronous dispatch. Its task is a long blocking SSH session with no retry/recovery semantics or separation between orchestration and execution. | `deployments/tasks.py:7-20`; `docker/entrypoint.staging.py:31-34` | **Moderate refactoring** for worker hardening; **architectural redesign** for distributed, resumable workflows. |
| Long-running deployment operations | Remote commands have a configurable timeout, cancellation polling and remote process-group PID file. A worker remains occupied for the entire build and polls the database every 250 ms. Worker termination loses ownership and recovery. | `deployments/services.py:70-127`; `Config/settings/production.py:47-52` | **Major subsystem replacement** with durable workflow state, leases/heartbeats and target execution handles. |
| Real-time logs | Not supported. Deployment steps store status/timing/error only; command output is read and discarded. Container logs are bounded one-shot HTTP responses, and the UI polls status. | `deployments/models.py:93-122`; `deployments/services.py:103-127,290-315`; `containers/services.py:258-271`; `frontend/src/pages/DeploymentDetailPage.tsx` | **Major subsystem replacement**: log transport, durable/object storage, streaming protocol, redaction and retention. |
| Multi-tenancy | Absent. No Organization, Team, Membership, Environment ownership or tenant key exists; project/server/deployment queries are global. | all domain models; `projects/models.py`; `servers/models.py`; `deployments/models.py` | **Architectural redesign**, required before broad feature work because every resource and query needs ownership. |
| Role-based access | Three coarse permission classes exist, but platform APIs use global `IsAdmin`. There are no object/action grants, member roles, scoped tokens or ownership checks. | `coreapp/permissions.py:5-29`; `projects/api/views.py:51-54`; `servers/api/views.py:32-35`; `deployments/api/views.py:17-22` | **Architectural redesign** alongside tenancy; not a local permission patch. |
| Backups | No platform or managed-application backup domain, scheduler, storage target, encryption, status, retention or restore verification. Named Compose volumes merely persist locally. | `compose.yml:75-79`; `compose.staging.yml:62-64`; repository-wide absence search | **Major new subsystem**; restore and validation are as important as backup creation. |
| Monitoring | Only manual SSH connection tests, deployment-time Compose health and live container status exist. No metrics pipeline, agent/exporter, uptime probes, alert rules, history or capacity data. | `servers/services.py:83-131`; `deployments/services.py:226-255`; `containers/services.py:195-207` | **Major new subsystem** for telemetry collection, retention and alerting. |
| Horizontal expansion | Web replicas are plausible behind an external proxy, but migrations run on web startup and file logs are local. Workers can be multiplied only at the cost of uncontrolled server contention. PostgreSQL/Redis are single instances; there is no leader election, scheduler lease or shared log/artifact store. | `compose.staging.yml:16-64`; `docker/entrypoint.staging.py:18-35`; `Config/settings/production.py:64-99` | **Architectural redesign** for control-plane HA and **major subsystem replacement** for work scheduling. |

### Structural conclusion

The next generalization should not add conditionals such as `if framework == ...` to `DeploymentRunner`. A viable target model needs at least:

1. Organization and membership.
2. Project as a grouping boundary.
3. Environment as a deployable isolation boundary.
4. Application/Service/Database resources inside an environment.
5. Source or Image specification.
6. Immutable Release/Build artifacts.
7. Deployment as a durable transition from one release to another.
8. Server/Cluster plus capabilities, capacity and placement.
9. Route/Domain/Certificate resources.
10. Storage/Backup/Restore resources.

Without these boundaries, most Coolify-level features will create cross-cutting migrations and duplicated special cases.

## 2. Deployment-engine risks

| Concern | Current behavior and risk | Evidence | Required response |
|---|---|---|---|
| Unsafe shell construction | User-controlled paths, branches and service names are mostly validated and passed through `shlex.quote`. This reduces direct injection. The larger risk is intentional execution of repository-controlled Dockerfiles and Compose directives, which can run privileged containers, mount the host and execute arbitrary build scripts. Nested `sh -c` and a command string remain difficult to reason about as new inputs are added. | `projects/validators.py:14-88`; `projects/git_services.py:212-220,240-322`; `deployments/services.py:91-100,138-208` | Keep typed command builders; stop concatenating new user fields. Parse/validate Compose policy and execute builds in an isolated builder/agent boundary. |
| Unbounded subprocesses | Deployment commands are time-bounded, but synchronous Git and container API operations read remote output into memory and use only command timeouts. Repository builds may fork descendants, consume host resources or continue if termination fails. No CPU, memory, disk or output quotas exist. | `projects/git_services.py:157-183`; `containers/services.py:102-134`; `deployments/services.py:79-127` | Enforce cgroup/build quotas, bounded log transport, process ownership and kill verification. |
| Timeout handling | Connection, Git, deploy, health and Docker-action timeouts exist. A timeout is global, not per project/step/server; it does not guarantee the remote process stopped, and timeout recovery is not reconciled. | `Config/settings/production.py:37-57`; `deployments/services.py:91-127` | Step-specific policies, server-side execution IDs, kill/confirm, retry classification and durable timeout events. |
| Cancellation | Cancellation is cooperative and checked every 250 ms while a worker is alive. It writes a remote PID file and sends TERM to a process group. Worker death, network loss, missing `setsid`, PID reuse or a child escaping the group can defeat it. Rollback ignores cancellation. | `deployments/services.py:70-127,257-274,286-315`; `deployments/api/views.py:78-95` | Durable cancellation intent, target agent/executor, fencing token, TERM/KILL escalation and reconciliation. |
| Idempotency | Task code skips records outside pending/cancelling, but there is no atomic task claim. Two deliveries can both observe `PENDING` and run. API creation has a per-project uniqueness constraint but no request idempotency key. Most Compose commands are convergent, while migrations, builds and arbitrary hooks need not be. | `deployments/tasks.py:8-20`; `deployments/models.py:76-82`; `projects/api/views.py:148-181` | Atomic lease/claim, idempotency keys, attempt numbers and step-level idempotency contracts. |
| Concurrency | Only one active deployment per project is blocked. No server, port, domain, volume, network, registry or build concurrency coordination exists. | `deployments/models.py:76-82`; no other locks found | Central scheduler with resource reservations and database-enforced uniqueness for globally exclusive resources. |
| Locking | The partial unique constraint prevents duplicate active rows but is not an execution lock. There is no `select_for_update`, advisory lock, lease expiry, fencing token or distributed lock. | `deployments/models.py:74-90`; repository search found none | Durable leases with expiration/renewal and target-side fencing. |
| Deployment state recovery | `run_deployment` has no retry declaration, heartbeat or finally handler outside `DeploymentRunner`. `DeploymentRunner` catches only `DeploymentPipelineError`; an unexpected exception can leave a row running and a step active. There is no stale deployment sweeper. | `deployments/tasks.py:7-20`; `deployments/services.py:336-403` | Reconciler that scans desired/observed state, task heartbeats, catch/finalize unexpected errors and resume/compensate safely. |
| Partial failure handling | Build/up/migration/static/restart mutate live resources sequentially. Failure after `up` can leave new containers, images, networks, schema changes or `.env`. `_skip_remaining` updates only DB step state. | `deployments/services.py:343-402` | Immutable release staging, explicit compensations, observed-state inventory, and transactional route switching. |
| Stale deployment cleanup | None. A stale active row also permanently trips the unique constraint and prevents a later deployment. Remote PID files are removed only during the live worker’s `finally`. | `deployments/models.py:76-82`; `deployments/services.py:120-124`; no sweeper | Heartbeat/lease expiry, operator recovery action and automated orphan process/resource discovery. |
| Rollback safety | Rollback hard-resets the mutable checkout, rebuilds, starts, collects static, restarts and checks health. It does not reverse migrations, restore `.env`, databases or volumes. It reruns a build rather than deploying an immutable known-good artifact. | `deployments/services.py:257-274,323-335,358-391` | Release artifacts/digests, pre-deploy backups for destructive migrations, migration compatibility policy and verified restore paths. |
| Image/container naming | Compose derives project identity from path/config because commands omit explicit `--project-name` and release ID. Names and tags are repository-defined; two configurations can collide through explicit names, external networks, ports or image tags. | `deployments/services.py:146-148`; `containers/services.py:135-137` | Stable platform-generated Compose project/release names, labels and ownership inventory. Reject unsafe explicit names where isolation is required. |
| Port collisions | Ports are repository-controlled and not reserved or validated centrally. Concurrent projects on one server can attempt the same host port. | no port model; `deployments/services.py:191-195`; container publisher display at `containers/services.py:178-192` | Port allocator/reservation table, preflight checks, or proxy-only internal exposure. |
| Domain collisions | `Project.domain` is not unique and is not applied. No route ownership or transactional proxy configuration exists. | `projects/models.py:30`; `projects/validators.py:35-45`; no proxy consumer | Domain/route model with normalized unique constraints, ownership verification and atomic proxy updates. |
| Volume preservation | Container removal deliberately preserves images/volumes, but the platform does not inventory volumes or bind mounts. Rollback and project/server deletion do not reason about data. | `containers/services.py:249-256`; no volume model | Storage resources with ownership, attachment, backup, retention and explicit destructive workflows. |
| Network lifecycle | Compose implicitly creates/removes networks. The platform neither inventories them nor controls external networks, aliases, cross-project connections or cleanup. | direct Compose execution in `deployments/services.py:185-208`; no network model | Per-environment network policy and labeled lifecycle reconciliation. |
| Proxy consistency | No managed application proxy exists. Adding one naively after `up` would create a second non-transactional state machine: app healthy while route absent, or route live while app failed. | `frontend/nginx.staging.conf:1-16`; `compose.staging.yml:42-60`; no application proxy code | Proxy controller with desired-state config, validation, atomic reload, rollback, certificate state and route health. |

## 3. Multi-server challenges

The schema can store many servers, but safe fleet management requires a control loop rather than more SSH calls.

| Area | Current state | Required capability |
|---|---|---|
| SSH connection management | Each API action or deployment creates a new blocking `paramiko.SSHClient`; no pooling, bastion, proxy jump, connection budget or per-host circuit breaker. | Connection service with bounded pools, deadlines, cancellation, bastion support, concurrency limits and telemetry—or preferably a mutually authenticated target agent. |
| Credentials | One encrypted private key is stored per server; Git keys are stored per project and copied into the server user’s home. | Credential references, vault/KMS integration, per-host/per-project principals, rotation versions, expiry and revocation. |
| Host-key validation | Paramiko uses `AutoAddPolicy`; Git SSH uses `StrictHostKeyChecking=accept-new`. No fingerprint is captured or approved. | Enrollment ceremony with pinned host/agent identity, change alerting and explicit rekey approval. |
| Connectivity checks | Manual authentication check persists status/latency. | Scheduled heartbeat with backoff, reason taxonomy, last-success age, maintenance state and alerting. |
| Capability detection | Deployment checks only Git and Compose availability at use time. | Inventory OS/arch, Docker API/Engine/Compose versions, BuildKit, disk, CPU, memory, filesystem, network, GPU and supported features. |
| Docker version differences | Commands assume the current Compose CLI and JSON output shape. | Version compatibility matrix, semantic capability flags, upgrade policy and integration tests across supported versions. |
| Remote command execution | Shell strings execute as a broad SSH user with Docker authority. | Versioned execution protocol, structured argv/results, streamed logs, execution IDs, resource limits, sandboxing and least privilege. |
| Retries | No task retry policy; blindly retrying migrations/build/up would be unsafe. | Error classification, idempotent operations, bounded exponential backoff and operator-visible retry attempts. |
| Distributed state | Database contains intent/history; the remote host contains checkout, keys, PID files, images, containers, volumes and networks with no inventory linkage. | Desired/observed state model, resource labels, periodic reconciliation and drift reporting. |
| Unavailable servers | A deployment fails at connection time; there is no queue pause, drain, reroute or recovery policy. | Server states (`ready`, `degraded`, `offline`, `maintenance`, `draining`), admission control and resumable failure handling. |
| Deployment routing | Project statically references one server. | Placement constraints, capacity reservations, affinity, data locality, environment pinning and optional migration/failover semantics. |
| Cleanup | Project deletion leaves remote checkout/Git key; container removal leaves volumes/images; no orphan sweeper exists. | Ownership labels, safe garbage collection, retention policy and dry-run/operator approval for data-bearing resources. |
| Server deletion | Server soft-delete is protected indirectly by project FK, but remote credentials/resources are not revoked or removed. | Drain/preflight, resource migration/deletion choice, remote key revocation, secrets deletion and tombstone/audit record. |
| Auditability | Git operations and deployment snapshots are partial evidence; SSH/container actions and secret reads are incomplete. | Append-only audit events including actor, tenant, target, command class, resource, execution/result IDs and redacted metadata. |

For a small trusted fleet, hardened SSH can remain a transport. For a large or multi-tenant fleet, a pull-based agent with mTLS, signed jobs and constrained capabilities is materially safer and easier to reconcile than distributing host-root-equivalent SSH keys to control-plane workers.

## 4. Security challenges

### Risk register

Likelihood and impact are qualitative for an Internet-accessible multi-user deployment platform.

| Risk | Attack scenario | Current evidence | Likelihood | Impact | Recommended control | Complexity | Blocking status |
|---|---|---|---|---|---|---|---|
| Repository-to-host escape | A user commits Compose with `privileged: true`, `/` bind mount, host PID/network or Docker socket; deployment gives repository code host control. | Compose is executed without policy (`deployments/services.py:185-208`). | High | Critical | Isolated builders; Compose admission policy; deny privileged/host mounts/socket/capabilities; dedicated runtime principals/VMs. | Very high | **Blocks untrusted multi-tenancy** |
| Compromised SSH master access | Control-plane compromise decrypts every server key and reaches all managed hosts as Docker-capable users. | Global Fernet keys and server ciphertext (`servers/services.py:30-54`; production env settings). | Medium | Critical | Vault/KMS envelope encryption, short-lived certificates, per-host identity, agent pull model, rotation/revocation. | High | **Blocks production fleet** |
| SSH MITM at enrollment | First connection accepts an attacker’s host key, allowing command redirection or credential exposure. | `AutoAddPolicy` in `servers/services.py:94-95`, `projects/git_services.py:103-105`, `projects/environment_services.py:78-91`. | Medium | Critical | Fingerprint pinning or mTLS agent enrollment; alert on identity changes. | Moderate | **Blocks production fleet** |
| Cross-tenant authorization failure | A future member alters an ID and reads another tenant’s secrets or controls its server because queries are global. | No tenant ownership; global `IsAdmin` only. | High once multi-user | Critical | Tenant-first schema, object-scoped querysets, policy engine, negative authorization tests. | Very high | **Blocks multi-tenancy** |
| Environment-secret disclosure | Any Admin can retrieve plaintext even when `is_secret=True`; XSS/admin compromise exposes all variables. | `EnvironmentVariableSerializer.to_representation` decrypts values (`projects/api/serializers.py`). | High | High | Metadata-only list, explicit audited reveal, secret references, scoped grants, masking/redaction. | Moderate | **Blocks delegated access** |
| Unversioned master-key loss/rotation | Lost keys make credentials undecryptable; leaked keys expose all records; rotation cannot be staged. | Ciphertext has no key version; keys are environment variables. | Medium | Critical | Versioned envelope encryption, key rotation jobs, escrow/recovery runbook and access audit. | High | **Blocks production secrets** |
| Git credential persistence on host | Project Git key remains in `~/.launchplatz/keys`; project deletion does not remove it. Host compromise exposes repository access. | `_prepare_git_credential` and no deletion cleanup (`projects/git_services.py:185-220`; project destroy only deletes DB row). | Medium | High | Short-lived provider tokens/deploy keys, cleanup reconciliation, scoped read-only key, revocation workflow. | Moderate | Production blocker for private repos |
| Shell-injection regression | A new feature inserts an unquoted build command/domain/path into nested `sh -c`; attacker gains SSH-user execution. | Current quoting is careful but command strings/nested shell are pervasive (`deployments/services.py:91-100`). | Medium | Critical | Typed command protocol, centralized allowlisted builders, fuzz/property tests, no arbitrary host shell interpolation. | High | Blocks custom command features |
| Resource-exhaustion denial of service | Repository build fills disk, forks processes, consumes CPU/RAM or emits huge output, taking down other apps. | No quotas/cgroups/capacity checks; Docker build on shared target. | High | High | Dedicated builders, cgroup quotas, disk reservations, time/output limits, cleanup thresholds and admission control. | High | **Blocks shared hosting** |
| Port/network collision or lateral access | A project publishes a sensitive host port or joins another project’s external network. | No port/network resource or policy. | High | High | Proxy-only exposure, port reservation, per-tenant networks, deny external/host networking by default. | High | **Blocks multi-tenancy** |
| Unsafe admin user serializer | Admin user endpoint exposes/accepts `fields='__all__'`, including internal privilege/password fields. | `coreapp/api/admin/serializers.py:4-8`. | Medium | High | Explicit read/write fields, password-specific APIs, privilege-change audit and reauthentication. | Low | Production blocker |
| No rate limiting/brute-force defense | Attacker repeatedly attempts login/refresh or expensive synchronous SSH/container APIs. | No DRF throttling/rate-limit configuration. | High | Medium/High | Per-IP/account/API limits, lockout/backoff, edge WAF and expensive-action quotas. | Moderate | Production blocker |
| Incomplete audit trail | Insider reads secrets or restarts/removes containers without durable audit evidence. | Base actor fields and deployment/Git history only; no audit event model. | Medium | High | Append-only tamper-evident audit log, secret-read events, retention/export and tenant access. | High | Blocks enterprise/delegated access |
| Secret leakage through logs/errors | Future command logging records `.env`, registry tokens or remote output; current redaction is ad hoc. | Git ANSI sanitation is not secret redaction; deployment output currently discarded. | Medium | High | Central redaction pipeline, structured sensitive fields, canary tests and access-controlled log storage. | High | Blocks real-time logs |
| Backup confidentiality/integrity | Backups added without encryption/signing expose databases, SSH keys and app data or permit malicious restore. | No backup system or backup encryption. | Medium | Critical | Client/server-side encryption, KMS keys, checksums/signatures, immutable storage and restore authorization. | High | Blocks backup release |
| CSRF/session edge cases | Refresh/logout use cookies on `AllowAny` endpoints without explicit CSRF token binding; same-site deployment assumptions may change. | `coreapp/api/common/views.py:88-128`; cookies are SameSite=Lax. | Low/Medium | Medium | Explicit CSRF/double-submit on cookie-auth flows; strict origin checks; session threat tests. | Low/Moderate | Before cross-site integrations |
| Dependency/image supply-chain compromise | Unscanned dependencies/base images or mutable `latest` frontend dependencies introduce known vulnerabilities. | No SCA/image scan/CI; frontend manifest uses `latest`. | Medium | High | Lock/pin dependencies, SBOM, SCA, signed images, vulnerability policy and patch SLA. | Moderate | Production blocker |
| Missing MFA/API token controls | Stolen Admin password grants full server/secret authority; no scoped automation tokens exist. | No MFA or API-token model. | Medium | Critical | WebAuthn/TOTP, recovery controls, scoped expiring tokens, revocation and step-up auth. | High | Production blocker |

## 5. Reliability challenges

| Failure | Present outcome | Production requirement |
|---|---|---|
| Control-plane failure | Staging restart policies relaunch containers, but no HA, load balancer healthcheck, leader election or external state reconciliation exists. Local file logs may disappear with a node. | Redundant web instances, health endpoints, external ingress, stateless logs/assets, runbooks and recovery objectives. |
| Database failure | Web/worker operations stop. PostgreSQL is one Compose container with one local named volume and no backup/failover. | Managed/HA PostgreSQL or replicated deployment, PITR, tested backups, connection pooling and documented RPO/RTO. |
| Worker failure | Active deployment may remain `running`; remote command may continue; no acknowledgement/retry/reconciler contract is configured. | Heartbeats, durable leases, idempotent step recovery, orphan termination and stale-state reconciliation. |
| Server disconnection | Current SSH operation raises a categorized failure only if the exception maps cleanly. Remote state after disconnect is unknown. | Execution IDs, reconnect/query status, bounded retry, observed-state refresh and operator recovery. |
| Interrupted deployment | Live checkout, `.env`, images, containers, migration state and routes may be at different revisions. | Immutable releases, transactional traffic switch, compensations and reconciliation. |
| Platform restart during deployment | Worker restart loses in-memory SSH/channel state; the DB row and remote process can remain active. | Startup reconciliation and target-side durable executor/agent with fencing. |
| Reverse-proxy failure | No application proxy is managed; external proxy failure is invisible to the platform. | HA proxy/controller, config validation, atomic reload, route health and rollback. |
| Backup failure | No backup workflow exists, so no status or retry can be observed. | Scheduled/manual jobs with checksums, failure states, alerting, retention and independent monitoring. |
| Restore failure | No restore workflow or test exists. | Regular automated restore drills, isolated validation, schema/version compatibility and clear destructive confirmation. |
| Disk exhaustion | Builds, images, logs, repositories and volumes have no quotas or cleanup controller. One project can affect all workloads on a server. | Disk telemetry/thresholds, reservations, BuildKit/image GC, log rotation, retention and emergency admission stop. |
| Certificate-renewal failure | Certificates are external and not tracked. | ACME account/certificate state, renewal scheduler, challenge routing, expiry alert and safe fallback. |

The system currently records an attempted workflow, not a continuously reconciled desired state. Production reliability requires controllers that can repeatedly answer: “What should exist?”, “What actually exists?”, “Who currently owns the operation?”, and “What safe action converges them?”

## 6. Scaling challenges

### Scaling hosted applications

Compose service scale, replicas, load balancing, autoscaling, resource requests, health-aware routing and multi-host scheduling are absent. Scaling a service manually in Compose would be overwritten or invisible to the platform. Stateful resources cannot move because storage has no first-class identity. Supporting horizontal applications requires service-level desired replica state, proxy discovery, resource placement and storage constraints—not merely more deployment workers.

### Scaling build workloads

Builds run on the destination host and consume the same CPU, memory and disk as production applications. There is no queue partition, per-server concurrency, fair scheduling, cache ownership, remote builder, quota or admission control. Builds should move to isolated BuildKit workers/VMs with artifact/image registry output, digest provenance and controlled cache. This is one of the first architectural splits required.

### Scaling the control plane

Django can scale horizontally, but startup migrations, local rotating logs and the lack of distributed controllers complicate replicas. PostgreSQL and Redis are single-node Compose services. A production control plane needs stateless web pods/containers, migration jobs, shared/object log storage, HA data services, health/readiness endpoints, queue observability, leader-elected controllers and backpressure.

### Scaling managed server count

Every status or operation opens SSH synchronously. At fleet scale, connection storms, slow hosts and credential decryption load can exhaust web/worker capacity. A heartbeat/capability inventory, circuit breakers, sharded controllers, batched reconciliation and agent connections are needed. Server count must not linearly increase request-time SSH work.

### Scaling concurrent users

Today all users with useful access are global Admins. More users increase security exposure and conflict risk. Tenant-scoped query performance, invitations, object permissions, API quotas, optimistic concurrency/version fields, audit retention, session management and notification fan-out must precede broad access.

### Scaling logs and metrics

One-shot SSH log reads and local Django files cannot support high-volume streams. A scalable design needs per-execution cursors, bounded transport, tenant-aware ingestion, object/columnar storage, indexing, retention tiers, redaction, access control, sampling/cardinality budgets and cost controls. Logs and metrics should not transit long-lived Django request workers.

## 7. User-experience challenges

Coolify-like usability is primarily automation of unsafe infrastructure decisions. The current UI exposes low-level prerequisites but does not convert them into validated outcomes.

| User task | Complexity currently left to the user | Required product behavior |
|---|---|---|
| Deployment configuration | Repository must contain compatible Compose, every service must have a healthcheck, one service must run Django management commands, target prerequisites must exist, and clone is a separate action. | Framework/image/Compose modes, preflight validation, generated defaults, compatibility diagnostics and a single guided deploy flow. |
| Domains | Domain is stored but has no effect. User must configure DNS, proxy and TLS elsewhere. | Domain availability/ownership checks, DNS guidance/API integration, route generation, ACME, conflict detection and visible certificate state. |
| Ports | Compose publishes arbitrary ports; user must avoid host collisions and firewall exposure. | Internal-by-default networking, declared service port selection, proxy routing, reservation and collision diagnostics. |
| Environment variables | Values are managed one at a time and secret values are returned plaintext to Admin; no environment scoping, imports, references or rotation. | Bulk dotenv import, validation, masking/reveal, secret references, shared scopes, diff/history and redeploy impact preview. |
| Repository credentials | User generates/pastes keys, manually installs server public keys, and manages Git provider deploy keys outside the platform. | Provider OAuth/App integration, guided deploy-key install, connection test, least-privilege scope, expiry and revocation. |
| Databases | User must author/database services, credentials, volumes, backups and connection strings in Compose. | Managed DB creation, version/size/storage options, generated credentials/URLs, internal networking, lifecycle and backups. |
| Persistent storage | User authors volumes/bind mounts and owns permissions/backups. | First-class storage attachments, mount validation, UID/GID guidance, capacity, backup/restore and deletion safeguards. |
| Build errors | Only a generic step category/message is retained; command output is not available. | Streaming structured logs, phase markers, searchable retained output, likely-cause hints and retry-from-safe-point. |
| Deployment errors | Failure may trigger an incomplete rollback; current status does not explain remote residual state or database risk. | Clear failed phase, observed resource state, rollback scope, data-risk warning and guided recovery actions. |
| Recovery actions | No reconcile, unlock stale deployment, restore backup, revert release, drain server, repair proxy or certificate-renew action exists. | Safe, idempotent operator actions with previews, confirmations, audit events and progress. |

## 8. Testing challenges

A production-grade test system should use layers rather than relying on mocked Paramiko calls.

| Test infrastructure | Required coverage |
|---|---|
| Disposable VM-based tests | Provision clean supported OS images; enroll host identity; install/validate Docker; deploy, reboot, disconnect and destroy; verify cleanup and no leaked credentials. Use ephemeral cloud VMs or nested virtualization in a gated suite. |
| Docker integration tests | Real BuildKit/Compose builds across supported Engine/Compose versions; multi-service health, images, labels, networks, ports, volumes, quotas, privileged-policy rejection and cleanup. |
| Reverse-proxy tests | Route creation/update/removal, duplicate domains, path routing, WebSockets, large uploads, proxy reload failure, backend transitions and rollback with real Traefik/Caddy/Nginx candidate. |
| Certificate tests | Local ACME test server (for example Pebble), HTTP/DNS challenges, wildcard flows, renewal, expiry warnings, account-key rotation and failed-challenge recovery. |
| Git-provider tests | GitHub/GitLab/Bitbucket/generic Git test repositories, Apps/OAuth/deploy keys, webhook signatures/replay, branch/tag/SHA, rate limits, revoked credentials and status callbacks. |
| Deployment interruption tests | Kill worker/control plane, sever SSH/network, reboot target and kill remote process at every pipeline boundary; assert eventual terminal state and resource convergence. |
| Rollback tests | Known-good immutable release rollback, failed build/up/health, migration compatibility/incompatibility, route rollback and assertions over data, volumes and environment. |
| Backup/restore tests | Scheduled/manual DB and volume backups, corruption, partial upload, encryption/key failure, retention, point-in-time restore and automated isolated restore verification. |
| Multi-server tests | Capacity routing, server drain/offline state, concurrent builds, server-level locks, cross-server migration, capability differences and fleet reconciliation. |
| Security tests | Hostile Compose/Dockerfiles, shell/metacharacter property tests, authorization matrix/IDOR, secret redaction, SSRF, rate limits, host-key replacement, dependency/SBOM/image scanning and container escape policy. |
| Browser end-to-end tests | Tenant/user onboarding, repository connection, environment creation, deploy/logs/domain/certificate, failure recovery, storage/database/backup flows and accessibility. |
| Control-plane integration | Real PostgreSQL, Redis and Celery delivery semantics, duplicate task delivery, transaction races, migration job, HA restart, queue backpressure and stale lease recovery. |
| Performance/soak tests | Many servers/users, long log streams, high-cardinality metrics, concurrent builds, large histories, slow/unavailable hosts and disk pressure. |

Test environments themselves require strict isolation and budget controls because hostile-build tests intentionally exercise host-escape and resource-exhaustion cases.

## 9. Challenge ranking

| Rank | Challenge | Reason | Prerequisite work | Affected features | Estimated uncertainty | Likely specialist needed | Severity |
|---:|---|---|---|---|---|---|---|
| 1 | Secure workload/build isolation | Current repository Compose executes with Docker authority; this is incompatible with untrusted tenants and shared hosts. | Threat model, trust tiers, builder/runtime boundary, admission policy | Arbitrary frameworks/images, Compose, builds, multi-tenancy | High | Container security/platform security engineer | **Critical** |
| 2 | Tenant-first resource and authorization model | Ownership cannot be added safely at the edges; it changes every model, query, API, secret and audit event. | Organization/membership design, migration plan, authorization matrix | Teams, environments, RBAC, tokens, quotas, audit | Medium | Software architect + application security engineer | **Critical** |
| 3 | Durable deployment orchestration and reconciliation | Worker death/network loss can strand DB and remote state; general workflows need leases, retries and compensation. | Desired/observed state, execution IDs, idempotency and lease design | Queue, cancellation, retries, history, recovery | High | Distributed-systems/platform engineer | **Critical** |
| 4 | Immutable release/build architecture | Mutable checkout plus rebuild rollback is non-reproducible and unsafe around migrations. | Release/artifact/image registry model, digest provenance | Deploy, rollback, zero downtime, previews, image deploy | High | Platform/build systems engineer | **Critical** |
| 5 | Managed server agent, identity and fleet control | Direct TOFU SSH with global decryptable keys does not scale safely or reconcile state. | Enrollment/PKI decision, capability protocol, upgrade channel | Multi-server, monitoring, cleanup, remote execution | High | Systems/security engineer | **Critical** |
| 6 | Service/environment/domain model redesign | One Project currently conflates repo, environment, target and application; most Coolify features need separate resources. | Canonical domain model and migration compatibility | Multiple environments/services/domains/databases/storage | Medium | Software/domain architect | **Critical** |
| 7 | Routing, proxy and certificate control plane | A deployment is not user-available without consistent ingress; domain state is currently inert. | Route/domain uniqueness, proxy choice, ACME state machine | Domains, TLS, ports, WebSockets, load balancing | Medium | Networking/DevOps engineer | **High** |
| 8 | Secrets and credential lifecycle | Fernet-at-rest helps, but global unversioned keys, plaintext reveals and persistent SSH/Git keys lack production lifecycle. | Vault/KMS design, secret reference model, rotation/revocation | SSH, Git, env, registry, DB, backups | Medium | Security/KMS engineer | **High** |
| 9 | Persistent storage, database and backup/restore lifecycle | Stateful workloads cannot be safely operated, moved or recovered without these first-class resources. | Storage ownership model, backup target/encryption, restore semantics | Volumes, managed DBs, migration, disaster recovery | High | Database/SRE/storage engineer | **Critical** |
| 10 | Capacity-aware scheduling and build isolation | Builds contend with production apps; no host reservations or concurrency controls exist. | Server metrics/capabilities, quota model, external builders | Concurrent builds, many servers, performance, cost | High | Scheduler/build infrastructure engineer | **High** |
| 11 | Logs, metrics, monitoring and alerting pipeline | Operators cannot diagnose builds or detect disk/cert/server failures; current local/polled data cannot scale. | Telemetry schema, ingestion/storage/retention and redaction | Logs, metrics, uptime, notifications, SLOs | Medium | Observability/SRE engineer | **High** |
| 12 | Failure-safe schema/data migration strategy | Application migrations run on the live service and rollback cannot undo them; platform migrations run on web startup. | Compatibility policy, migration hooks, backup gates, dedicated migration job | Deploy/rollback/upgrades/restore | High | Database reliability engineer | **Critical** |
| 13 | Resource collision and lifecycle control | Ports, domains, names, networks, images and volumes have no centralized ownership or garbage collection. | Resource IDs/labels, uniqueness/reservation and reconciler | Networking, cleanup, multi-service, server deletion | Medium | Platform runtime engineer | **High** |
| 14 | Production control-plane HA and operations | Single PostgreSQL/Redis, local logs, no health/recovery/upgrade pipeline prevent reliable self-hosting. | RPO/RTO, HA topology, backups, migration/release process | Installation, upgrades, availability, scaling | Medium | SRE/DevOps engineer | **High** |
| 15 | Real integration, interruption and security test infrastructure | Mock-heavy tests cannot establish correctness of Docker/SSH/proxy/ACME/restore/distributed failure behavior. | Disposable VM lab, CI isolation, fixtures and fault injection | All production features and release confidence | Medium | Test infrastructure/SRE/security engineer | **High** |

### Overall readiness judgment

For a restricted, trusted-operator use case, the current code can be hardened incrementally. For a Coolify-comparable platform accepting multiple users and arbitrary repositories, challenges 1–6 are architectural prerequisites, not backlog features. Work on templates, additional databases, notifications, schedules or provider integrations before establishing those foundations will likely be discarded or migrated twice.

