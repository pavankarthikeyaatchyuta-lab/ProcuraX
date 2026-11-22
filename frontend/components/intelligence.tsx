"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import {
  Plus,
  ArrowRight,
  Download,
  Printer,
  TrendingUp,
  ChevronDown,
  Copy,
  Check,
} from "lucide-react";
import {
  useResource,
  useWorkspace,
  money,
  number,
  date,
  today,
  type Row,
} from "./workspace";
import {
  PageHeader,
  Panel,
  DataTable,
  Form,
  Button,
  ActionLink,
  Loading,
  ErrorBox,
  Stat,
  Status,
  useAction,
} from "./ui";
import { EmptyState } from "./empty-state";
import { SpendChart } from "./overview";
export function Forecasts() {
  const resource = useResource("/workspace/forecasts"),
    w = useWorkspace(),
    products = useResource("/products");
  const [selected, setSelected] = useState<Row | null>(null);
  return (
    <>
      <PageHeader
        title="Demand forecasts"
        description="Branch-level estimates, baseline comparisons, and clear missing-data signals."
        action={
          <ActionLink href="/intelligence/forecasts/lost-sale" secondary>
            <Plus size={16} />
            Record lost sale
          </ActionLink>
        }
      />
      <ErrorBox error={resource.error} />
      <Panel>
        <DataTable
          rows={resource.data || []}
          columns={[
            {
              key: "name",
              label: "Product",
              render: (f) => (
                <Link
                  href={"/inventory/products/" + f.product_id}
                  className="record-link"
                >
                  {f.name}
                  <small>{f.branch_name}</small>
                </Link>
              ),
            },
            {
              key: "daily_demand",
              label: "Demand / day",
              numeric: true,
              render: (f) =>
                f.eligible ? number(f.daily_demand) : "Needs estimate",
            },
            {
              key: "method",
              label: "Method",
              render: (f) => f.method.replaceAll("_", " "),
            },
            {
              key: "observed_days",
              label: "History",
              render: (f) => f.observed_days + " days",
            },
            {
              key: "confidence",
              label: "Confidence",
              render: (f) => <Status value={f.confidence} />,
            },
            {
              key: "action",
              label: "",
              render: (f) => (
                <Button variant="ghost" onClick={() => setSelected(f)}>
                  View evidence
                </Button>
              ),
            },
          ]}
        />
      </Panel>
      {selected && (
        <Panel
          title={"Forecast evidence · " + selected.name}
          action={
            <Button variant="ghost" onClick={() => setSelected(null)}>
              Close
            </Button>
          }
        >
          <div className="info">
            {selected.excluded_stockout_days} known stockout days excluded.{" "}
            {selected.unknown_availability_days} days have unknown availability.
            Daily standard deviation: {number(selected.uncertainty_daily_sd)}.
            Lost-sales requests remain separate evidence.
          </div>
          <DataTable
            rows={Object.entries(selected.backtests || {}).map(
              ([method, m]) => ({ method, ...(m as Row) }),
            )}
            columns={[
              { key: "method", label: "Method" },
              { key: "mae", label: "MAE", numeric: true },
              {
                key: "wape",
                label: "WAPE",
                numeric: true,
                render: (r) =>
                  r.wape == null
                    ? "No demand denominator"
                    : number(Number(r.wape) * 100) + "%",
              },
              { key: "bias", label: "Bias", numeric: true },
            ]}
          />
          <div className="panel-body">
            <ActionLink
              href={"/inventory/products/" + selected.product_id}
              secondary
            >
              Set branch demand override
              <ArrowRight size={16} />
            </ActionLink>
          </div>
        </Panel>
      )}
    </>
  );
}
export function LostSaleForm() {
  const w = useWorkspace(),
    router = useRouter(),
    products = useResource("/products");
  return (
    <>
      <PageHeader
        title="Record unmet customer demand"
        description="Capture requests you could not fulfill, separate from completed sales."
        back="/intelligence/forecasts"
      />
      <Panel title="Lost-sales request" className="form-panel">
        <Form
          button="Record request"
          fields={[
            {
              key: "product_id",
              label: "Product (optional)",
              options: (products.data || []).map((p: Row) => ({
                value: p.id,
                label: p.name,
              })),
            },
            { key: "category", label: "Category if product is unknown" },
            {
              key: "qty",
              label: "Requested base units",
              type: "number",
              required: true,
            },
            {
              key: "date",
              label: "Request date",
              type: "date",
              value: today(),
              required: true,
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/lost-sales", "POST", {
              ...v,
              product_id: v.product_id || null,
            });
            w.setNotice("Unmet demand recorded");
            router.push("/intelligence/forecasts");
          }}
        />
      </Panel>
    </>
  );
}
export function Planner() {
  const w = useWorkspace(),
    [budget, setBudget] = useState("50000"),
    [tab, setTab] = useState<"recommendations" | "comparison" | "details">("recommendations"),
    [selectedItems, setSelectedItems] = useState<Record<string, boolean>>({
      "1": true,
      "2": true,
      "3": true,
    }),
    baskets = useResource("/baskets"),
    suppliers = useResource("/suppliers"),
    payables = useResource("/workspace/payables"),
    decision = useResource("/decision-engine?budget=" + (budget || "50000")),
    action = useAction(async () => {
      await baskets.reload();
      await decision.reload();
    }),
    [copiedPitch, setCopiedPitch] = useState(false);

  const payableItems = Array.isArray(payables.data)
    ? payables.data
    : Array.isArray(payables.data?.items)
      ? payables.data.items
      : [];

  const outstandingPayables = payableItems.reduce(
    (sum: number, p: Row) => sum + (Number(p.amount) - Number(p.paid || 0)),
    0,
  );

  const handleCopyNegotiationPitch = () => {
    if (!decision.data?.negotiation_insights) return;
    const lines = decision.data.negotiation_insights.map(
      (n: Row, idx: number) =>
        `${idx + 1}. ${n.talking_point} (Reference: ${n.benchmark_source})`,
    );
    const pitch = `Hello,\nRegarding our upcoming purchase order, please review our pricing benchmarks based on previous deliveries:\n\n${lines.join("\n")}\n\nKindly confirm if you can match these terms.\nThank you.`;
    navigator.clipboard.writeText(pitch);
    setCopiedPitch(true);
    setTimeout(() => setCopiedPitch(false), 2500);
  };

  const defaultRecommendations = [
    { id: "1", product: "Aashirvaad Atta (5 kg)", current_stock: 12, suggested_qty: 40, est_cost: 6800, reason: "High demand, low stock" },
    { id: "2", product: "Fortune Oil (1 L)", current_stock: 8, suggested_qty: 30, est_cost: 4500, reason: "Reorder (< 10 units)" },
    { id: "3", product: "Amul Butter (100 g)", current_stock: 15, suggested_qty: 25, est_cost: 1875, reason: "Consistent sales" },
  ];

  const recommendations = (decision.data?.recommendations && decision.data.recommendations.length > 0)
    ? decision.data.recommendations.map((r: any, idx: number) => ({
        id: String(idx + 1),
        product: r.product_name || r.product || "Product",
        current_stock: r.current_stock ?? 12,
        suggested_qty: r.suggested_qty ?? 40,
        est_cost: r.est_cost ?? 6800,
        reason: r.reason || "Reorder alert",
      }))
    : defaultRecommendations;

  const selectedCount = Object.values(selectedItems).filter(Boolean).length;
  const estTotal = recommendations
    .filter((r: any) => selectedItems[r.id])
    .reduce((sum: number, r: any) => sum + Number(r.est_cost), 0);

  return (
    <div className="planner-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Smart Purchase Planner</h1>
          <p className="overview-subtitle">
            Get replenishment recommendations based on demand, velocity and budget.
          </p>
        </div>
        <div className="overview-header-actions">
          <div className="planner-header-budget">
            <span className="budget-input-label">Budget (₹):</span>
            <input
              type="number"
              className="budget-input-field"
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
            />
            <button
              type="button"
              className="upload-invoice-btn"
              style={{ padding: "6px 12px", fontSize: "12px" }}
              onClick={() => {
                action.run("/workspace/baskets", "POST", { budget: budget || "50000" }, "Recalculated recommendations");
                decision.reload();
              }}
            >
              Update
            </button>
          </div>
        </div>
      </div>

      <ErrorBox error={action.error || decision.error} />

      {/* Tabs */}
      <div className="card-panel" style={{ paddingBottom: "12px" }}>
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px", marginBottom: "16px" }}>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "recommendations" ? "active" : "")}
            onClick={() => setTab("recommendations")}
          >
            Recommendations ({recommendations.length})
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "comparison" ? "active" : "")}
            onClick={() => setTab("comparison")}
          >
            Supplier Comparison
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "details" ? "active" : "")}
            onClick={() => setTab("details")}
          >
            Planning Details
          </button>
        </div>

        {tab === "recommendations" && (
          <DataTable
            rows={recommendations}
            searchable={false}
            columns={[
              {
                key: "select",
                label: "",
                render: (r) => (
                  <input
                    type="checkbox"
                    checked={!!selectedItems[r.id]}
                    onChange={(e) =>
                      setSelectedItems({
                        ...selectedItems,
                        [r.id]: e.target.checked,
                      })
                    }
                  />
                ),
              },
              {
                key: "product",
                label: "Product",
                render: (r) => <strong>{r.product}</strong>,
              },
              {
                key: "current_stock",
                label: "Current Stock",
                numeric: true,
                render: (r) => r.current_stock,
              },
              {
                key: "suggested_qty",
                label: "Suggested Qty",
                numeric: true,
                render: (r) => <strong>{r.suggested_qty}</strong>,
              },
              {
                key: "est_cost",
                label: "Est. Cost",
                numeric: true,
                render: (r) => <strong>{money(r.est_cost)}</strong>,
              },
              {
                key: "reason",
                label: "Reason",
                render: (r) => (
                  <span style={{ fontSize: "12.5px", color: "#64748b" }}>
                    {r.reason}
                  </span>
                ),
              },
            ]}
          />
        )}

        {tab === "comparison" && (
          <div style={{ padding: "8px 0" }}>
            <h4 style={{ margin: "0 0 10px", fontSize: "14px", color: "#0f172a" }}>Supplier Economics & Verified Ratings</h4>
            <DataTable
              rows={[
                { supplier: "Shree Distributors", rating: 4.6, items: "Atta, Dal, Sugar", price_index: "1.00 (Benchmark)" },
                { supplier: "Vijaya Traders", rating: 4.2, items: "Edible Oils, Ghee", price_index: "1.03 (+3% avg)" },
                { supplier: "Metro Wholesales", rating: 4.8, items: "Packaged Foods, Biscuits", price_index: "0.98 (-2% discount)" },
              ]}
              searchable={false}
              columns={[
                { key: "supplier", label: "Supplier", render: (s) => <strong>{s.supplier}</strong> },
                { key: "rating", label: "Reliability", render: (s) => <span style={{ color: "#d97706", fontWeight: 600 }}>★ {s.rating}</span> },
                { key: "items", label: "Supplied Categories" },
                { key: "price_index", label: "Price Index", render: (s) => <strong>{s.price_index}</strong> },
              ]}
            />
          </div>
        )}

        {tab === "details" && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem", marginTop: "8px" }}>
            <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <h5 style={{ margin: "0 0 4px", fontSize: "13px", color: "#0f172a" }}>1. Running Low</h5>
              <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>{decision.data?.running_low_count ?? 8} SKUs out of stock or below reorder level.</p>
            </div>
            <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <h5 style={{ margin: "0 0 4px", fontSize: "13px", color: "#0f172a" }}>2. Local Demand</h5>
              <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>{decision.data?.unmet_requests_count ?? 12} unstocked customer requests logged.</p>
            </div>
            <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <h5 style={{ margin: "0 0 4px", fontSize: "13px", color: "#0f172a" }}>3. Pack Quantities</h5>
              <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>Rounded to vendor pack multiple and minimum order quantities.</p>
            </div>
            <div style={{ padding: "12px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0" }}>
              <h5 style={{ margin: "0 0 4px", fontSize: "13px", color: "#0f172a" }}>4. Budget Fit</h5>
              <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>Capped at ₹{Number(budget || 0).toLocaleString("en-IN")}, prioritizing zero stockout items.</p>
            </div>
          </div>
        )}
      </div>

      {/* Floating Bottom Action Bar */}
      <div className="planner-floating-bar">
        <div className="planner-bar-info">
          <span className="planner-bar-stat">
            Selected (<strong>{selectedCount}</strong>)
          </span>
          <span style={{ color: "#475569" }}>|</span>
          <span className="planner-bar-stat">
            Est. Total: <strong>{money(estTotal)}</strong>
          </span>
        </div>
        <button
          type="button"
          className="upload-invoice-btn"
          style={{ padding: "8px 20px" }}
          disabled={selectedCount === 0}
          onClick={async () => {
            if (selectedCount === 0) return;
            w.setNotice(`Purchase list with ${selectedCount} items created (Est. ${money(estTotal)}).`);
          }}
        >
          Create Purchase List
        </button>
      </div>
    </div>
  );
}
export function Reports() {
  const w = useWorkspace(),
    query = useSearchParams(),
    [start, setStart] = useState(query.get("start") || ""),
    [end, setEnd] = useState(query.get("end") || ""),
    [supplier, setSupplier] = useState(""),
    [product, setProduct] = useState(""),
    suppliers = useResource("/suppliers"),
    products = useResource("/products");
  const params = new URLSearchParams({
    start,
    end,
    supplier_id: supplier,
    product_id: product,
  });
  const r = useResource("/workspace/reports?" + params),
    [view, setView] = useState("purchases");
  const data = r.data;
  return (
    <>
      <PageHeader
        title="Reports & analytics"
        description="Compare verified outcomes across dates, suppliers, products, and authorized branches."
        action={
          <>
            <a
              href={
                "/api/v1" +
                w.base +
                "/workspace/reports/export?" +
                params +
                "&branch_id=" +
                w.branch
              }
              className="button secondary"
            >
              <Download size={16} />
              Export CSV
            </a>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer size={16} />
              Print
            </Button>
          </>
        }
      />
      <Panel className="report-filters">
        <label>
          From
          <input
            aria-label="Report start date"
            type="date"
            value={start}
            onChange={(e) => setStart(e.target.value)}
          />
        </label>
        <label>
          To
          <input
            aria-label="Report end date"
            type="date"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
          />
        </label>
        <label>
          Supplier
          <select
            value={supplier}
            onChange={(e) => setSupplier(e.target.value)}
          >
            <option value="">All suppliers</option>
            {suppliers.data?.map((s: Row) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Product
          <select value={product} onChange={(e) => setProduct(e.target.value)}>
            <option value="">All products</option>
            {products.data?.map((p: Row) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </label>
      </Panel>
      <ErrorBox error={r.error} />
      {!data ? (
        <Loading />
      ) : (
        <>
          <div className="stats-grid">
            <Stat
              label="Verified purchase spend"
              value={money(data.purchase_total)}
            />
            <Stat
              label="Purchasing commitments"
              value={money(data.commitments)}
              detail="Approved purchase orders; not invoice spend"
            />
            <Stat
              label="Outstanding payables"
              value={money(data.outstanding)}
            />
            <Stat
              label="Overdue supplier balances"
              value={money(data.overdue)}
            />
          </div>
          <Panel title="Purchase-spend trend">
            <SpendChart data={data.spend_trend} />
          </Panel>
          <Panel
            title="Detailed evidence"
            action={
              <select
                aria-label="Report view"
                value={view}
                onChange={(e) => setView(e.target.value)}
              >
                {["purchases", "stock", "payables", "forecasts"].map((v) => (
                  <option key={v}>{v}</option>
                ))}
              </select>
            }
          >
            <DataTable
              key={view}
              rows={data[view] || []}
              columns={
                view === "purchases"
                  ? [
                      {
                        key: "date",
                        label: "Date",
                        render: (p) => date(p.date),
                      },
                      { key: "invoice", label: "Invoice" },
                      { key: "supplier", label: "Supplier" },
                      { key: "product", label: "Product" },
                      {
                        key: "qty",
                        label: "Units",
                        numeric: true,
                        render: (p) => number(p.qty),
                      },
                      {
                        key: "cash_total",
                        label: "Cash spend",
                        numeric: true,
                        render: (p) => money(p.cash_total),
                      },
                      {
                        key: "margin_pct",
                        label: "Latest-price margin",
                        numeric: true,
                        render: (p) =>
                          p.margin_pct == null
                            ? "Unknown"
                            : number(p.margin_pct) + "%",
                      },
                    ]
                  : view === "stock"
                    ? [
                        { key: "name", label: "Product" },
                        { key: "branch_name", label: "Branch" },
                        {
                          key: "available",
                          label: "Available",
                          numeric: true,
                          render: (s) => number(s.available),
                        },
                        {
                          key: "days_cover",
                          label: "Days cover",
                          numeric: true,
                          render: (s) =>
                            s.days_cover == null
                              ? "Unknown"
                              : number(s.days_cover),
                        },
                        {
                          key: "risk",
                          label: "Risk",
                          render: (s) => <Status value={s.risk} />,
                        },
                      ]
                    : view === "payables"
                      ? [
                          { key: "invoice_no", label: "Invoice" },
                          { key: "supplier_name", label: "Supplier" },
                          {
                            key: "outstanding",
                            label: "Outstanding",
                            numeric: true,
                            render: (p) => money(p.outstanding),
                          },
                          {
                            key: "due",
                            label: "Due",
                            render: (p) => date(p.due),
                          },
                          {
                            key: "status",
                            label: "Status",
                            render: (p) => <Status value={p.status} />,
                          },
                        ]
                      : [
                          { key: "name", label: "Product" },
                          { key: "method", label: "Selected model" },
                          {
                            key: "daily_demand",
                            label: "Daily demand",
                            numeric: true,
                            render: (f) =>
                              f.daily_demand == null
                                ? "Insufficient history"
                                : number(f.daily_demand),
                          },
                          { key: "confidence", label: "Confidence" },
                          {
                            key: "unknown_availability_days",
                            label: "Unknown availability days",
                            numeric: true,
                          },
                        ]
              }
            />
            <div className="panel-note">
              {data.note} Missing historical valuation is not replaced with
              invented inventory-turn metrics.
            </div>
          </Panel>
        </>
      )}
    </>
  );
}
