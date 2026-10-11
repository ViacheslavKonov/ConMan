# Codex: Implement ConMan Concept A branding

**This file is the single start point for Codex.** All materials are tracked in this repository on the docs/conman-concept-a-codex-kit branch until the documentation PR is merged. No application redesign has been performed by this kit alone.

## Copy this as your task

Implement the frontend rebrand for ConMan using approved Concept A: blue/teal palette, CM monogram, hall/booth floor tiles and a location pin. Start by reading AGENTS.md and all files linked from docs/branding/README.md. Use frontend/public/brand/*.svg as canonical logo assets. Study current frontend architecture and avoid changing application logic.

Work in small phases: P0 assets/BrandLogo/favicon/semantic CSS tokens and frontend Dockerfile; P1 sign-in, first-admin and public page branding; P2 adapt existing role-gated sidebar into horizontal desktop navigation with accessible mobile/overflow navigation, preserving every view and current event; P3 build, accessibility QA and screenshots.

Do not invent functional SSO, forgot-password, remember-me or demo metrics. Do not touch backend, migrations, APIs, auth or permissions. Do not deploy or merge. Report changed files, build result, checks, screenshots, limitations, and create an implementation PR for review.

## Execution order
1. [Brand specification](docs/branding/01_BRAND_SPEC.md)
2. [Implementation plan](docs/branding/02_IMPLEMENTATION_PLAN.md)
3. [Codex task prompts](docs/branding/03_CODEX_TASKS.md)
4. [QA checklist](docs/branding/04_QA_CHECKLIST.md)
5. [Release and rollback](docs/branding/05_RELEASE_ROLLBACK.md)
6. [Assets guide](docs/branding/06_ASSET_NOTES.md)

Recommended development branch for implementation: feat/conman-concept-a-ui. Do **not** work directly on main.

## What this upload contains
Planning documents, scalable SVG assets and instructions. The original generated concept board was part of the ChatGPT design package; it is a visual reference, not a production asset. The repository contains code-ready SVG interpretations. Raster exports (PNG/favicon.ico) can be generated from the SVG files by Codex as its first task; SVG is authoritative.

## Checks
Run: cd frontend && npm install && npm run build
Also run: git diff --check
Dockerfile must copy the public directory into Vite build context.
