# Django Base 2025

A comprehensive Django REST Framework boilerplate with role-based authentication, dynamic email configuration, and modular architecture.

## Features

- **JWT Authentication** with secure refresh token handling
- **Role-based Access Control** (Admin, User roles)
- **Dynamic SMTP Configuration** with encrypted password storage
- **Email Services** (Welcome, Password Reset, Verification)
- **Comprehensive Logging** with table formatting
- **Location Services** (Countries, States, Cities)
- **API Documentation** with Swagger/OpenAPI
- **Modular Architecture** with separate apps

## Quick Start

### Prerequisites
- Python 3.8+
- PostgreSQL
- Git

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd django_base_2025
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**
```bash
# For development
pip install -r requirements/development.txt

# For production
pip install -r requirements/production.txt
```

4. **Environment setup**
```bash
cp .env.example .env
```

5. **Configure environment variables**
```bash
# Generate encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Edit .env file with your values
SECRET_KEY=your-django-secret-key
DB_NAME=your_database_name
DB_USER=your_database_user
DB_PASSWORD=your_database_password
SMTP_ENCRYPTION_KEY=generated_encryption_key
FRONTEND_URL=http://localhost:3000
```

6. **Database setup**
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
```

7. **Create logs directory**
```bash
mkdir logs
```

8. **Run the server**
```bash
python manage.py runserver
```

## API Endpoints

### Authentication
- `POST /api/v1/auth/login/` - User login
- `POST /api/v1/auth/refresh/` - Refresh access token
- `GET /api/v1/auth/profile/` - User profile

### Location Services
- `GET /api/v1/auth/common/countries/` - List countries
- `GET /api/v1/auth/common/states/{country_id}/` - List states
- `GET /api/v1/auth/common/cities/{state_id}/` - List cities

### Documentation
- `GET /api/docs/` - Swagger UI
- `GET /api/schema/` - OpenAPI schema

## Project Structure

```
django_base_2025/
├── Config/                 # Django settings
│   ├── settings/
│   │   ├── base.py
│   │   ├── development.py
│   │   └── production.py
│   ├── urls.py
│   └── wsgi.py
├── coreapp/               # Core application
│   ├── api/
│   │   ├── admin/         # Admin APIs
│   │   └── common/        # Common APIs
│   ├── utils/             # Utilities
│   │   ├── email_utils.py
│   │   ├── smtp_config.py
│   │   └── logging.py
│   └── models.py
├── utility/               # Utility app
│   ├── models.py          # Settings models
│   └── constants.py
└── logs/                  # Log files
```

## Configuration

### SMTP Settings
Configure email settings via Django admin or create `SMTPSettings` objects:
- Host, Port, Username, Password (encrypted)
- TLS/SSL configuration
- From email and name

### Site Settings
Configure site information via `SiteSettings` model:
- Site name, description
- Contact information
- Maintenance mode

### Logging
- **Development**: Console + file logging with table format
- **Production**: File logging with rotation
- **Error-only**: Only logs errors and warnings

## Security Features

- **JWT Tokens**: Access tokens (60 min) + Refresh tokens (7 days)
- **Secure Cookies**: HTTP-only refresh token storage
- **Password Encryption**: SMTP passwords encrypted with Fernet
- **CORS Protection**: Configurable allowed origins
- **Role-based Access**: Admin/User role separation

## Email Services

Available email templates:
- Welcome email on first login
- Password reset
- Email verification
- Account activation
- Password change notification

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Collecting Static Files
```bash
python manage.py collectstatic
```

## Deployment

1. Set `DJANGO_ENV=production` in environment
2. Configure production database
3. Set up HTTPS and SSL certificates
4. Configure reverse proxy (Nginx)
5. Use process manager (Gunicorn + Supervisor)

## Contributing

1. Fork the repository
2. Create feature branch
3. Make changes
4. Add tests
5. Submit pull request

## License

MIT License - see LICENSE file for details.