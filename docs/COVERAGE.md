# Proposal-to-feature coverage

| Capability | Implementation / evidence |
|---|---|
| Business/tenant setup, owner/reviewer permissions | Membership-scoped endpoints, MFA-gated real-owner mutations, Settings account creation |
| CSV/XLSX imports | Templates, column mapping, preview, row errors, atomic rollback and source-key idempotency |
| Structured GST invoices | JSON parsing, IRN/ack metadata preserved; no direct IRP validation claim |
| PDF/photo invoices | ClamAV scan, real EU Document AI client, extraction versions and manual review |
| Human verification | Document preview, editable lines, arithmetic/discount/product/unit validation, version checks |
| Product/variant/pack identities | Canonical attributes, base-unit factors, supplier aliases, exact matching and reviewed fuzzy suggestions |
| Duplicate detection | Document hash plus purchase invoice identity; uploaded/synced evidence linked, conflicting totals blocked |
| Stock ledger | Opening, sales/purchases/returns/adjustments, append-only correction movements |
| Stock authority | Standalone or Zoho snapshots; explicit complete-product reconciliation when switching |
| Inventory visibility | On-hand, reserved, available, on-order, count gap, stock freshness and cover |
| Lost sales | Manual request capture, shown separately from sales |
| Quotations | Net/base-unit price, taxes, freight, pack/MOQ/multiple, lead time, validity, quantity tiers and supplier minimums |
| Supplier scorecards | Receipt sample size, on-time/fulfillment rates and observed lead time; no fabricated ratings |
| Alerts | Percentage changes, median/MAD, alternative suppliers, bank-change verification, stockouts and margin rules |
| Forecasts | Moving average, weekly baseline, exponential smoothing and Croston-SBA; rolling-origin MAE/WAPE/bias; known stockout censoring and unknown-history disclosures |
| Budget purchasing | Deterministic greedy allocation; cash/economic cost separation; constraints rechecked after edits and approval |
| Explanations | Forecast method, demand, available/on-order stock, lead time, price date and cash spend |
| Approval/export | Immutable approved basket input snapshot, feedback, CSV and explicit Zoho draft creation |
| Outcomes | Linked receipts, acceptance, estimated contribution and realized comparable cost reduction; unavailable metrics disclose reasons |
| Audit/security | Sessions, CSRF, origin checks, rate limiting, MFA, encrypted provider secrets, scoped file access and upload scanning |
| Privacy/operations | EU consent, retention, export/deletion, health, failure jobs, scheduler and backup/restore scripts |
| Real connector | OAuth/state/org selection, pagination, refresh, read retries, 180-day sync, uncertain-write reconciliation |

## Verification boundaries

Automated backend tests cover tenant/role/CSRF controls, MFA gating, arithmetic, pack/MOQ/budget/cover rules, duplicate evidence, invoice reconciliation, returns/reversals, atomic imports, malicious uploads, sparse demand, no future data leakage, export privacy, OAuth token refresh, pagination/throttling and ambiguous draft-write recovery. Browser tests exercise the rendered workflow at desktop/mobile sizes.

Live Zoho sync, real Google extraction and actual draft creation remain **unverified until authorized credentials are configured**. Managed OCR quality and the proposal's ≥95% critical-field target require a labeled, supplier-diverse pilot corpus, reported by field and supplier. Demonstration outcomes are synthetic.

Some connector source formats need explicit reconciliation: alternate Zoho unit groups, invoice-level charges and unavailable return APIs. These block unsafe writeback or appear as source gaps. Freight-bearing POs currently require manual draft entry in Zoho. The greedy optimizer satisfies validated constraints but does not claim globally optimal allocation; a supplier group that fails its minimum is excluded and unused budget can remain.

## Expansion roadmap

1. Multi-store, multilingual UI and reconciled hierarchical forecasts after single-store pilot validation.
2. Additional ERP connectors, direct authorized IRP/GSP access and automated quotation/WhatsApp ingestion.
3. Hosted-pilot operations: TLS/secure cookies, managed keys/encryption, independent security review, alerting and onboarding.
4. Bank/payable feeds through eligible partners, separate consent and retention policy.
5. Probabilistic/global forecasting and mixed-integer optimization after measured baseline failures justify them.
6. Cross-shop intelligence and optional assistants only after aggregation/privacy design and separate consent.

Autonomous ordering, accounting, payroll and fraud classification remain outside this MVP. Pricing, staffing and go-to-market figures remain hypotheses from the proposal, not product measurements.
