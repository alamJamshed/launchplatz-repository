# LaunchPlatz Demo Deployment Quick Guide

This guide deploys the public demo repository to a VPS through LaunchPlatz:

```text
https://github.com/alamJamshed/launchplatz-deployment-demo.git
```

There are two separate Docker Compose stacks:

- The root `compose.yml` runs the LaunchPlatz API, PostgreSQL, Redis, and Celery
  on your development computer.
- The demo repository's `docker-compose.yml` is cloned and run by LaunchPlatz on
  the selected VPS.

Do not run commands intended for the VPS inside the LaunchPlatz containers.

## Project Requirements for LaunchPlatz Deployment

This section describes the application being deployed through LaunchPlatz. It
does not describe how to install or run LaunchPlatz itself.

### Repository requirements

The application must:

- Be stored in a Git repository that the VPS can reach through public HTTPS or
  through an SSH URL with a Git private key added to LaunchPlatz.
- Have the selected branch available on the remote repository.
- Contain a Docker Compose file at the relative path configured on the
  LaunchPlatz Project. The recommended path is `docker-compose.yml` at the
  repository root.
- Keep the deployed branch compatible with fast-forward-only pulls. LaunchPlatz
  rejects dirty, diverged, or manually modified remote workspaces.
- Keep production credentials and private keys out of Git.

LaunchPlatz clones the repository into
`~/launchplatz/projects/{project_id}` on the selected VPS.

### Django service requirements

The Compose application must contain a Django service. Its Compose service name
is stored in the Project's `django_service_name` field and defaults to
`backend`.

Inside that service:

- `manage.py` must be available in the container's working directory.
- Python must be callable as `python`.
- Both of these non-interactive commands must succeed:

```bash
python manage.py migrate --noinput
python manage.py collectstatic --noinput
```

The Django service must start before these commands are executed. Database and
other service dependencies therefore need appropriate Compose dependencies and
startup behavior.

### Docker Compose requirements

The Compose application must:

- Build and run on the target Linux VPS and its CPU architecture.
- Start through `docker compose up -d` without interactive input.
- Define a Docker `healthcheck` for every declared service. A deployment fails
  if any service has no health check or does not become `healthy` before the
  configured timeout.
- Use non-conflicting published ports on the VPS.
- Use named volumes or another persistent storage strategy for data that must
  survive image rebuilds and container replacement.
- Avoid relying on software or files that exist only on a developer's computer.

### Environment-variable requirements

LaunchPlatz generates a `.env` file at the cloned repository root during every
deployment. The application must load its runtime configuration from that file,
for example through Compose `env_file` entries.

Before deployment, every required variable must be created through the Project's
environment-variable APIs. Values are strings; secrets should be marked with
`is_secret: true` for UI metadata, although all values are encrypted at rest.

The repository must not depend on a committed production `.env` file.

### Current compatibility limits

The current pipeline is specifically designed for Docker Compose applications
containing Django and React. It does not currently support non-Compose projects,
Node-only applications, alternative Django management-command locations,
interactive deployment scripts, Kubernetes, or Docker Swarm.

### Pre-deployment checklist

Verify this checklist before creating the LaunchPlatz Project:

- [ ] The Git repository is reachable from the VPS.
- [ ] The selected branch exists.
- [ ] The configured Docker Compose path exists in the repository.
- [ ] The configured Django service name matches a Compose service.
- [ ] `manage.py` is in that service's working directory.
- [ ] `python manage.py migrate --noinput` succeeds in the service.
- [ ] `python manage.py collectstatic --noinput` succeeds in the service.
- [ ] Every Compose service defines a working health check.
- [ ] All required environment-variable names and values are known.
- [ ] Published ports are available on the VPS.
- [ ] Persistent application data uses volumes or external storage.
- [ ] No production secrets or private keys are committed to Git.

The included demo repository satisfies this contract with the `backend` Django
service, the root `docker-compose.yml`, and health checks for both `backend` and
`frontend`.

## 1. Start LaunchPlatz Locally

Install and start Docker Desktop, then run these commands from the LaunchPlatz
repository root:

```bash
python scripts/setup_docker_env.py
docker compose up --build -d
docker compose ps
```

All four services should be running, and `db` and `redis` should be healthy.
Create an Admin the first time:

```bash
docker compose exec web python manage.py createsuperuser
```

Open Swagger at <http://127.0.0.1:8000/api/docs/>.

Useful local diagnostics:

```bash
docker compose logs -f web worker
docker compose exec web python manage.py check
```

## 2. Prepare the VPS

The VPS must have:

- SSH access using the private key that will be stored in LaunchPlatz.
- Git.
- Docker Engine.
- The Docker Compose plugin (`docker compose`).
- Permission for the configured SSH user to run Docker and write inside its home
  directory.

Verify the same private key from your development computer before adding it:

```cmd
ssh -i "%USERPROFILE%\.ssh\id_ed25519" root@YOUR_VPS_IP
```

Use the VPS username and key path that apply to your server. Exit the interactive
SSH session with:

```bash
exit
```

LaunchPlatz opens and closes its own short-lived SSH sessions automatically.

## 3. Log In to LaunchPlatz

In Swagger, run `POST /api/v1/auth/login/`:

```json
{
  "email": "your-admin@example.com",
  "password": "your-admin-password"
}
```

Copy the returned access token, select **Authorize**, and enter:

```text
Bearer YOUR_ACCESS_TOKEN
```

## 4. Add and Test the VPS

Run `POST /api/v1/servers/`:

```json
{
  "name": "Demo VPS",
  "ip_address": "YOUR_VPS_IP",
  "ssh_port": 22,
  "username": "root",
  "private_key": "PASTE_THE_COMPLETE_PRIVATE_KEY_HERE"
}
```

In Swagger, paste the actual private-key file contents, including the BEGIN and
END lines. Do not paste the public `.pub` file. Swagger handles line breaks; do
not type visible `\n` text between key lines.

Save the returned server ID, then run:

```text
POST /api/v1/servers/{server_id}/test-connection/
```

Continue only after the response reports `Online` without a failure reason.

## 5. Create the Demo Project

Run `POST /api/v1/projects/` with the server ID:

```json
{
  "server": 1,
  "name": "LaunchPlatz Deployment Demo",
  "git_repository_url": "https://github.com/alamJamshed/launchplatz-deployment-demo.git",
  "branch": "main",
  "docker_compose_path": "docker-compose.yml",
  "django_service_name": "backend"
}
```

Replace `1` with the real server ID. The demo repository is public, so it does
not require `git_private_key`. The domain is optional for this port-based demo.

Save the returned project ID.

## 6. Clone the Demo Repository

Run:

```text
POST /api/v1/projects/{project_id}/git/clone/
```

LaunchPlatz clones it on the VPS under:

```text
~/launchplatz/projects/{project_id}
```

If the endpoint reports that the workspace already exists, use the existing
project record or remove the stale remote workspace manually only after checking
that it contains no needed data.

## 7. Add Demo Environment Variables

Create each variable separately with:

```text
POST /api/v1/projects/{project_id}/environment-variables/
```

Create `SECRET_KEY` using a unique generated Django key:

```json
{
  "key": "SECRET_KEY",
  "value": "YOUR_UNIQUE_DEMO_DJANGO_SECRET",
  "is_secret": true
}
```

Create `DEBUG`:

```json
{
  "key": "DEBUG",
  "value": "False",
  "is_secret": false
}
```

Create `ALLOWED_HOSTS`:

```json
{
  "key": "ALLOWED_HOSTS",
  "value": "*",
  "is_secret": false
}
```

LaunchPlatz encrypts all three database values and generates the remote `.env`
during deployment. You do not need to call `generate-env` separately.

## 8. Deploy

Run:

```text
POST /api/v1/projects/{project_id}/deploy/
```

The API returns HTTP `202`. Save the deployment ID and poll:

```text
GET /api/v1/deployments/{deployment_id}/progress/
```

Continue polling until `status` becomes `success`, `failed`, or `cancelled`.
A successful run completes these steps:

1. Connect to the VPS.
2. Pull the selected Git branch using fast-forward-only behavior.
3. Generate the remote `.env` securely.
4. Build the Compose images.
5. Start the services.
6. Run Django migrations in `backend`.
7. Run Django `collectstatic` in `backend`.
8. Restart the services.
9. Wait for every declared service to become healthy.
10. Record the deployed commit and immutable history.

## 9. Open and Inspect the Demo

The demo publishes these VPS ports:

- Frontend: `http://YOUR_VPS_IP:8080`
- Backend health endpoint: `http://YOUR_VPS_IP:8001/api/health/`

The VPS firewall or provider firewall must permit these ports for remote browser
access. They are convenient demo ports, not the recommended production layout.
Production applications should normally use a reverse proxy and expose only
ports `80` and `443`, while keeping SSH restricted.

Inspect live Compose state through LaunchPlatz:

```text
GET /api/v1/projects/{project_id}/containers/
GET /api/v1/projects/{project_id}/containers/backend/
GET /api/v1/projects/{project_id}/containers/frontend/
```

Read recent logs:

```text
GET /api/v1/projects/{project_id}/containers/backend/logs/?tail=200
GET /api/v1/projects/{project_id}/containers/frontend/logs/?tail=200
```

## 10. Redeploy Later Changes

After changes are pushed to the repository's selected branch, run:

```text
POST /api/v1/projects/{project_id}/redeploy/
```

Save the new deployment ID and poll its progress. Every attempt remains in the
immutable history:

```text
GET /api/v1/deployments/?project={project_id}&ordering=newest
GET /api/v1/deployments/{deployment_id}/
```

## Deployment and Container APIs

| API | What it does |
|---|---|
| `POST /api/v1/projects/{id}/deploy/` | Queues the first deployment pipeline. |
| `POST /api/v1/projects/{id}/redeploy/` | Queues the same pipeline as a redeployment. |
| `GET /api/v1/projects/{id}/deployment-status/` | Returns the project's latest deployment. |
| `GET /api/v1/deployments/{id}/progress/` | Returns one deployment and its ordered steps. |
| `POST /api/v1/deployments/{id}/cancel/` | Cooperatively requests cancellation. |
| `GET /api/v1/deployments/` | Lists immutable deployment history. |
| `GET /api/v1/deployments/{id}/` | Returns immutable deployment details. |
| `GET /api/v1/projects/{id}/containers/` | Polls every declared Compose service. |
| `GET /api/v1/projects/{id}/containers/{service}/` | Polls one Compose service. |
| `POST /api/v1/projects/{id}/containers/{service}/start/` | Starts an existing stopped container. |
| `POST /api/v1/projects/{id}/containers/{service}/stop/` | Stops an existing container. |
| `POST /api/v1/projects/{id}/containers/{service}/restart/` | Restarts an existing container. |
| `DELETE /api/v1/projects/{id}/containers/{service}/` | Removes only that service container. |
| `GET /api/v1/projects/{id}/containers/{service}/logs/?tail=200` | Returns recent timestamped logs. |

## Troubleshooting

### Deployment remains pending

Check the local worker and Redis:

```bash
docker compose ps
docker compose logs --tail=200 worker redis
```

### `broker_not_configured`

Confirm LaunchPlatz was started with the root Compose stack and that
`.env.docker` contains the Redis URLs. Restart after environment changes:

```bash
docker compose down
docker compose up --build -d
```

### SSH or authentication failure

Test the exact key directly with `ssh -i`, verify its matching public key exists
in the VPS user's `~/.ssh/authorized_keys`, then rerun the server connection test.

### Git clone or pull failure

Confirm the repository URL and branch. The demo uses public HTTPS and needs no
Git key. Pull rejects dirty, diverged, or non-fast-forward workspaces.

### `compose_up_failed`

Inspect backend and frontend logs through the container log APIs. If necessary,
SSH into the VPS and inspect the project without changing it:

```bash
cd ~/launchplatz/projects/PROJECT_ID
docker compose ps --all
docker compose logs --tail=200
```

### `health_check_failed`

Both demo services define health checks. Inspect their live state and logs. The
backend must answer `/api/health/`, and the frontend Nginx health route must be
reachable before the deployment can succeed.

### Stop or reset local LaunchPlatz

```bash
docker compose down
docker compose down --volumes
```

The second command permanently removes the local LaunchPlatz PostgreSQL and
Redis data. It does not remove anything from the VPS.
