# ConMan

ConMan is a self-hosted convention vendor-management application for managing vendor applications, payments, seating, on-site check-in, badges, administration, and reports.

## Stack

- **Backend:** Python, FastAPI, SQLAlchemy 2, Alembic
- **Database:** PostgreSQL 17
- **Frontend:** React, TypeScript, Vite
- **Reverse proxy:** Caddy
- **Deployment:** Docker Compose, GitHub Actions, GHCR

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

## Local build / development

The local compose file builds the backend, frontend, and Caddy images from the working tree.

1. Copy the environment template:

   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and set a strong PostgreSQL password.

3. Build and start the local stack:

   ```bash
   docker compose -f compose.dev.yaml up -d --build
   ```

4. Create the first administrator:

   ```bash
   docker compose -f compose.dev.yaml exec backend python -m app.cli create-admin --email you@example.com --name "Administrator"
   ```

5. Open the host in a browser. For the default LAN setup this is normally:

   ```text
   http://<server-ip>/
   ```

## Production deployment with Portainer

Production `compose.yaml` does **not** contain Compose `build:` steps. GitHub Actions builds the application images and publishes them to GitHub Container Registry (GHCR); Portainer only pulls and runs those images. This avoids remote BuildKit/Portainer Agent build failures.

### 1. Build the images

Push or merge changes into `main`. The workflow `.github/workflows/docker-images.yml` publishes:

```text
ghcr.io/viacheslavkonov/conman-backend:latest
ghcr.io/viacheslavkonov/conman-frontend:latest
ghcr.io/viacheslavkonov/conman-proxy:latest
```

Every build is also tagged with the full Git commit SHA, which can be used for a pinned production release.

### 2. Allow Portainer to pull private GHCR images

If the GHCR packages are private, add GitHub Container Registry to Portainer:

```text
Registry: ghcr.io
Username: ViacheslavKonov
Password/token: GitHub token with read:packages
```

Keep this credential in Portainer; do not commit it to the repository or place it in `.env`.

### 3. Configure the stack

Use the repository `compose.yaml` and configure at least:

```env
CONMAN_IMAGE_REGISTRY=ghcr.io/viacheslavkonov
CONMAN_IMAGE_TAG=latest

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

For a controlled rollout, replace `latest` with the full Git commit SHA published by the workflow:

```env
CONMAN_IMAGE_TAG=<full-git-commit-sha>
```

### 4. Deploy / update

Deploy the stack normally in Portainer. No image build should run on the Portainer host.

When using `latest`, redeploy the stack with image pulling enabled so the freshly published images are fetched. For deterministic production deployments, prefer a commit-SHA tag and change `CONMAN_IMAGE_TAG` when promoting a release.

## Configuration

The repository intentionally contains only `.env.example`. **Do not commit `.env`**.

Important variables:

```env
CONMAN_IMAGE_REGISTRY=ghcr.io/viacheslavkonov
CONMAN_IMAGE_TAG=latest

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

## Database migrations

Backend startup runs:

```bash
alembic upgrade head
```

The current schema includes migrations through Step 7 seating preferences and planning (`0006_seating_planning`).

## Repository layout

```text
.
├── .github/workflows/   Container image build/publish workflow
├── backend/             FastAPI, SQLAlchemy, Alembic
├── frontend/            React + TypeScript
├── proxy/               Caddy configuration
├── compose.yaml         Production: pulls prebuilt GHCR images
├── compose.dev.yaml     Local: builds images from source
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
