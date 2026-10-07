# ConMan

ConMan is a self-hosted convention vendor-management application for managing vendor applications, payments, seating, on-site check-in, badges, administration, and reports.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic
- **Database:** PostgreSQL 17
- **Frontend:** React, TypeScript, Vite
- **Reverse proxy:** Caddy
- **Deployment:** Docker Compose

## Current functionality

- Authentication and role-based access: `ADMIN`, `MANAGER`, `REGISTRATION`, `VIEWER`
- Events and current-event selection
- Vendor and participant master data
- FULL / HALF vendor bookings and tariff-based pricing
- Public vendor registration and application review
- Charges, payments, refunds, and financial status
- Public seating preferences for approved vendors: preferred tables/zones, near/avoid relationships, priorities, and notes
- Versioned seating plans with automatic multi-variant heuristic planning, scores, conflicts, and explanations
- Interactive final seating map with zones, tables, A/B slots, drag-and-drop, grid snapping, and table editing
- Tabular vendor-to-table assignment
- On-site check-in and badge tracking
- Administrative CRUD and cascade operations
- Reports for vendors, participants, seating, finance, and check-in
- Audit log and check-in history

## Quick start

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set a strong PostgreSQL password.

3. Start the stack:

   ```bash
   docker compose up -d --build
   ```

4. Create the first administrator:

   ```bash
   docker compose exec backend python -m app.cli create-admin --email you@example.com --name "Administrator"
   ```

5. Open the host in a browser. For the default LAN setup this is normally:

   ```text
   http://<server-ip>/
   ```

## Configuration

The repository intentionally contains only `.env.example`. **Do not commit `.env`**.

Important variables:

```env
POSTGRES_DB=conman
POSTGRES_USER=conman
POSTGRES_PASSWORD=CHANGE_ME_TO_A_LONG_RANDOM_PASSWORD

APP_ENV=production
APP_NAME=ConMan
SESSION_TTL_HOURS=12

APP_HOST=:80
COOKIE_SECURE=false
COOKIE_DOMAIN=
```

For production with a DNS name and HTTPS, configure `APP_HOST`, `COOKIE_SECURE=true`, and `COOKIE_DOMAIN`.

## Database migrations

Backend startup runs:

```bash
alembic upgrade head
```

The current schema includes migrations through Step 7 seating preferences and planning (`0006_seating_planning`).

## Repository layout

```text
.
├── backend/        FastAPI, SQLAlchemy, Alembic
├── frontend/       React + TypeScript
├── proxy/          Caddy configuration
├── compose.yaml
├── .env.example
└── .gitignore
```

## Development status

ConMan is under active development. Current code includes applications, finance, seating preferences, versioned automatic/manual seating planning, final seating, check-in, administration, and reports.

## Security notes

- Passwords are hashed with Argon2.
- Authentication uses opaque server-side sessions.
- Only session-token hashes are stored in PostgreSQL.
- Session cookies are HttpOnly.
- Authenticated mutating requests use CSRF protection.
- Public seating-preference links use opaque bearer tokens and should be treated as private invitation links.
- Audit and check-in logs are kept as historical records.
