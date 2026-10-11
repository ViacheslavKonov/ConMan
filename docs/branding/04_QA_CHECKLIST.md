# Concept A — UI regression and accessibility checklist

Use this after each phase and report pass/fail/not-tested; never claim an unrun test passed.

## Build and assets
- [ ] cd frontend && npm install && npm run build
- [ ] git diff --check
- [ ] public brand SVGs reachable in Vite dev and the built Docker image
- [ ] Browser tab SVG favicon loads; no broken assets in devtools
- [ ] No new external font or CDN requests; no console errors
- [ ] Check SVG rendering and logo clarity at 16, 32, 64, 192px

## User flows
- [ ] Session restored with api.me and correct unauthorized/failed states
- [ ] Login success/error/busy and keyboard submit
- [ ] First-run admin bootstrap works once, validation/error state preserved
- [ ] Logout still clears session
- [ ] Event selection and event-specific data remain intact
- [ ] /register works for selected event, direct URL, invalid event and submission
- [ ] /preferences works for access link, draft, submitted, invalid token and empty state
- [ ] Dashboard metrics come only from real API, never mockup numbers
- [ ] All existing planning/seating pages and forms remain functional

## Roles and navigation
- [ ] ADMIN sees allowed views
- [ ] MANAGER sees allowed views
- [ ] REGISTRATION sees allowed views, protected views remain absent
- [ ] VIEWER sees allowed views, protected views remain absent
- [ ] Every allowed view reachable in desktop topbar/overflow and mobile menu
- [ ] Current event and logout accessible at all breakpoints
- [ ] Keyboard Tab/Shift+Tab, Enter/Space, Escape and focus return
- [ ] Active selection is identifiable without color alone

## Visual accessibility
- [ ] 320, 390, 768, 1440 and 1920px widths, no accidental horizontal scroll
- [ ] 200% browser zoom and long event names
- [ ] WCAG AA text contrast >=4.5:1, essential icons/controls >=3:1
- [ ] Focus ring visible; hit targets sufficiently large on mobile
- [ ] Prefers-reduced-motion respected
- [ ] Images have meaningful alt or empty alt if decorative
- [ ] Form labels/errors usable with assistive technologies
- [ ] No dead/fake interactive controls

## Evidence
Provide screenshots of login, first-run, app shell desktop/mobile, registration, preferences; record commands and results and any untested items.
