# Verification · 10 November 2026

The application is running at http://localhost:3000 using the production Docker build. PostgreSQL, Redis, API, RQ worker, scheduler, web and ClamAV are running; the database/API/scanner health checks pass.

## Automated checks

- **21 backend tests pass** on native Python 3.14 and inside the Python 3.13 API container. They cover money/pack constraints, duplicate invoices, standalone/mirrored stock, returns/reversals, invoice corrections, tenant isolation, CSRF/roles, session-bound MFA, atomic imports, sparse forecasts/no future-data leakage, private exports, failed uploads, read retry/pagination, partial supplier failures, uncertain-write reconciliation and late OCR results racing human review.
- TypeScript checking passes. The Next.js production build succeeds, including the Linux standalone image. Dependency versions are recorded in the Python and npm lockfiles.
- **Desktop and mobile end-to-end tests pass against the production Docker app.** The flow signs in, opens every main view, uploads a GST invoice through the real scanner, verifies its mapping and arithmetic, creates a basket, confirms prices, recalculates and approves. It also checks Escape dismissal, page identity, no framework error overlay, no unexpected browser console/runtime errors, and no page-level horizontal overflow. Expected unauthenticated `/auth/me` responses are excluded from console-error assertions.

## Browser and visual QA

Browser plugin not available; used Playwright with installed Chrome. Desktop viewport: 1280 × 720. Mobile: iPhone 13 profile, 390 × 844, device pixel ratio 3. Screenshots preserve full-page or element content beyond the viewport.

The user explicitly selected a practical dashboard without generated visual concepts. There is no accepted ImageGen reference to compare against; visual QA checks the agreed dashboard requirements and rendered behavior rather than claiming concept fidelity.

Inspected screenshots using `view_image`:

- [Desktop overview](screenshots/overview-desktop.png)
- [Mobile overview](screenshots/overview-mobile.png)
- [Desktop approved basket](screenshots/basket-desktop.png)
- [Mobile approved basket](screenshots/basket-mobile.png)

Checked navigation hierarchy, heading/control typography, green/white palette, table and monetary alignment, status labels, spacing, modal behavior, responsive navigation, horizontal table scrolling, missing-evidence labels and clear distinction between estimated benefits and realized savings. Fixed sidebar overflow, overly narrow mobile basket descriptions, a login-profile transition crash and a stale-basket refresh race. Dense tables intentionally scroll horizontally on phones, with a visible swipe instruction. No generated concept/copy-diff comparison applies. No material visual blocker remains in the checked workflow.

## Restore rehearsal

The backup script now quiesces application writers automatically to keep database/document snapshots consistent, then restarts previously running services. A concurrent-write rehearsal exposed the need for this change.

The final backup was restored into a separate temporary PostgreSQL database. Matching counts: 1 business, 8 products, 8 documents, 8 baskets and 48 audit events. SHA-256 checks passed for all 8 restored document originals. The rehearsal database was removed; the primary database remained intact. All services were restarted and API/database/queue health was rechecked.

## Unverified external behavior and limits

Zoho and Google Document AI credentials are not configured. Real authorized Zoho sync, actual cloud extraction, measured invoice-field accuracy and real draft-order creation therefore remain unverified. Provider tests use mocked external responses. No real orders were created. Synthetic demo outcomes do not establish pilot savings or the proposal's 95% extraction target.

Known connector boundaries—alternate Zoho units, invoice-level landed charges, freight-bearing writeback and unavailable credit permissions—are documented in README and COVERAGE. A production network deployment still needs the separately planned hosting/security work. The test runner emits one upstream Starlette/httpx deprecation warning; it does not affect the passing checks.
