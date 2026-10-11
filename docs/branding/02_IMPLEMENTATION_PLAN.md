# ConMan Concept A — implementation plan

Repository snapshot reviewed 2026-10-11; re-check main before coding.

## Actual code touchpoints
| Area | File | Action |
|---|---|---|
| Router and shell | frontend/src/App.tsx | LoginPage, Shell, NavButton, role gating and currentEvent |
| Login styles + all UI | frontend/src/styles.css | Add tokens and targeted selectors; avoid broad regex in ~3300 CSS lines |
| Initial admin | frontend/src/FirstAdminPage.tsx | Brand first-run UI, preserve bootstrap and validation |
| Vendor registration | frontend/src/PublicRegistrationPage.tsx | PublicShell header/style only, keep /register event_id behavior |
| Vendor preferences | frontend/src/PublicPreferencesPage.tsx | PreferenceShell branding only, preserve invite token |
| Static assets | frontend/public/brand | Use SVGs in this documentation branch |
| Browser tab | frontend/index.html | favicon, theme-color |
| Image build | frontend/Dockerfile | Crucial: add COPY public ./public in build stage (currently only src is copied) |
| CI | .github/workflows/ci.yml | Existing npm run build should still pass |
| Deploy | compose.yaml, .github/workflows/docker-images.yml | Remain unchanged; GHCR + Portainer production |

## Phase P0 — foundations
1. Inspect SVG files and render at 16/32/64/192px.
2. Build reusable BrandLogo React component with stacked/horizontal/mark variants, optional className, correct decorative semantics.
3. Add public to frontend Docker build, connect SVG favicon in index.html; optional raster exports.
4. Add --cm-* and semantic CSS tokens; align primary action, focus, base surfaces, errors/success.
5. Build after each change.

## Phase P1 — branding screens
1. Rebrand App.tsx LoginPage and loading/error screens, keeping api.me and api.login.
2. Rebrand FirstAdminPage without changing api.bootstrap or form validation.
3. Apply header/logo to PublicShell (/register) and PreferenceShell (/preferences), preserving token/event/form logic.
4. Verify keyboard, error, loading, very narrow mobile width.

## Phase P2 — navigation
1. Extract typed navigation config for current 10 View types (dashboard, applications, events, vendors, planning, seating, checkin, reports, management, users) without broadening visibility.
2. Adapt existing sidebar styling to approved horizontal desktop header; include current event and logout, overflow when needed.
3. Accessible mobile navigation/drawer. Escape closes, focus returns, selected state non-color-only.
4. Test each role ADMIN/MANAGER/REGISTRATION/VIEWER.

## Phase P3 — QA / PR
1. Check 320, 390, 768, 1440, 1920px + 200% zoom, reduced motion, contrast, focus, hover, disabled.
2. Capture (when available) screenshot evidence login, first-run, nav, /register and /preferences.
3. Run frontend build and git diff --check; run local smoke checks if test DB available.
4. PR summary must include changed files, test evidence, risks and rollback path.

## Scope protection
No backend, migrations, API client/types, business flows, seating solver, Docker Compose production settings, secrets, or Portainer actions. Do not add a component library or React Router solely for cosmetics.
