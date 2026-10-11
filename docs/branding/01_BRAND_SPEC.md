# ConMan Brand Specification — Concept A

Approved direction: Convention Management. Symbol integrates (1) convention hall table/booth grid, (2) location/seating pin, (3) C + M motif. Modern, orderly, professional yet friendly. Original image reference was a design proposal; code-ready brand artwork is scalable SVG, not a crop.

## Palette

| Token | Hex | Use |
|---|---|---|
| --cm-navy | #0F2D4A | Structural mark, key headings, dark text |
| --cm-blue | #2563EB | Primary action, selected nav, link/focus |
| --cm-teal | #14B8A6 | Pin and non-textual accents |
| --cm-ice | #E0F2FE | Decorative backgrounds |
| --cm-gray | #94A3B8 | Disabled/ornamental icons |
| --cm-ink | #172033 | Body text |
| --cm-muted | #526075 | Secondary text |
| --cm-surface | #FFFFFF | Cards/forms |
| --cm-border | #DFE6EF | Dividers |
| --cm-canvas | #F4F7FB | Page background |
| --cm-danger | #A93636 | Errors |
| --cm-success | #167557 | Successful status |

Define semantic aliases (action-primary, text-primary, focus, border, surface), not scattered hex values. Text contrast >=4.5:1; essential non-text contrast >=3:1. Teal on white is NOT suitable for ordinary small text without verification. Do not recolor danger/success to brand accent.

## Typography and spacing
- Inter, system-ui, Segoe UI, sans-serif. No external font fetch at runtime.
- ConMan wordmark bold, 'Con' navy / 'Man' teal. Subtitle 'CONVENTION MANAGEMENT' uppercase.
- UI body usually 14–16px; avoid 8–11px for important content.
- 8px spacing grid; control targets ideally >=44px; cards radius 10–16px; restrained shadows.

## Logo usages
- Login / first-run: /brand/conman-lockup-stacked.svg, around 180–260px.
- Wide navigation: /brand/conman-lockup-horizontal.svg, around 170–220px.
- Compact navigation: /brand/conman-mark.svg.
- Dark background: /brand/conman-mark-white.svg.
- App icon: /brand/conman-app-icon.svg.
- Browser favicon: /brand/conman-favicon.svg; create .ico/png exports if appropriate.

Brand images need meaningful alt when standalone; alt="" when adjacent visible 'ConMan' text already names the product. At 16px use the simplified favicon; avoid unreadable subtitle.

## Login and public UI
Pale blue-white decorative floor-plan background, white card (max ~420px), stacked brand, existing email/password fields, clear submit/error/loading states, keyboard-visible focus. Do not add mockup-only SSO, password recovery or login-remember checkbox unless implemented end-to-end. First-admin, /register, /preferences use matching brand but preserve their own forms and copy.

## Navigation
Reference concept shows top horizontal menu, while the product currently has a sidebar with 10 views. On desktop display logo, current event, role-allowed tabs with 'Ещё' overflow. On mobile (including 320px) use keyboard-accessible menu/drawer with Escape to dismiss, focus return and aria-expanded; no clipped controls. Keep all role checks and event context. Do NOT use static illustrative sample KPI counters.

## Don't
No API/auth/DB changes. No fake actions. No screenshot-cropped logo. No navigation hiding. No external runtime assets. Don't change registration event selection, public preference token flow, or seating data.
