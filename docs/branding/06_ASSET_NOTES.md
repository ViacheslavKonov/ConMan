# ConMan Concept A — asset inventory and rendering

Canonical production resources shipped by this GitHub upload:

| URL from Vite site root | Purpose |
|---|---|
| /brand/conman-mark.svg | Responsive colored CM + grid + pin |
| /brand/conman-mark-white.svg | Single-color version for dark background |
| /brand/conman-lockup-stacked.svg | Login / first admin |
| /brand/conman-lockup-horizontal.svg | Menu / app header |
| /brand/conman-app-icon.svg | App tile / PWA |
| /brand/conman-favicon.svg | Small browser favicon |

Located in frontend/public/brand. Use as-is or adapt via deliberate design review; the SVGs are a simplified **vector interpretation**, not an exact tracing of the illustration. Avoid cropping a generated raster image into production UI.

The original design board, PNG icon sizes (192/512) and favicon.ico were included in the downloadable ChatGPT ZIP but were not transferred in this initial GitHub documentation upload. Codex can create raster exports from the canonical SVGs, add them to the implementation PR, and verify small-size legibility. Do not create references in index.html to non-existent files.

IMPORTANT: frontend/Dockerfile currently copies src but not public to its build stage. Add COPY public ./public as part of CM-BRAND-01 or production icons will 404.

Display semantics: stacked or horizontal standalone logo alt='ConMan — Convention Management'; if brand name is already adjacent in text, use alt='' to avoid duplicate announcement. Use stable paths, no CDN or external scripts. Verify SVG contains no JS, event handlers or remote references.

Palette: navy #0F2D4A, blue #2563EB, teal #14B8A6, ice #E0F2FE, muted gray #94A3B8. Graphics are static and scalable.
