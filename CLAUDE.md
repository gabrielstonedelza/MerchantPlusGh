# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Merchant+ Backend — a multi-tenant SaaS financial platform for payment agents in Ghana. Built with Django 4.2+, Django REST Framework, Django Channels (WebSockets), and Celery for background tasks.

## Common Commands

```bash
# Development server
python manage.py runserver

# Run migrations
python manage.py migrate

# Seed subscription plans (required for company registration)
python manage.py seed_plans

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_auth.py

# Run a specific test
pytest tests/test_auth.py::TestLogin::test_login_success

# Docker development stack (PostgreSQL, Redis, Celery, API)
docker-compose up

# Celery worker (requires Redis)
celery -A config worker -l info

# Celery beat scheduler
celery -A config beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler
```

## Architecture

### Multi-Tenancy Model
- `Company` is the tenant. All domain models have a `company` ForeignKey for isolation.
- `TenantMiddleware` (`middleware/tenant.py`) resolves company from the `X-Company-ID` header or the user's single active membership, attaching `request.company` and `request.membership`.
- Every protected endpoint requires `IsCompanyMember` permission.

### Authentication & Authorization
- **Auth methods**: DRF TokenAuthentication + SessionAuthentication, with optional TOTP-based 2FA (`accounts/views_2fa.py`).
- **RBAC** (`permissions.py`): 4-tier role hierarchy — `owner(4) > admin(3) > manager(2) > teller(1)`. Permission classes: `IsOwner`, `IsAdminOrAbove`, `IsManagerOrAbove`, `IsCompanyMember`, `IsCompanyActive`.
- **Brute-force protection**: `AccountLockoutMiddleware` locks IPs after 5 failed login attempts for 15 minutes.

### Request Flow
```
Request → SecurityMiddleware → CorsMiddleware → AuthenticationMiddleware
        → AccountLockoutMiddleware → SecurityHeadersMiddleware
        → TenantMiddleware (sets request.company/membership)
        → AuditMiddleware (thread-local tracking)
        → DRF View (permission checks → serializer → response)
```

### App Structure
| App | Responsibility |
|---|---|
| `accounts` | Custom User model (email-based), Membership, Invitation, UserProfile, 2FA |
| `core` | Company, Branch, SubscriptionPlan, APIKey, CompanySettings, Webhooks |
| `customers` | Customer records, CustomerAccount, KYC verification |
| `transactions` | Transaction (bank/mobile money/cash), approvals, reversals, DailyClosing, ProviderBalance |
| `notifications` | In-app notifications, ActivityLog, email/SMS dispatch (Hubtel/Arkesel) |
| `reports` | Dashboard analytics, filtered reports, CSV exports |
| `audit` | Immutable AuditEntry compliance logs |
| `middleware` | TenantMiddleware, AccountLockoutMiddleware, SecurityHeadersMiddleware, AuditMiddleware |

### API Routing
All API endpoints are under `/api/v1/` (aggregated in `api_urls.py`). OpenAPI docs at `/api/docs/` (Swagger) and `/api/redoc/`.

### Real-Time
- WebSocket via Django Channels at `ws://.../ws/admin/dashboard/` (`transactions/consumers.py`)
- Events: `transaction_event`, `customer_event`, `balance_event`
- Channel layer: Redis in production, InMemoryChannelLayer in development

### Background Tasks
- Celery with Redis broker (`config/celery.py`)
- Key tasks: webhook delivery with HMAC-SHA256 signing (`core/tasks.py`), email/SMS dispatch (`notifications/tasks.py`)
- Webhook events: `transaction.created`, `transaction.completed`, `transaction.reversed`, `customer.created`, `customer.kyc_verified`, `balance.changed`

### Transaction Workflow
Transactions go through: `pending → approved/rejected → completed/reversed/failed`. High-value transactions (above `require_approval_above` threshold in CompanySettings) require manager+ approval.

### Database
- **Development**: SQLite (`db.sqlite3`)
- **Production**: PostgreSQL 16 (configured via `DB_*` env vars with `python-decouple`)
- Custom User model uses email as the username field

### Environment Variables
Configured via `.env` file using `python-decouple`. Key vars: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DB_NAME/USER/PASSWORD/HOST/PORT`, `REDIS_HOST`, `CELERY_BROKER_URL`, `SMS_PROVIDER`, `SMS_API_KEY`, `EMAIL_HOST_USER/PASSWORD`.

## Testing
- Framework: pytest + pytest-django (config in `pytest.ini`)
- Fixtures in `tests/conftest.py` provide: subscription plans, company, owner/teller users with tokens and authenticated API clients, customer instances
- Settings module: `config.settings`
