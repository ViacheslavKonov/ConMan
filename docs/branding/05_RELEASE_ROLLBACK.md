# ConMan Concept A — release and rollback

This documentation PR does not deploy anything. UI implementation must be separately reviewed and merged before production release.

## Pre-release
1. Verify frontend build and repository CI.
2. Review screenshots + docs/branding/04_QA_CHECKLIST.md.
3. Confirm backend, migrations, API types and permissions are unaffected.
4. Verify frontend/Dockerfile copies public and all brand files appear under /usr/share/nginx/html after building.
5. Review GHCR workflow .github/workflows/docker-images.yml and compose.yaml. Do not reintroduce build: entries into production compose.

## Release (only after separate approval)
- Merge approved implementation PR.
- Existing GitHub Actions publishes image tags to GHCR; wait for the correct build/checks.
- For Portainer, prefer pinned CONMAN_IMAGE_TAG equal to a published git commit SHA over latest.
- Set only the image tag in existing stack; pull updated images and redeploy through authorized operator.
- Do not destroy volumes/databases, remove the existing stack, or modify secrets for a logo change.
- Confirm login, selected event, /register, /preferences and navigation immediately after rollout.

## Rollback
- Revert to previous known-good CONMAN_IMAGE_TAG (previous published GHCR image), pull/redeploy.
- Branding change should not require schema migration or database rollback.
- If release included unexpected backend changes, stop and escalate; do not guess DB rollback commands.

## Safety and provenance
- No production commands are authorized in this task.
- Original concept rendering is a creative reference, not canonical production artwork; see 06_ASSET_NOTES.md.
