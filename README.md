# Vyaya · AI Procurement Intelligence Platform for MSMEs

As part of this project, we are developing an AI-based Procurement Intelligence Platform called **Vyaya**, mainly focused on helping small businesses manage their purchasing and inventory activities more effectively. The platform is designed to bring different business operations together in one place, making it easier for shop owners to manage supplier bills, sales, products, stock and customer requirements.

The current prototype includes a business dashboard with options to upload supplier bills, record sales, add products, log customer requests and manage purchasing activities. It also includes dedicated sections for inventory management, purchase planning and procurement intelligence. The planned intelligent features include identifying unusual supplier price changes, detecting possible profit losses, suggesting products based on customer demand and helping shop owners make better purchasing decisions through an AI assistant.

The main aim of Vyaya is to reduce the effort involved in managing everyday business activities and help small business owners make decisions based on their business records rather than relying only on manual calculations and personal experience.

---

## Key Core Modules & Capabilities

1. **Live Business Operations & Quick POS**:
   - Fast counter sales entry (`+ Record Quick Sale`) with immediate stock deduction and real-time ledger auditing.
   - One-click supplier invoice and bill upload (`PDF`, `images`, and `GST e-invoice JSON`) with OCR extraction.
   - Product catalog management with SKU unit conversion and pack multiple support.

2. **Module 1: Invoice Intelligence & Price Anomaly Detection**:
   - Robust extraction of line items, units, and tax allocations.
   - Historical cost tracking and sudden supplier price surge detection.

3. **Module 2: Transaction-Safe Inventory Management**:
   - Real-time stock movement ledger (purchases increment, sales decrement, counts reconcile).
   - Reversal and replacement movements for strict accounting auditing.

4. **Module 3: Smart Replenishment & Demand Forecasting**:
   - Stockout-aware reorder formula: $Q = \max(0, d(L+R) + S - I - P)$.
   - Pack size and supplier Minimum Order Quantity (MOQ) rounding.

5. **Module 4: Local Market Demand Intelligence**:
   - **Unmet Customer Demand Register**: Captures shopper requests for unstocked items.
   - **Product Opportunity Scoring**: Multidimensional scoring ($S = 0.4 S_{freq} + 0.25 S_{cat} + 0.25 S_{margin} - 0.1 S_{risk}$) forecasting trial revenue.
   - **Assortment Gap Analysis & Seasonal Signals**: Highlights categories with limited variety and alerts on upcoming festivals and weather trends.

6. **Module 5: Profit Leak Detector**:
   - Uncovers unpassed purchase cost increases, below-cost retail sales, and supplier price divergence.
   - Quantifies monthly rupee leakage and preserves the gross margin vs. net profit accounting distinction.

7. **Module 6: Grounded AI Business Assistant**:
   - Factual natural-language Q&A engine grounded in verified store SQL records (zero hallucinations).
   - Multi-lingual support: **English**, **తెలుగు (Telugu)**, and **हिन्दी (Hindi)** with expandable evidence drawers and database citations.

8. **Module 7: Cash-Aware Unified Decision Engine**:
   - 7-point purchasing decision matrix within declared cash budget.
   - Auto-generated factual supplier negotiation talking points with one-click copy.

9. **Real-Time Architecture & Zero-Data Mode**:
   - Bi-directional WebSocket synchronization (`/api/v1/ws/{id}`) with dynamic live tickers ("just now", "14s ago").
   - 100% clean slate capability with zero default data required and Linear/Stripe-styled empty states.

---

## Start on Windows

Install Docker Desktop with its Linux engine, then run PowerShell in this folder:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose up --build -d
docker compose logs -f api
```

Open [the application](http://localhost:3000). Demo email: `owner@vyaya.local`. Its random password is the `DEMO_PASSWORD` in your private `.env`. The seed command does not change existing credentials. The demo contains synthetic products, supplier quotes, 84 days of sales, purchase history, stock counts and delivery evidence. It is isolated from real businesses.

First builds download sizeable images. ClamAV must download its signature database before uploads work; check `docker compose ps` for scanner health. Database migrations and seeding run before the API health check succeeds. The worker and scheduler wait for that check.

`docker compose stop` preserves data. Do not use `down -v` unless you intend to destroy the database, documents and queue volumes. Only the app/API/scanner bind to localhost; database and Redis are private to the Compose network.

## Try the complete workflow

1. Sign in to Asha Daily Mart. Explore the readiness checklist, stockout and price-change signals.
2. In Products, review exact size, variant and pack identity. Use aliases only after verifying equivalence. In Suppliers & prices, inspect quotations, dated costs and delivery scorecards.
3. In Inventory, inspect the current count and ledger; record a physical count or a signed adjustment with a reason. Count discrepancies are evidence, not automatic stock changes. Correcting a movement appends reversal and replacement entries.
4. In Imports & review, download a template, preview a CSV/XLSX, map columns and commit. A validation error rolls back the entire import. Stable `source_key` values make transaction imports repeatable. Import catalog data before transactions.
5. Enable EU OCR consent in Settings, upload an invoice and review it beside the original. GST e-invoice JSON bypasses OCR. Confirm supplier, totals, product mapping and units before verification. Each line's `factor` converts the invoice quantity to base units. Allocate invoice-level charges across lines explicitly. Unreconciled totals block posting.
6. In Replenishment, inspect methods, backtest errors, missing availability history and manual-demand overrides. Capture unmet customer requests separately from sales.
7. Create a basket with a cash budget. Edit quantities/suppliers, confirm prices, then **Recalculate & save**. Approval requires stock evidence no older than 24 hours and valid constraints.
8. In standalone mode, approval and CSV export work without Zoho. For live writeback, connect and sync Zoho, reconcile every product's opening stock and switch authority. An owner then explicitly creates draft orders from an approved basket.
9. Record delivery evidence against a basket to measure observed supplier performance and comparable realized cost reduction. Delivery evidence alone does not post inventory; verified purchases or Zoho do that.

## Real-business setup

Enable your authenticator in Settings before creating a real business. Use encrypted host storage (for example BitLocker), including backups, before entering real data. Demo owners can exercise the workflow without MFA; real-business owner mutations require it. Add reviewer/owner accounts in Settings. No public registration is enabled.

For local administrative recovery:

```powershell
docker compose exec api python -m app.cli create-user --email person@example.com
docker compose exec api python -m app.cli grant --email person@example.com --business BUSINESS_ID --role reviewer
docker compose exec api python -m app.cli reset-mfa --email person@example.com
```

The recovery command requires local server access, revokes sessions and forces re-enrollment before further real-business owner actions. Preserve `TOKEN_ENCRYPTION_KEY` in a password manager; losing it makes saved OAuth/MFA secrets unreadable.

## Zoho Inventory

Create a Zoho server-based OAuth client. Register this exact redirect URI:

```text
http://localhost:3000/api/v1/zoho/callback
```

Set `ZOHO_CLIENT_ID` and `ZOHO_CLIENT_SECRET` in `.env`, then recreate the API/worker/scheduler with `docker compose up -d`. Use Settings → Connect Zoho India → Choose organization → Sync now. The API also supports `.com`, `.eu` and `.com.au` data centers through the `region` parameter. OAuth uses one-time, session-bound state and encrypted refresh tokens. See [official OAuth documentation](https://www.zoho.com/inventory/api/v1/oauth/) and [purchase-order API](https://www.zoho.com/inventory/api/v1/purchaseorders/).

Sync imports items, suppliers, stock, outstanding orders and up to 180 days of finalized sales/bills and supported credits. It paginates, refreshes tokens, backs off reads on throttling, and updates corrected/voided source transactions. Missing credit permissions, invoice-level charges and unit-conversion requirements are visible reconciliation gaps. Current snapshots are authoritative in Zoho mode; historical movements not returned by the source are not fabricated.

The connector deliberately blocks draft writeback when it cannot safely represent the quote: missing product/vendor mappings, unmapped GST tax ID, alternate Zoho unit groups or freight-bearing quotes. Resolve these in Zoho/manual draft entry before ordering. It never calls issue/send endpoints. On a write timeout or unconfirmed response, it stores an uncertain attempt, searches the unique reference on a subsequent explicit retry, and blocks a second POST if no unique result is found. Inspect Zoho manually when reconciliation remains ambiguous.

**Live credential checks are not automated by the demo.** A real authorized organization and an explicitly approved test basket are required to verify sync and PO creation. Do not connect demo products to a production organization.

## Google invoice extraction and upload scanning

Create an Invoice Parser processor in the `eu` location. Put a least-privilege service-account JSON at `secrets/google.json`, enable Document AI, and set:

```text
GOOGLE_DOCUMENT_AI_PROCESSOR=projects/PROJECT/locations/eu/processors/PROCESSOR
```

Only EU processor resource names are accepted. Set business processing consent in Settings. OCR failures remain in Activity with a safe error and an explicit retry action. Invoice review permits manual entry when extraction is unavailable. Files are private and require a valid business session to retrieve.

All uploads, including spreadsheets and JSON, require a live ClamAV scan. Unsupported signatures, invalid images and over-limit files are rejected. CSV/XLSX uploads are capped at 10 MB and 10,000 rows, XLSX expansion is limited, and CSV exports escape spreadsheet-formula prefixes.

## Development without building containers

Node 20.9+ and Python 3.13+ are supported. A SQLite database is used if `DATABASE_URL` is absent. PostgreSQL remains the Compose default. The Compose scanner can be used from native development:

```powershell
docker compose up -d scanner
python -m venv .venv
.\.venv\Scripts\python -m pip install -r backend/requirements.lock
Set-Location backend
..\.venv\Scripts\python -m app.cli init
..\.venv\Scripts\python -m app.cli seed
..\.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
Set-Location frontend
npm ci
npm run dev
```

The backend loads the root `.env`. Without `REDIS_URL`, it uses local background tasks; this mode needs the separate scheduler/Redis for automatic hourly sync and retention. Use Compose for durable queue processing. Real data remains subject to the same encrypted-host-storage requirement. `requirements.lock` and `package-lock.json` preserve tested dependencies; `requirements.txt` records the direct Python dependency ranges for deliberate upgrades.

## Checks

```powershell
Set-Location backend
..\.venv\Scripts\python -m pytest tests -q
Set-Location ../frontend
npm run typecheck
npm run build
npx playwright install chromium
npm run test:e2e
```

API contracts are available at [OpenAPI docs](http://localhost:8000/docs). Backend tests use temporary databases and mocked external HTTP; they never create real orders. Browser tests require running API/web and `DEMO_PASSWORD` matching that database. See [feature coverage](docs/COVERAGE.md) and the [completed verification report](docs/VERIFICATION.md).

## Operations, backup and privacy

See [operations](docs/OPERATIONS.md) for backup/restore, incident handling, retention and credential rotation. Keep the application bound to localhost. Hosted rollout requires TLS, secure cookies, managed encryption/key management, malware-scan capacity, operational review and a security assessment; this repository does not claim production certification or legal compliance.

Forecast quality, invoice accuracy and savings require representative pilot data. Demo data cannot establish the proposed 95% critical-field extraction target. Estimated contribution is a model-based purchasing priority, not booked profit or guaranteed savings.
