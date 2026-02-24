# ZapControl Backend (Django Foundation)

This folder contains the Django backend for ZapUI.

It provides the **authentication and application foundation** only. Setup wizard logic and scanning domain workflows are intentionally deferred.

## What is implemented

- Django 5 + DRF baseline
- Custom user model with **email login**
- Role model with built-in roles:
  - `admin`
  - `security_engineer`
  - `readonly`
- Django Admin wiring for custom user + core models
- Auth routes:
  - `/login`
  - `/logout`
  - `/dashboard` (requires authentication)
- Setup placeholder endpoint:
  - `/setup`
- API endpoint:
  - `/api/version`
- Basic Bootstrap-based UI shell

## Project structure

```text
backend/zapcontrol/
├── manage.py
├── requirements.txt
├── accounts/
│   ├── models.py        # custom User + roles
│   ├── admin.py         # custom admin config
│   ├── views.py         # login/logout views
│   ├── urls.py          # /login, /logout
│   └── templates/
│       └── accounts/login.html
├── core/
│   ├── models.py        # AppSetting + SetupState placeholders
│   ├── views.py         # health, setup, dashboard, api_version
│   ├── admin.py
│   └── templates/core/  # base.html + dashboard.html
└── zapcontrol/
    ├── settings.py
    └── urls.py
```

## Authentication model

- `AUTH_USER_MODEL = accounts.User`
- Username field is email (`USERNAME_FIELD = 'email'`)
- `username` is removed from the custom user model
- Roles are stored in `User.role` with Django choices

### Role semantics (current baseline)

- `admin`: full platform admin intent
- `security_engineer`: intended for operational security work
- `readonly`: read-only role intent

> Note: role-based authorization policy enforcement is not fully expanded yet; this foundation establishes identity + role storage.

## Security defaults

- CSRF middleware enabled
- Session + CSRF secure cookie behavior when HTTPS/proxy is used
- Session defaults:
  - `SESSION_COOKIE_AGE`: 8 hours
  - `SESSION_SAVE_EVERY_REQUEST`: enabled
- `SECURE_PROXY_SSL_HEADER` is configured for reverse-proxy TLS forwarding

## Endpoints

### Web

- `GET /health` → health JSON
- `GET /setup` → placeholder response (wizard not implemented)
- `GET /login` and `POST /login`
- `GET /logout`
- `GET /dashboard` (auth required)
- `GET /admin/`

### API

- `GET /api/version`

Example response:

```json
{
  "name": "zapcontrol",
  "version": "0.1.0"
}
```

## Local development

Install dependencies:

```bash
pip install -r backend/zapcontrol/requirements.txt
```

Run checks:

```bash
cd backend/zapcontrol
python manage.py check
```

Run server:

```bash
cd backend/zapcontrol
python manage.py runserver 0.0.0.0:8000
```

## Database and migrations

### Default runtime database

By default, settings target PostgreSQL using `POSTGRES_*` environment variables.

### Optional SQLite mode (for local quick validation)

Set:

```bash
export DJANGO_DB_ENGINE=sqlite
```

Then run:

```bash
cd backend/zapcontrol
python manage.py makemigrations
python manage.py migrate
```

## Create an admin user

Interactive:

```bash
cd backend/zapcontrol
python manage.py createsuperuser
```

Non-interactive example:

```bash
cd backend/zapcontrol
DJANGO_SUPERUSER_EMAIL=admin@example.com \
DJANGO_SUPERUSER_PASSWORD=change-me \
python manage.py createsuperuser --noinput
```

## Docker workflow

From repo root:

```bash
docker compose exec web python manage.py makemigrations
docker compose exec web python manage.py migrate
docker compose exec web python manage.py createsuperuser
```

## Current non-goals

This backend foundation does **not** yet implement:

- setup wizard business logic
- scan orchestration and scheduling
- findings normalization
- risk scoring and trend analytics
- reporting pipeline

These are planned for subsequent iterations.
