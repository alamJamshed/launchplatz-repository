# LaunchPlatz Backend

LaunchPlatz is an Admin-only deployment platform for Docker-based Django and
React projects. It connects to VPS servers over SSH, manages Git repositories
and environment variables, runs deployments through Celery, and provides live
Docker Compose controls and immutable deployment history.

This repository contains the Django REST API. A frontend is not included.

## Implemented Modules

1. Authentication - Admin JWT login, refresh-cookie rotation, logout, and profile.
2. Server Management - VPS CRUD, encrypted SSH keys, connection tests, and status.
3. Project Management - Project CRUD, archive/restore, and server assignment.
4. Git Integration - Clone, pull, branches, commit inspection, and operation history.
5. Environment Variables - Encrypted variable CRUD and remote `.env` generation.
6. Deployment Pipeline - Celery-based Docker Compose deployment and rollback.
7. Docker Management - Live service status, lifecycle controls, and recent logs.
8. Deployment History - Immutable, filterable deployment records and step details.

## Architecture

- Django and Django REST Framework provide the API.
- PostgreSQL stores users, servers, projects, encrypted values, and audit history.
- JWT access tokens authorize requests; refresh tokens use HttpOnly cookies.
- Paramiko connects to project VPS servers over SSH/SFTP.
- Redis is the Celery message broker and result backend.
- Celery workers perform deployment pipelines outside the HTTP request.
- Git and Docker Compose commands run on the assigned VPS, not this API host.

Redis and Celery are only required when running background deployments. Normal
CRUD, authentication, history, and synchronous management APIs do not require a
Celery worker.

## Setup methods

Use exactly one of the following methods to run LaunchPlatz locally:

- **Method 1 - Docker setup (recommended):** Docker runs Django, PostgreSQL,
  Redis, and Celery for you.
- **Method 2 - Manual setup:** You install and run Python, PostgreSQL, Redis,
  Django, and Celery yourself.

Do not complete both methods. Both produce the same LaunchPlatz API at
<http://127.0.0.1:8000/>.

A real deployment additionally requires a target VPS with SSH, Git, Docker
Engine, and the Docker Compose plugin.

## Method 1 - Docker Setup (Recommended)

Docker Compose runs Django, PostgreSQL, Redis, and Celery together. You do not
need to install or start PostgreSQL or Redis separately.

### Requirements

- Git
- Python 3.11 or newer, used only to generate private local credentials
- Docker Desktop with Docker Compose v2

### 1. Clone and enter the repository

```cmd
git clone https://github.com/alamJamshed/launchplatz-repository.git
cd launchplatz-repository
```

### 2. Generate private local credentials

```bash
python scripts/setup_docker_env.py
```

This creates an ignored `.env.docker` containing random local credentials and
encryption keys. Running the command again preserves the existing file. Do not
replace it while retaining the Docker database because previously encrypted
records would become unreadable.

### 3. Build and start the stack

```bash
docker compose up --build
```

The first startup downloads images, installs dependencies, creates PostgreSQL
and Redis volumes, waits for both services, and applies Django migrations. Django
reloads automatically when Python source files change.

To run the stack in the background instead:

```bash
docker compose up --build -d
```

### 4. Create the Admin account

In a second terminal:

```bash
docker compose exec web python manage.py createsuperuser
```

Open:

- Swagger UI: <http://127.0.0.1:8000/api/docs/>
- OpenAPI schema: <http://127.0.0.1:8000/api/schema/>
- Django Admin: <http://127.0.0.1:8000/admin/>

### Everyday Docker commands

```bash
# Stop the stack while preserving its data
docker compose down

# Rebuild after changing Python dependencies or Docker files
docker compose up --build

# Follow Django and Celery output
docker compose logs -f web worker

# Run tests and checks inside Django
docker compose exec web python manage.py test
docker compose exec web python manage.py check
docker compose exec web python manage.py makemigrations --check --dry-run

# Apply migrations manually when needed
docker compose exec web python manage.py migrate

# Open a Django shell or container shell
docker compose exec web python manage.py shell
docker compose exec web sh
```

To permanently delete the disposable local PostgreSQL and Redis data:

```bash
docker compose down --volumes
```

This cannot be undone. After removing the volumes, you can safely regenerate
`.env.docker` with:

```bash
python scripts/setup_docker_env.py --force
```

The values in `.env.docker` are development credentials. Never use them in
production or commit the file.

### Docker setup troubleshooting

If `docker` is not recognized, install or start Docker Desktop and confirm that
Docker Compose v2 is available:

```bash
docker compose version
```

If a container is unhealthy or a deployment remains pending, inspect only the
Docker stack used by Method 1:

```bash
docker compose ps
docker compose logs --tail=200 db redis web worker
```

After changing `.env.docker`, restart the stack with `docker compose down` and
`docker compose up --build -d`. Do not regenerate its encryption keys while
keeping the existing database volume.

## Method 2 - Manual Setup

Use this alternative only when you do not want to run the backend services in
Docker. Skip this entire section if Method 1 is already running.

### Requirements

- Git
- Python 3.11 or newer
- PostgreSQL
- Redis when running deployments

### 1. Clone and enter the repository

```cmd
git clone https://github.com/alamJamshed/launchplatz-repository.git
cd launchplatz-repository
```

### 2. Create and activate a virtual environment

Windows Command Prompt:

```cmd
python -m venv venv
venv\Scripts\activate
```

Windows PowerShell:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

Linux/macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Create the environment file

Windows Command Prompt:

```cmd
copy .env.example .env
```

Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Linux/macOS:

```bash
cp .env.example .env
```

Generate a Django secret key:

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Generate four distinct Fernet keys, one at a time:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Copy the generated values into `.env` for:

- `SECRET_KEY`
- `SMTP_ENCRYPTION_KEY`
- `SERVER_CREDENTIAL_ENCRYPTION_KEY`
- `GIT_CREDENTIAL_ENCRYPTION_KEY`
- `ENVIRONMENT_VARIABLE_ENCRYPTION_KEY`

Keep the following development values valid:

```env
DJANGO_ENV=development
DEBUG=True
DB_NAME=launchplatz
DB_USER=postgres
DB_PASSWORD=your_postgres_password
DB_HOST=localhost
DB_PORT=5432
```

`DEBUG` must be `True` or `False`; values such as `development` or `release`
will prevent Django from starting.

### 5. Create the PostgreSQL database

Open PostgreSQL's `psql` shell and create the database:

```sql
CREATE DATABASE launchplatz;
```

If `psql` is not on the Windows PATH, use its full path, for example:

```cmd
"C:\Program Files\PostgreSQL\18\bin\psql.exe" -U postgres -h localhost -p 5432
```

Update the version in that path if a different PostgreSQL version is installed.

### 6. Apply migrations and create an Admin

```bash
python manage.py migrate
python manage.py createsuperuser
```

The application role on an API Admin must be `Admin`. Accounts created through
the current custom superuser manager receive that role.

### 7. Start Django

```bash
python manage.py runserver
```

Open:

- Swagger UI: <http://127.0.0.1:8000/api/docs/>
- OpenAPI schema: <http://127.0.0.1:8000/api/schema/>
- Django Admin: <http://127.0.0.1:8000/admin/>

### 8. Start Redis and Celery for deployments

Deployment requests need Redis and a Celery worker in addition to Django.

Set these values in `.env`:

```env
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/1
```

#### Start Redis on Windows with WSL

From PowerShell or Command Prompt:

```cmd
wsl -d Ubuntu
```

Inside Ubuntu:

```bash
sudo service redis-server start
redis-cli ping
```

Redis is ready when the second command returns `PONG`.

On Linux, install Redis through the system package manager and start its service.
On macOS, Redis can be installed and started with Homebrew.

#### Start the Celery worker

Open a second terminal in the repository, activate the same virtual environment,
and run this on Windows:

```cmd
celery -A Config worker --loglevel=info --pool=solo
```

Linux/macOS:

```bash
celery -A Config worker --loglevel=info
```

Keep Django, Redis, and the worker running while deployment jobs execute. They
must all use the same database, Redis URLs, and encryption keys.

### Manual setup tests and checks

The automated test suite mocks VPS, SSH, Docker, Git, and Redis interactions; it
does not deploy to a real server.

```bash
python manage.py test
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yml --validate
```

Use `DJANGO_ENV=test` when an isolated SQLite test configuration is preferred.

### Manual setup troubleshooting

If Django reports `Invalid truth value`, set `DEBUG=True` for development or
`DEBUG=False` for production.

If Python reports `No module named celery`, activate the virtual environment and
run:

```bash
pip install -r requirements.txt
```

For `broker_not_configured` or Redis connection errors, confirm both Celery URLs
exist in `.env`, verify `redis-cli ping` returns `PONG`, and restart Django and
the manually started Celery worker.

For PostgreSQL errors, confirm PostgreSQL is running and verify `DB_NAME`,
`DB_USER`, `DB_PASSWORD`, `DB_HOST`, and `DB_PORT`. The database must already
exist. If `psql` is not recognized on Windows, run `psql.exe` using its complete
installation path or add its `bin` directory to PATH.

`Copy-Item` is a PowerShell command. In Command Prompt, use:

```cmd
copy .env.example .env
```

## After Either Setup Method

Once the selected method is running, both methods provide the same API, Swagger
interface, authentication behavior, and deployment workflow. Do not start the
services from the other method at the same time.

## API Documentation

- [SERVER_API_GUIDE.md](SERVER_API_GUIDE.md) explains the server, project, Git,
  environment-variable, deployment-history, and container APIs.
- [DEPLOYMENT_QUICK_GUIDE.md](DEPLOYMENT_QUICK_GUIDE.md) defines the application
  compatibility requirements and provides the complete demo deployment workflow.
- Swagger provides interactive request and response schemas at `/api/docs/`.

All protected endpoints require an access token from
`POST /api/v1/auth/login/`. In Swagger, select **Authorize** and enter:

```text
Bearer <access-token>
```

## Project Structure

```text
django_boilerplate_2025/
|-- Config/          Django settings, root URLs, and Celery configuration
|-- coreapp/         Custom users, authentication, permissions, and shared code
|-- servers/         VPS records, encrypted SSH credentials, and status checks
|-- projects/        Projects, Git, environment variables, and Docker APIs
|-- deployments/     Deployment pipeline, tasks, history, and step records
|-- containers/      Remote Docker Compose inspection and lifecycle services
|-- utility/         Supporting application models and APIs
|-- requirements/    Canonical Python dependency list
|-- manage.py        Django command entry point
|-- .env.example     Safe environment-variable template
`-- requirements.txt Root dependency installation entry point
```

## Sharing and Security

Never commit or send these files to another developer:

- `.env` or any production environment file
- Private SSH or Git keys
- `venv/` or another virtual environment
- SQLite/database files or PostgreSQL dumps containing real data
- Application logs

Share `.env.example` and let every developer generate their own secrets. Fernet
keys must remain stable after encrypted records are created; changing a key makes
the corresponding stored ciphertext unreadable.
