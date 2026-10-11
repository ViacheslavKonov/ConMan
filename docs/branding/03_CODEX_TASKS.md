# ConMan — tasks for Codex

Complete sequentially. Codex must read AGENTS.md and docs/branding/01_BRAND_SPEC.md first. Every task is allowed to change UI/frontend only; no backend or database changes.

## CM-BRAND-01 (P0) — assets and BrandLogo
Create frontend/src/components/BrandLogo.tsx with variants stacked, horizontal and mark, className, proper accessible alt/decorative semantics, based on frontend/public/brand SVGs. Ensure frontend/Dockerfile build stage copies public directory. Add SVG favicon/theme-color to frontend/index.html; optionally export PNG and .ico from canonical SVG. Run frontend npm install && npm run build.
Acceptance: no broken public asset URL in dev or Docker; favicon renders; no network logo dependency.

## CM-BRAND-02 (P0) — design tokens
Implement CM palette + semantic CSS tokens in scoped variables. Ensure focus visible, primary action legible, success and error semantics unchanged; DO NOT mass-replace colors across seating planning/graphics. Build succeeds.
Acceptance: stable CSS, accessible contrast for text/focus, no functional UI changes.

## CM-BRAND-03 (P1) — sign-in, first-run, error/loading
Use stack logo and white login card over subtle venue-grid background. Apply same visual system to first administrator screen, loading/error/retry states. Preserve FormData field names and api.login/api.bootstrap, validation, setup detection, and enabled/disabled behavior. Add role=alert to errors as needed. NO SSO/forgot-password/remember-me fake UI.
Acceptance: good/error login, first-admin flow, responsive 320px.

## CM-BRAND-04 (P1) — public vendor pages
Rebrand PublicShell (/register) and PreferenceShell (/preferences) with BrandLogo; preserve all event_id URL behavior, registration status steps, preference token storage/submission and unauthenticated access.
Acceptance: registration and seating preferences work without auth, including empty/error/loading.

## CM-BRAND-05 (P2) — desktop and mobile navigation
Current Shell in App.tsx uses a sidebar and 10 role-filtered View identifiers. Implement the Concept A desktop top navigation with event context, 'Ещё' overflow and accessible mobile drawer; preserve *exact* original role gating and ability to visit each allowed view. Use typed nav config. Escape closes mobile menu; focus return; aria-expanded, active text/underline; logout preserved. Avoid React Router and fake routes.
Acceptance: role matrix correct and 320px no clipped/unreachable navigation.

## CM-BRAND-06 (P3) — audit, screenshots, PR
Perform docs/branding/04_QA_CHECKLIST.md review. Build frontend; if possible smoke test against non-production DB. Document screenshots, changed files, commands/results and limitations. Prepare implementation PR, don't merge/deploy.
Acceptance: zero backend changes; user journeys still work; documented exceptions.

## General Definition of Done
- Consistent mark/logo/favicon across login, first-run, app shell, register and preferences.
- All 10 existing views remain accessible under original permissions.
- Keyboard focus, usable mobile nav, real metrics and no fake buttons.
- Build passes in test environment; PR with QA evidence and rollout notes.
