# ConMan — Codex repository instructions

Approved visual direction: **Concept A** — navy/blue/teal, convention floor tiles + location pin + CM monogram.

## Start here
1. Read [CODEX_START.md](CODEX_START.md), then [docs/branding/README.md](docs/branding/README.md) and linked files.
2. Inspect the *current* code before modifying it; instructions reflect 2026-10-11 main and can become stale.
3. Use a feature branch and reviewable commits. Do not merge, tag, release, or deploy without explicit authorization.
4. Branding scope is frontend/UI and documentation only. Do not modify backend business logic, DB, APIs, permissions, event-selection semantics, CSRF, or seating solver.
5. Run frontend build and record results, changed files and QA limitations.

## Repository architecture
- Frontend: React 19, TypeScript, Vite 6; App shell, LoginPage, NavButton in frontend/src/App.tsx.
- Shared CSS: frontend/src/styles.css (large; change selectors carefully).
- First admin: frontend/src/FirstAdminPage.tsx.
- Public registration: frontend/src/PublicRegistrationPage.tsx (route /register).
- Public seating preferences: frontend/src/PublicPreferencesPage.tsx (route /preferences).
- Frontend Dockerfile currently copies src but not public. Add COPY public ./public in build stage when using assets here.
- Internal navigation uses view state (10 views); do not add React Router for a cosmetic change.

## Constraints
- Preserve role restrictions for ADMIN, MANAGER, REGISTRATION and VIEWER; preserve all reachable sections.
- Preserve api.me, api.login, api.bootstrap, api.logout and api.currentEvent behavior.
- Never add fake SSO, password recovery, remembered-login actions or mock attendance counts.
- Use brand SVG files from frontend/public/brand/, not crops of a screenshot.
- Keep existing Russian UI labels and real event data.
- Meet keyboard focus, WCAG AA contrast, 320px responsiveness, 200% zoom and reduced-motion considerations.
- No external logo CDN or runtime font dependency; use Inter with system fallbacks.

## Completion evidence
- cd frontend && npm install && npm run build
- git diff --check
- Confirm files under public appear in frontend Docker image (build stage COPY).
- Smoke-check login, initial admin, main navigation by roles, /register, /preferences.
- Summarize screenshots when available, commands executed and remaining risks.
