# MCA UI deployment — 2026-11-22

This branch contains a patch utility for the separate self-hosted TanStack application. The legacy application on main was not deployed or replaced.

Changes: original MCA logo replaces the placeholder icon; mobile language buttons move into the menu; the student panel always links to the catalog. Only SiteHeader.tsx and panel.tsx changed. Educational content, enrollment permissions, and progress calculations are unchanged.

Deployed image: `mca-course-test:ui20261122`.
Source release: `/srv/marka-course-academy/releases/ui-20261122`.
Compose directory: `deploy/hetzner`; `.env` APP_VERSION was persisted as `ui20261122`.

Validation: patch preflight passed against the actual deployed source; Docker production build passed; `docker compose up -d --wait` reported healthy; public catalog loaded both courses and the original MCA image. Desktop logo loading was verified. Authenticated panel and mobile viewport were not verified in-browser (no Academy login on this browser; viewport override did not take effect).

Rollback: run `docker compose up -d --wait` from the unchanged `/srv/marka-course-academy/releases/staging-20261010/deploy/hetzner` with its original environment. The old source release and image remain available.

Outstanding: real payment provider, checkout, verified payment webhook and entitlements, Play Billing integration, remaining Play publication requirements. No successful payment or purchase was claimed. Do not claim the whole Academy is ready for sales based on this UI deployment.
