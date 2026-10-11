# Concept A implementation — review evidence

Implemented on `feat/conman-concept-a-ui`, based on documentation branch
`docs/conman-concept-a-codex-kit` at `ac7ef76`. The implementation is intended for
a separate review against that branch while documentation PR #4 is open. No
merge, production deployment, release, or tag has been performed.

## Changes

- `frontend/src/components/BrandLogo.tsx`: canonical stacked, horizontal, and
  mark SVG variants with meaningful or decorative alternative text.
- `frontend/index.html`, `frontend/Dockerfile`: local SVG favicon, theme color,
  and `COPY public ./public` in the Vite build stage.
- `frontend/src/styles.css`, `frontend/src/brand.css`, `frontend/src/main.tsx`:
  semantic navy/blue/teal palette, readable primary actions, focus rings, venue
  grid backgrounds, responsive surfaces, and reduced motion support. Seating
  map colors and solver behavior are unchanged.
- `frontend/src/App.tsx`, `frontend/src/components/AppNavigation.tsx`: top
  navigation, typed original role rules, desktop overflow, current event and
  logout, native modal mobile navigation, focus return, Escape, and skip link.
- `frontend/src/FirstAdminPage.tsx`, `PublicRegistrationPage.tsx`, and
  `PublicPreferencesPage.tsx`: branding and accessibility labels only; existing
  forms, field names, URL/event handling, bootstrap, and preference token flow
  are preserved.
- This report and `evidence/*.png` document the review.

No backend, migration, API client, API types, permission endpoint, dependency
declaration, lockfile, Compose, or GitHub workflow was changed. Runtime QA used a
disposable development database; production data and the existing development
database were not used for test writes.

## Executed checks

| Check | Result |
|---|---|
| `cd frontend && npm install --package-lock=false && npm run build` | Passed; TypeScript and Vite 6.4.4, no dependency or lockfile changes |
| Subsequent `npm run build` after UI and accessibility fixes | Passed |
| `git diff --check` | Passed |
| Frontend Docker build, Node 22 / nginx 1.27 | Passed; cloud CA/proxy configuration supplied in an external build copy, TLS verification retained |
| Six SVG files under `/usr/share/nginx/html/brand` | Present and byte-for-byte equal to canonical sources |
| SVG XML inspection | No script, event-handler attributes, foreignObject, or external resource links |
| Vite development asset requests and favicon | All six SVGs return HTTP 200; local favicon is connected |
| Chromium functional checks | Passed against existing API in isolated `conman_concept_a_qa` PostgreSQL database |
| 320, 390, 768, 1440, 1920px | No page horizontal overflow on auth/public/dashboard screens; all role-allowed sections checked at 320px |
| 200% zoom equivalent | 720×500 CSS-pixel viewport for a 1440×1000 display checked; manual browser toolbar zoom not tested |
| Reduced motion | Preference detected and animation/transition overrides applied |
| Keyboard | Enter login, native mobile focus containment, Tab cycling, Escape, return to menu trigger; desktop overflow Escape |
| Browser runtime / external assets | No uncaught page errors; no external font or logo requests |

The development browser sent the frontend's original `/api/*` requests to the
isolated existing backend via a test harness. No production URL or application
API code was modified. Screenshots contain actual responses from test records,
not hard-coded dashboard metrics. Expected HTTP errors for wrong credentials,
bad event IDs, and invalid preference tokens were deliberately exercised.

## Functional results

- First-run password confirmation, administrator creation, automatic sign-in,
  and setup closing after creation passed.
- Wrong-password error, busy/disabled submit, keyboard login, `api.me` session
  restoration, logout, and HTTP 503 error/retry passed.
- Current event switching through the existing Events page updated the header
  and event context; the original test event was restored.
- `/register?event_id=...` selected the requested event, switching events updated
  the query, and the unauthenticated form submitted a vendor application.
- `/preferences` opened with booking code/e-mail and an invitation token;
  selected zone, draft save, submission, and session-storage restoration passed.
- Invalid preference tokens and registration event IDs showed existing errors.
- Every allowed view mounted on desktop and mobile (66 navigation visits).

| Role | Allowed sections verified |
|---|---|
| ADMIN | Dashboard, Мероприятия, Вендоры, Заявки, Планирование, Рассадка, Check-in, Отчёты, Управление, Пользователи |
| MANAGER | All above except Пользователи |
| REGISTRATION | Dashboard, Мероприятия, Вендоры, Рассадка, Check-in, Отчёты |
| VIEWER | Dashboard, Мероприятия, Вендоры, Заявки, Планирование, Рассадка, Check-in, Отчёты |

## Accessibility evidence

axe-core WCAG 2 A/AA and WCAG 2.1 AA scans found **zero violations** on the
first-admin form, login, dashboard, mobile drawer, registration form, and
submitted preference form after fixes. This is automated coverage, not a full
accessibility certification.

Contrast against white, computed using WCAG relative luminance:

| Use | Ratio |
|---|---|
| Navy headings | 14.05:1 |
| Blue primary action / white text | 5.17:1 |
| Muted body/label text | 6.39:1 |
| Essential control border | 3.56:1 |

Teal is used for canonical artwork and decoration, not small UI text. Selected
navigation includes an underline and `aria-current`, not color alone.

## Screenshots

| Screen | Evidence |
|---|---|
| First administrator | [first-admin.png](evidence/first-admin.png) |
| Sign-in | [login.png](evidence/login.png) |
| Auth error/retry at 320px | [error-retry.png](evidence/error-retry.png) |
| Desktop shell | [navigation-desktop.png](evidence/navigation-desktop.png) |
| Mobile shell at 320px | [navigation-mobile-closed.png](evidence/navigation-mobile-closed.png) |
| Mobile menu/focus at 320px | [navigation-mobile.png](evidence/navigation-mobile.png) |
| Registration | [registration.png](evidence/registration.png) |
| Preference access | [preferences-access.png](evidence/preferences-access.png) |
| Submitted preferences | [preferences.png](evidence/preferences.png) |
| SVGs at 16/32/64/192px | [logo-sizes.png](evidence/logo-sizes.png) |

## Limits and rollout

Firefox, Safari, screen-reader review, manual native 200% browser zoom, real
mobile devices, and all possible long/localized data combinations remain
untested. Existing planning/seating/report sections were opened for every
allowed role; solver generation, drag-and-drop, every administrative mutation,
and financial operations were not exhaustively retested. No PNG/ICO logo
exports were needed because the SVG favicon and canonical artwork load directly.

Production image publication and Portainer rollout remain unexecuted. After
review and separately authorized merge, follow [release and rollback](05_RELEASE_ROLLBACK.md):
build/publish through existing CI, pin the approved image SHA, keep current
volumes, and roll back to the preceding published image tag if necessary. This
UI change requires no database migration or database rollback.
