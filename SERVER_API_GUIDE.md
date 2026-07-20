# LaunchPlatz API Reference

This document describes the version 1 REST API implemented by this project.

## URLs

| Resource | Local URL |
|---|---|
| API base | `http://127.0.0.1:8000/api/v1/` |
| Swagger UI | `http://127.0.0.1:8000/api/docs/` |
| OpenAPI schema | `http://127.0.0.1:8000/api/schema/` |

Requests and responses use JSON unless noted otherwise. All endpoint paths below are
relative to `/api/v1/`.

## Authentication

Only active users with the Admin role (`role: 1`) can log in or use protected
endpoints.

The API uses two JWTs:

- The access token is returned in JSON and expires after 60 minutes.
- The refresh token is stored in the `refresh_token` HttpOnly cookie and expires
  after 7 days. It is never returned in JSON.

Send the access token on protected requests:

```http
Authorization: Bearer <access-token>
```

Browser clients must include credentials on login, refresh, and logout requests so
that the refresh cookie is accepted and sent. For example, use
`credentials: "include"` with `fetch` or `withCredentials: true` with Axios.

The refresh cookie uses `SameSite=Lax`, is restricted to `/api/v1/auth/`, and is
marked `Secure` when Django is running with `DEBUG=False`.

## Response Format

Successful non-paginated response:

```json
{
  "success": true,
  "message": "Success",
  "data": {},
  "status_code": 200
}
```

Validation or error response:

```json
{
  "success": false,
  "message": "Validation failed",
  "errors": {
    "field_name": ["Error details."]
  },
  "status_code": 400
}
```

List endpoints backed by the standard paginator use limit/offset pagination with a
default page size of 30:

```http
GET /api/v1/servers/?limit=10&offset=20
```

```json
{
  "success": true,
  "message": "Data retrieved successfully",
  "data": {
    "count": 42,
    "next": "http://127.0.0.1:8000/api/v1/servers/?limit=10&offset=30",
    "previous": "http://127.0.0.1:8000/api/v1/servers/?limit=10&offset=10",
    "results": []
  },
  "status_code": 200
}
```

Common HTTP statuses are `200` (success), `201` (created), `400` (validation
failure), `401` (missing or invalid authentication), `403` (authenticated but not
an Admin), and `404` (resource not found).

## Authentication Endpoints

### Log in

```http
POST /api/v1/auth/login/
Content-Type: application/json
```

```json
{
  "email": "admin@example.com",
  "password": "StrongPassword123!"
}
```

Successful response data:

```json
{
  "access": "<access-token>",
  "user": {
    "id": 1,
    "first_name": "Launch",
    "last_name": "Admin",
    "email": "admin@example.com",
    "phone": "",
    "role": 1,
    "is_verified": true,
    "is_approved": true,
    "is_active": true
  }
}
```

The response also sets the refresh-token cookie. Invalid credentials, inactive
accounts, and non-Admin accounts return `400`.

### Refresh access token

```http
POST /api/v1/auth/refresh/
Cookie: refresh_token=<refresh-token>
```

No request body is required. The response data contains a new `access` token. The
old refresh token is blacklisted and a new refresh cookie is set. A missing,
malformed, expired, blacklisted, inactive-user, or non-Admin token returns `401`
and clears the cookie.

### Log out

```http
POST /api/v1/auth/logout/
Cookie: refresh_token=<refresh-token>
```

No request body is required. The refresh token is blacklisted when present and the
cookie is cleared. The endpoint is idempotent and returns `200` even when there is
no valid cookie.

### Get current profile

```http
GET /api/v1/auth/profile/
Authorization: Bearer <access-token>
```

Returns the authenticated Admin's `id`, name, email, phone, role, verification,
approval, and active-state fields.

## Location Endpoints

All location endpoints require an Admin access token and return only active
records. These lists are not paginated.

### List countries

```http
GET /api/v1/auth/common/countries/
```

Each result contains `id`, `name`, `code`, and `phone_code`.

### List states in a country

```http
GET /api/v1/auth/common/states/{country_id}/
```

Each result contains `id`, `name`, `code`, and `country`. An unknown country ID
produces an empty list rather than `404`.

### List cities in a state

```http
GET /api/v1/auth/common/cities/{state_id}/
```

Each result contains `id`, `name`, `postal_code`, and `state`. An unknown state ID
produces an empty list rather than `404`.

## User Management

The Admin user viewset is available at `/api/v1/auth/users/` and requires an Admin
access token.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `auth/users/` | List users (paginated) |
| `POST` | `auth/users/` | Create a user |
| `GET` | `auth/users/{id}/` | Retrieve a user |
| `PUT` | `auth/users/{id}/` | Replace a user |
| `PATCH` | `auth/users/{id}/` | Partially update a user |
| `DELETE` | `auth/users/{id}/` | Permanently delete a user |

This viewset currently exposes all model fields through its serializer, including
permission and password-related fields. Treat it as an internal administrative
API. Confirm its generated schema in Swagger before integrating a client, and do
not submit a plain-text password until the endpoint uses explicit password hashing.

## Server Management

All server endpoints require an Admin access token. Only active, non-deleted
servers are visible.

### Server object

| Field | Type | Access | Description |
|---|---|---|---|
| `id` | integer | Read only | Server identifier |
| `name` | string | Read/write | Display name, maximum 150 characters |
| `ip_address` | string | Read/write | IPv4 or IPv6 address; hostnames are rejected |
| `ssh_port` | integer | Read/write | SSH port from 1 through 65535; defaults to 22 |
| `username` | string | Read/write | Remote SSH username, maximum 100 characters |
| `private_key` | string | Write only | RSA, ECDSA, or Ed25519 private key |
| `status` | string | Read only | Latest SSH result: `Unknown`, `Online`, or `Offline` |
| `last_checked_at` | datetime/null | Read only | Time of the latest SSH test |
| `last_latency_ms` | number/null | Read only | Latency from the latest successful SSH test |
| `last_failure_reason` | string | Read only | Sanitized reason from the latest failed SSH test |
| `created_at` | datetime | Read only | Creation timestamp |
| `updated_at` | datetime | Read only | Last-update timestamp |
| `created_by` | integer/null | Read only | Creator user ID |
| `updated_by` | integer/null | Read only | Last updater user ID |

The private key is required on creation. Password-protected keys are not supported.
It is encrypted with `SERVER_CREDENTIAL_ENCRYPTION_KEY` before storage. Neither the
plain-text key nor its encrypted value is returned by the API.

The combination of `ip_address`, `ssh_port`, and `username` must be unique among
non-deleted servers.

### List servers

```http
GET /api/v1/servers/
```

Returns a paginated list ordered from newest to oldest.

### Create server

```http
POST /api/v1/servers/
Content-Type: application/json
```

```json
{
  "name": "Production VPS",
  "ip_address": "192.0.2.10",
  "ssh_port": 22,
  "username": "deploy",
  "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----\n"
}
```

Returns `201` with the saved server object, excluding the key.

### Retrieve server

```http
GET /api/v1/servers/{id}/
```

Returns `404` when the server does not exist, is inactive, or was soft-deleted.

### Update server

```http
PATCH /api/v1/servers/{id}/
Content-Type: application/json
```

```json
{
  "name": "Production Web VPS",
  "ssh_port": 2222
}
```

`PATCH` accepts only fields that need to change. Omitting `private_key` preserves
the existing key; including it replaces and re-encrypts the key. `PUT` is also
available for a full replacement.

### Delete server

```http
DELETE /api/v1/servers/{id}/
```

This is a soft delete. It sets `is_deleted=true` and `is_active=false`, retains the
database record for history, and hides it from all server API operations. The
endpoint returns `200` with `data: null`.

### Test SSH connection

```http
POST /api/v1/servers/{id}/test-connection/
```

No request body is required. The API decrypts and parses the stored key, attempts
SSH authentication, and closes the connection without executing a remote command.
The timeout is controlled by `SSH_CONNECTION_TIMEOUT` and defaults to 30 seconds.
The result is saved as the server's latest known SSH status.

Online response data:

```json
{
  "status": "Online",
  "latency_ms": 125.4,
  "checked_at": "2026-07-17T11:05:37.600Z"
}
```

Offline response data:

```json
{
  "status": "Offline",
  "reason": "authentication_failed",
  "checked_at": "2026-07-17T11:05:37.600Z"
}
```

| Offline reason | Meaning |
|---|---|
| `authentication_failed` | The username or private key was rejected |
| `timeout` | The connection or authentication timed out |
| `host_unreachable` | The IP address or port could not be reached |
| `credential_error` | The stored credential could not be decrypted or parsed |
| `ssh_error` | Another SSH protocol error occurred |

New servers start with `status: Unknown`. `Online` means the latest SSH
authentication succeeded; it does not confirm that deployed applications or
Docker containers are healthy.

An offline result returns HTTP `200`: the API operation succeeded and its result is
that the remote server is offline.

## Project Management

All project endpoints require an Admin access token. Every project belongs to an
active, non-deleted server and represents the supported `Django + React` framework.

### Project object

| Field | Access | Description |
|---|---|---|
| `server` | Read/write | Active Server ID used as the deployment target |
| `name` | Read/write | Globally unique project name |
| `framework` | Read only | Fixed value `django_react` |
| `framework_display` | Read only | Display value `Django + React` |
| `git_repository_url` | Read/write | HTTPS, `ssh://`, or `git@host:path` repository URL |
| `branch` | Read/write | Git branch; defaults to `main` |
| `domain` | Read/write | Optional lowercase domain without scheme, port, or path |
| `docker_compose_path` | Read/write | Safe relative path; defaults to `docker-compose.yml` |
| `is_archived` | Read only | Whether the project is archived |
| `archived_at` | Read only | Archive timestamp |
| `archived_by` | Read only | Admin who archived the project |

Environment variables are managed through the dedicated encrypted endpoints below;
they are not included in ordinary Project responses.

### List projects

```http
GET /api/v1/projects/
```

The default list excludes archived projects. Use `?archived=true` for archived
projects or `?archived=all` for both states.

### Create project

```http
POST /api/v1/projects/
Content-Type: application/json
```

```json
{
  "server": 1,
  "name": "LaunchPlatz",
  "git_repository_url": "https://github.com/example/launchplatz.git",
  "branch": "main",
  "domain": "launchplatz.example.com",
  "docker_compose_path": "docker-compose.yml"
}
```

Git validation checks URL syntax only; it does not contact or clone the repository.

### Retrieve and update project

```http
GET /api/v1/projects/{id}/
PATCH /api/v1/projects/{id}/
PUT /api/v1/projects/{id}/
```

`PATCH` changes only supplied fields. A project may be reassigned to another
active server.

### Archive and restore project

```http
POST /api/v1/projects/{id}/archive/
POST /api/v1/projects/{id}/restore/
```

Both actions are idempotent. Archived projects remain retrievable and restorable.

### Delete project

```http
DELETE /api/v1/projects/{id}/
```

Permanently removes the project. This differs from Server DELETE, which is a soft
delete.

## Git Integration

Git operations run synchronously on the Project's VPS and require an Admin access
token. The VPS must have Git installed. Repositories are stored at:

```text
~/launchplatz/projects/{project_id}
```

Project responses include the read-only cached fields `git_cloned_at`,
`current_branch`, `current_commit`, and `last_git_synced_at`.

### Git credential

For an SSH repository URL, add `git_private_key` when creating or patching the
Project. It is write-only and encrypted in PostgreSQL with
`GIT_CREDENTIAL_ENCRYPTION_KEY`.

The key is installed on the VPS at `~/.launchplatz/keys/project-{id}` with file
mode `600`; the containing directory uses mode `700`. Public HTTPS repositories
do not require a Git key.

### Clone

```http
POST /api/v1/projects/{id}/git/clone/
```

Clones only the selected Project branch. Returns `409` if the remote workspace
already exists. A successful clone caches the branch, commit, clone time, and sync
time.

### Pull latest code

```http
POST /api/v1/projects/{id}/git/pull/
```

Uses `git pull --ff-only`. It returns `409` without changing files when the working
tree is dirty, the repository is not cloned, or a fast-forward is impossible.

### Current commit

```http
GET /api/v1/projects/{id}/git/current-commit/
```

Returns the live branch and full commit hash from the VPS and refreshes the cached
Project Git state.

### List branches

```http
GET /api/v1/projects/{id}/git/branches/
```

Returns sorted remote branch names from `origin`.

### Select branch

```http
POST /api/v1/projects/{id}/git/select-branch/
Content-Type: application/json
```

```json
{
  "branch": "develop"
}
```

Fetches and checks out the remote branch only when the working tree is clean, then
updates the Project branch and cached commit.

After a repository has been cloned, the ordinary Project PATCH endpoint cannot
change `branch`; use this Select Branch endpoint so the database and VPS working
tree remain consistent.

### Operation history

```http
GET /api/v1/projects/{id}/git/operations/
```

Returns paginated clone, pull, commit, branch-list, and branch-selection attempts
with status, sanitized output, error category, commit, duration, timestamps, and
initiating Admin. Stored output is limited to 20,000 characters and never includes
private-key contents.

Mutating Git operations are blocked while a Project is archived. Git commands use
`GIT_OPERATION_TIMEOUT`, defaulting to 120 seconds. Project deletion does not
remove the remote workspace or installed Git key.

## Environment Variables

All endpoints require an Admin access token. Values are individually encrypted in
PostgreSQL using `ENVIRONMENT_VARIABLE_ENCRYPTION_KEY`. They are returned decrypted
only by these dedicated endpoints, whose responses include `Cache-Control: no-store`.

Keys must use uppercase letters, digits, and underscores and cannot begin with a
digit. Every value must be a string; empty and multiline strings are supported.
`is_secret` defaults to `false` and is descriptive metadata—every value is encrypted.

### List and add variables

```http
GET /api/v1/projects/{id}/environment-variables/
POST /api/v1/projects/{id}/environment-variables/
Content-Type: application/json
```

```json
{
  "key": "DATABASE_URL",
  "value": "postgres://user:password@db/app",
  "is_secret": true
}
```

Keys are unique within a project. Values and encryption ciphertext are never
included in ordinary Project responses.

### Retrieve, update, and delete a variable

```http
GET /api/v1/projects/{id}/environment-variables/{variable_id}/
PATCH /api/v1/projects/{id}/environment-variables/{variable_id}/
DELETE /api/v1/projects/{id}/environment-variables/{variable_id}/
```

`PATCH` preserves any field that is omitted. DELETE permanently removes the
individual variable.

### Generate the remote `.env` file

```http
POST /api/v1/projects/{id}/environment-variables/generate-env/
```

The repository must already be cloned. LaunchPlatz uploads a temporary file over
SFTP, applies mode `600`, and atomically replaces
`~/launchplatz/projects/{id}/.env`. The response contains only `variable_count` and
`generated_at`, never file contents. Existing `.env` files are replaced without a
backup.

Archived projects permit variable reads but block create, update, delete, and
generation with HTTP `409`.

## Deployment Pipeline

Deployments require an Admin token, an active VPS, and a repository previously
cloned through Module 4. Redis and a running Celery worker execute deployments in
the background. Only one deployment may be active for a project at a time.

Set `django_service_name` on the Project when the Django Compose service is not
named `backend`.

### Deploy and redeploy

```http
POST /api/v1/projects/{id}/deploy/
POST /api/v1/projects/{id}/redeploy/
```

Both return HTTP `202` with a Deployment ID. They run the same pipeline and retain
different trigger labels for auditing. The pipeline pulls with `--ff-only`, writes
`.env`, builds and starts Compose services, runs migrations and collectstatic,
restarts services, and waits for Docker healthchecks.

Every Compose service must define a healthcheck and become healthy within
`DEPLOYMENT_HEALTH_TIMEOUT` (120 seconds by default).

### View progress

```http
GET /api/v1/projects/{id}/deployment-status/
GET /api/v1/deployments/{deployment_id}/progress/
```

Progress contains ordered step statuses, timestamps, durations, and sanitized
failure categories/messages. Raw command output and secrets are not stored or
returned.

### Cancel

```http
POST /api/v1/deployments/{deployment_id}/cancel/
```

Cancellation is idempotent. The worker terminates the current isolated remote
command, skips remaining steps, and attempts code/container rollback when the Git
commit changed. Rollback never reverses Django migrations, so database changes may
remain. Rollback outcome is recorded separately from `failed` or `cancelled`.

Projects with deployment history cannot be permanently deleted.

## Deployment History

Deployment history is immutable and Admin-only. It is read from PostgreSQL and
does not contact Redis, Celery, Docker, or the VPS.

### List deployment history

```http
GET /api/v1/deployments/
GET /api/v1/deployments/?project=2&status=success&ordering=newest
```

The list is paginated and compact: it includes status, duration, commits, rollback
and failure summaries, triggering Admin, timestamps, and audit snapshots without
embedding all step records. Supported filters are `project`, `status`, and
`ordering=newest|oldest`.

### Deployment details

```http
GET /api/v1/deployments/{deployment_id}/
GET /api/v1/deployments/{deployment_id}/progress/
```

Both endpoints return the same detailed record, including all ordered deployment
steps. The progress route remains available for compatibility.

New deployments snapshot the project name, server name/IP, branch, repository URL,
and triggering Admin email. Later edits do not rewrite these values. Deployments
created before Module 8 have blank snapshot fields.

Cancellation records the first requesting Admin and an immutable email snapshot.
Repeated cancellation does not overwrite that identity. Celery task IDs and raw
command output are never exposed.

History cannot be deleted, and Module 8 does not provide deployment retry. Retry
is deferred to the generic background-job module.

## Docker Management

Docker endpoints require an Admin token and manage only services declared by the
selected Project's Docker Compose file. They never expose unrelated VPS containers.
Each request reads live state over SSH; the database does not cache container state.

### List and inspect containers

```http
GET /api/v1/projects/{id}/containers/
GET /api/v1/projects/{id}/containers/{service}/
```

Responses include the Compose service, container ID/name, image, state, health,
exit code, creation value, and published ports. A declared service whose container
was removed remains visible with state `not_created`.

The frontend can poll the list or detail endpoint to refresh status. LaunchPlatz
does not run a background container-status poller.

### Start, stop, and restart

```http
POST /api/v1/projects/{id}/containers/{service}/start/
POST /api/v1/projects/{id}/containers/{service}/stop/
POST /api/v1/projects/{id}/containers/{service}/restart/
```

Start and stop are idempotent for an existing running or stopped container. Start
and restart return `409` when the service container was removed; run a deployment
to recreate it.

### Remove a container

```http
DELETE /api/v1/projects/{id}/containers/{service}/
```

Force-stops and removes only that service container. Images, volumes, project files,
and other service containers are preserved. Repeated removal is safe.

### Recent logs

```http
GET /api/v1/projects/{id}/containers/{service}/logs/?tail=200
```

Returns timestamped raw Docker log lines. `tail` defaults to 200 and cannot exceed
`DOCKER_LOG_MAX_LINES` (1,000 by default). Responses use `Cache-Control: no-store`.
Applications must not print credentials because Module 7 intentionally does not
redact raw Admin-visible logs.

Archived projects and projects with an active deployment permit status and log
reads but reject start, stop, restart, and removal with HTTP `409`.

## cURL Examples

Log in and store the refresh cookie:

```bash
curl -i -c cookies.txt \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@example.com","password":"StrongPassword123!"}' \
  http://127.0.0.1:8000/api/v1/auth/login/
```

Use the returned access token:

```bash
curl -H "Authorization: Bearer <access-token>" \
  http://127.0.0.1:8000/api/v1/servers/
```

Refresh it using the cookie jar:

```bash
curl -b cookies.txt -c cookies.txt -X POST \
  http://127.0.0.1:8000/api/v1/auth/refresh/
```

## Security Notes

- Keep all encryption keys, including `ENVIRONMENT_VARIABLE_ENCRYPTION_KEY`, out
  of source control.
- Use HTTPS in production; the refresh cookie is Secure outside debug mode.
- The SSH tester currently accepts an unknown SSH host key automatically. Add
  known-host or fingerprint verification before use on an untrusted network.
- Restrict access to Swagger and the OpenAPI schema if the deployment should not
  expose its API surface publicly.
