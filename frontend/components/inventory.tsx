"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";
import { Plus, ArrowRight, ArrowLeftRight, Check, Truck } from "lucide-react";
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
  RecordsTable,
  Form,
  Button,
  ActionLink,
  ErrorBox,
  Loading,
  Status,
  useAction,
} from "./ui";
export function Stock() {
  const stock = useResource("/workspace/inventory"),
    movements = useResource("/movements"),
    products = useResource("/products"),
    [tab, setTab] = useState<"list" | "movements" | "alerts">("list");

  const stockItems = Array.isArray(stock.data)
    ? stock.data
    : Array.isArray(stock.data?.items)
      ? stock.data.items
      : [];
  const totalSKUs = stockItems.length;
  const inStockCount = stockItems.filter((s: Row) => Number(s.available) > 10).length;
  const lowStockCount = stockItems.filter((s: Row) => Number(s.available) > 0 && Number(s.available) <= 10).length;
  const outOfStockCount = stockItems.filter((s: Row) => Number(s.available) <= 0).length;

  const reorderAlerts = stockItems.filter((s: Row) => Number(s.available) <= 10);

  return (
    <div className="inventory-stock-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Stock & Inventory</h1>
          <p className="overview-subtitle">Track live stocks, movements and alerts.</p>
        </div>
        <div className="overview-header-actions">
          <Link href="/inventory/products/new" className="upload-invoice-btn">
            <Plus size={15} />
            + Add Product
          </Link>
        </div>
      </div>

      <ErrorBox error={stock.error} />

      {/* 4 Status Cards */}
      <div className="inventory-status-grid">
        <div className="inv-status-card blue">
          <span className="status-label">Total SKUs</span>
          <span className="status-num">{number(totalSKUs)}</span>
        </div>
        <div className="inv-status-card green">
          <span className="status-label">In Stock</span>
          <span className="status-num">{number(inStockCount)}</span>
        </div>
        <div className="inv-status-card amber">
          <span className="status-label">Low Stock</span>
          <span className="status-num">{number(lowStockCount)}</span>
        </div>
        <div className="inv-status-card red">
          <span className="status-label">Out of Stock</span>
          <span className="status-num">{number(outOfStockCount)}</span>
        </div>
      </div>

      {/* 3 Tabs */}
      <div className="card-panel">
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px", marginBottom: "16px" }}>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "list" ? "active" : "")}
            onClick={() => setTab("list")}
          >
            Stock List
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "movements" ? "active" : "")}
            onClick={() => setTab("movements")}
          >
            Stock Movements
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "alerts" ? "active" : "")}
            onClick={() => setTab("alerts")}
          >
            Reorder Alerts ({lowStockCount + outOfStockCount})
          </button>
        </div>

        {tab === "list" && (
          <DataTable
            rows={stockItems}
            empty="No products in stock yet"
            columns={[
              {
                key: "name",
                label: "Product",
                render: (s) => (
                  <Link
                    href={s.product_id ? "/inventory/products/" + s.product_id : "#"}
                    className="record-link"
                  >
                    <strong>{s.name}</strong>
                    <small style={{ display: "block", color: "#64748b" }}>{s.sku || "SKU-001"}</small>
                  </Link>
                ),
              },
              {
                key: "available",
                label: "Current Stock",
                numeric: true,
                render: (s) => <strong>{number(s.available)}</strong>,
              },
              {
                key: "reorder_point",
                label: "Reorder Level",
                numeric: true,
                render: (s) => number(s.reorder_point || 20),
              },
              {
                key: "status",
                label: "Status",
                render: (s) => {
                  const qty = Number(s.available);
                  const rop = Number(s.reorder_point || 20);
                  if (qty <= 0) {
                    return <span style={{ color: "#ef4444", fontWeight: 600, fontSize: "12px", background: "#fef2f2", padding: "3px 8px", borderRadius: "9999px" }}>● Out of Stock</span>;
                  }
                  if (qty <= rop) {
                    return <span style={{ color: "#d97706", fontWeight: 600, fontSize: "12px", background: "#fffbeb", padding: "3px 8px", borderRadius: "9999px" }}>● Low Stock</span>;
                  }
                  return <span style={{ color: "#10b981", fontWeight: 600, fontSize: "12px", background: "#ecfdf5", padding: "3px 8px", borderRadius: "9999px" }}>● In Stock</span>;
                },
              },
            ]}
          />
        )}

        {tab === "movements" && (
          <DataTable
            rows={(movements.data || []).slice().reverse()}
            columns={[
              { key: "at", label: "Date", render: (m) => date(m.at) },
              {
                key: "product_id",
                label: "Product",
                render: (m) =>
                  stock.data?.find((s: Row) => s.product_id === m.product_id)?.name || m.product_id?.slice(0, 8),
              },
              {
                key: "kind",
                label: "Movement",
                render: (m) => m.kind.replaceAll("_", " "),
              },
              {
                key: "qty",
                label: "Units",
                numeric: true,
                render: (m) => (
                  <strong style={{ color: Number(m.qty) >= 0 ? "#10b981" : "#ef4444" }}>
                    {Number(m.qty) > 0 ? `+${m.qty}` : m.qty}
                  </strong>
                ),
              },
              { key: "reason", label: "Reason" },
            ]}
          />
        )}

        {tab === "alerts" && (
          <DataTable
            rows={reorderAlerts}
            empty="No reorder alerts at this time"
            columns={[
              {
                key: "name",
                label: "Product",
                render: (s) => (
                  <Link
                    href={s.product_id ? "/inventory/products/" + s.product_id : "#"}
                    className="record-link"
                  >
                    <strong>{s.name}</strong>
                    <small style={{ display: "block", color: "#64748b" }}>{s.sku}</small>
                  </Link>
                ),
              },
              {
                key: "available",
                label: "Current Stock",
                numeric: true,
                render: (s) => <strong>{number(s.available)}</strong>,
              },
              {
                key: "reorder_point",
                label: "Reorder Level",
                numeric: true,
                render: (s) => number(s.reorder_point || 20),
              },
              {
                key: "action",
                label: "Action",
                render: (s) => (
                  <Link href="/purchasing/planner" className="button secondary" style={{ fontSize: "11.5px", padding: "4px 10px" }}>
                    Add to Planner
                  </Link>
                ),
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}
export function StockForm() {
  const w = useWorkspace(),
    router = useRouter(),
    query = useSearchParams(),
    products = useResource("/products"),
    movements = useResource("/movements");
  const kind = query.get("kind") || "adjustment",
    movement = query.get("movement"),
    original = movements.data?.find((m: Row) => m.id === movement);
  return (
    <>
      <PageHeader
        title={
          movement
            ? "Correct stock movement"
            : kind === "count"
              ? "Record stock count"
              : "Post stock adjustment"
        }
        description="Counts record physical evidence. Adjustments explicitly change stock and require a reason."
        back="/inventory/stock"
      />
      <Panel title="Stock evidence" className="form-panel">
        <Form
          key={movement || kind}
          button={movement ? "Append correction" : "Record stock evidence"}
          fields={[
            {
              key: "product_id",
              label: "Product",
              required: true,
              value: original?.product_id,
              options: (products.data || []).map((p: Row) => ({
                value: p.id,
                label: p.name,
              })),
            },
            {
              key: "kind",
              label: "Entry type",
              required: true,
              value: kind,
              options: [
                { value: "count", label: "Physical count" },
                { value: "adjustment", label: "Signed stock adjustment" },
                { value: "opening", label: "Opening stock" },
              ],
            },
            {
              key: "qty",
              label:
                kind === "count"
                  ? "Counted base units"
                  : "Signed base units (+ add, − remove)",
              type: "number",
              required: true,
              value: original?.qty,
            },
            {
              key: "reserved",
              label: "Reserved base units (count only)",
              type: "number",
              value: 0,
            },
            {
              key: "on_order",
              label: "Known external on-order units (count only)",
              type: "number",
              value: 0,
            },
            {
              key: "reason",
              label: "Reason / count reference",
              type: "textarea",
              required: true,
            },
          ]}
          onSubmit={async (v) => {
            await w.api(
              movement ? "/movements/" + movement + "/reverse" : "/inventory",
              "POST",
              v,
            );
            w.setNotice("Stock evidence recorded");
            router.push("/inventory/stock");
          }}
        />
      </Panel>
    </>
  );
}
export function Transfers() {
  return (
    <>
      <PageHeader
        title="Branch transfers"
        description="Track stock from dispatch to destination, including goods in transit."
        action={
          <ActionLink href="/inventory/transfers/new">
            <Plus size={16} />
            New transfer
          </ActionLink>
        }
      />
      <Panel>
        <RecordsTable
          path="/workspace/transfers"
          columns={[
            {
              key: "number",
              label: "Transfer",
              render: (t) => (
                <Link
                  className="record-link"
                  href={"/inventory/transfers/" + t.id}
                >
                  {t.number}
                </Link>
              ),
            },
            {
              key: "branch_id",
              label: "Source branch",
              render: (t) => <BranchName id={t.branch_id} />,
            },
            {
              key: "destination_id",
              label: "Destination",
              render: (t) => <BranchName id={t.destination_id} />,
            },
            {
              key: "created",
              label: "Requested",
              render: (t) => date(t.created),
            },
            {
              key: "status",
              label: "Status",
              render: (t) => <Status value={t.status} />,
            },
          ]}
        />
      </Panel>
    </>
  );
}
function BranchName({ id }: { id: string }) {
  const w = useWorkspace();
  return <>{w.branches.find((b) => b.id === id)?.name || id.slice(0, 8)}</>;
}
export function TransferForm() {
  const w = useWorkspace(),
    router = useRouter(),
    products = useResource("/products"),
    [lines, setLines] = useState<Row[]>([{ product_id: "", qty: 1 }]);
  return (
    <>
      <PageHeader
        title="Request a branch transfer"
        description="Select a source branch in the top bar. Stock moves only when the transfer is dispatched."
        back="/inventory/transfers"
      />
      <Panel title="Transfer request" className="form-panel">
        <Form
          button="Create transfer request"
          fields={[
            {
              key: "destination_id",
              label: "Destination branch",
              required: true,
              options: w.branches
                .filter((b) => b.id !== w.branch)
                .map((b) => ({ value: b.id, label: b.name })),
            },
          ]}
          onSubmit={async (v) => {
            const t = await w.api("/workspace/transfers", "POST", {
              ...v,
              lines,
            });
            w.setNotice("Transfer requested");
            router.push("/inventory/transfers/" + t.id);
          }}
        >
          <div className="section-heading">
            <h3>Products to transfer</h3>
            <Button
              variant="secondary"
              onClick={() => setLines([...lines, { product_id: "", qty: 1 }])}
            >
              <Plus size={16} />
              Add product
            </Button>
          </div>
          {lines.map((l, i) => (
            <div className="editable-line" key={i}>
              <label>
                Product
                <select
                  aria-label={`Transfer product ${i + 1}`}
                  required
                  value={l.product_id}
                  onChange={(e) =>
                    setLines(
                      lines.map((x, n) =>
                        n === i ? { ...x, product_id: e.target.value } : x,
                      ),
                    )
                  }
                >
                  <option value="">Choose…</option>
                  {products.data?.map((p: Row) => (
                    <option key={p.id} value={p.id}>
                      {p.name}
                    </option>
                  ))}
                </select>
              </label>
              <label>
                Base units
                <input
                  aria-label={`Transfer quantity ${i + 1}`}
                  type="number"
                  required
                  min=".0001"
                  step="any"
                  value={l.qty}
                  onChange={(e) =>
                    setLines(
                      lines.map((x, n) =>
                        n === i ? { ...x, qty: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
            </div>
          ))}
        </Form>
      </Panel>
    </>
  );
}
export function TransferDetail() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    resource = useResource("/workspace/transfers/" + id),
    products = useResource("/products"),
    action = useAction(resource.reload);
  const t = resource.data;
  async function change(a: string) {
    try {
      await action.run("/workspace/transfers/" + id + "/transition", "POST", {
        version: t.version,
        action: a,
      });
    } catch {}
  }
  if (!t) return <Loading />;
  return (
    <>
      <PageHeader
        title={t.number}
        description="Branch-to-branch stock movement"
        back="/inventory/transfers"
      />
      <ErrorBox error={action.error} />
      <div className="order-banner">
        <Status value={t.status} />
        <BranchName id={t.branch_id} />
        <ArrowRight size={17} />
        <BranchName id={t.destination_id} />
      </div>
      <Panel title="Transfer quantities">
        <DataTable
          searchable={false}
          rows={t.lines.map((l: Row) => ({
            ...l,
            name: products.data?.find((p: Row) => p.id === l.product_id)?.name,
            in_transit: ["dispatched", "partially_received"].includes(t.status)
              ? Number(l.qty) - Number(l.received) - Number(l.shortage)
              : 0,
          }))}
          columns={[
            { key: "name", label: "Product" },
            {
              key: "qty",
              label: "Requested / dispatched",
              numeric: true,
              render: (l) => number(l.qty),
            },
            {
              key: "received",
              label: "Received",
              numeric: true,
              render: (l) => number(l.received),
            },
            {
              key: "in_transit",
              label: "In transit",
              numeric: true,
              render: (l) => number(l.in_transit),
            },
            {
              key: "shortage",
              label: "Approved shortages",
              numeric: true,
              render: (l) => number(l.shortage),
            },
          ]}
        />
        <div className="panel-body button-row">
          {t.status === "requested" && (
            <Button onClick={() => change("approve")}>
              Approve transfer
              <Check size={16} />
            </Button>
          )}
          {t.status === "approved" && (
            <Button onClick={() => change("ordered")}>
              Dispatch stock
              <Truck size={16} />
            </Button>
          )}
          {["requested", "approved"].includes(t.status) && (
            <Button variant="danger" onClick={() => change("cancel")}>
              Cancel transfer
            </Button>
          )}
          {["dispatched", "partially_received"].includes(t.status) && (
            <ActionLink href={"/inventory/transfers/" + id + "/receive"}>
              Receive at destination
              <ArrowRight size={16} />
            </ActionLink>
          )}
        </div>
      </Panel>
      <Panel title="Transfer history">
        <div className="timeline">
          {t.history.map((h: Row, i: number) => (
            <div key={i}>
              <span />
              <div>
                <strong>
                  {h.action === "ordered" ? "Dispatched" : h.action}
                </strong>
                <small>{date(h.at)}</small>
                {h.reason && <p>{h.reason}</p>}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
export function TransferReceiving() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    router = useRouter(),
    resource = useResource("/workspace/transfers/" + id),
    products = useResource("/products"),
    [lines, setLines] = useState<Row[]>([]),
    [key] = useState(() => crypto.randomUUID());
  useEffect(() => {
    if (resource.data)
      setLines(
        resource.data.lines.map((l: Row) => ({
          ...l,
          qty: Number(l.qty) - Number(l.received) - Number(l.shortage),
          shortage: 0,
        })),
      );
  }, [resource.data]);
  const t = resource.data;
  if (!t) return <Loading />;
  return (
    <>
      <PageHeader
        title="Receive branch transfer"
        description={`${t.number} · Select the destination branch in the top bar before confirming.`}
        back={"/inventory/transfers/" + id}
      />
      <Panel title="Destination receiving" className="form-panel">
        <Form
          button="Confirm transfer receipt"
          fields={[
            {
              key: "reason",
              label: "Discrepancy / shortage reason",
              type: "textarea",
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/workspace/transfers/" + id + "/receive", "POST", {
              version: t.version,
              idempotency_key: key,
              lines: lines
                .filter((l) => Number(l.qty) > 0)
                .map((l) => ({ product_id: l.product_id, qty: l.qty })),
              shortages: lines
                .filter((l) => Number(l.shortage) > 0)
                .map((l) => ({ product_id: l.product_id, qty: l.shortage })),
              reason: v.reason,
            });
            w.setNotice("Transfer receipt recorded");
            router.push("/inventory/transfers/" + id);
          }}
        >
          {lines.map((l, i) => (
            <div className="receipt-line" key={l.product_id}>
              <strong>
                {products.data?.find((p: Row) => p.id === l.product_id)?.name}
              </strong>
              <label>
                Received units
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={l.qty}
                  onChange={(e) =>
                    setLines(
                      lines.map((x, n) =>
                        n === i ? { ...x, qty: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
              <label>
                Shortage (manager / owner)
                <input
                  type="number"
                  min="0"
                  step="any"
                  value={l.shortage}
                  onChange={(e) =>
                    setLines(
                      lines.map((x, n) =>
                        n === i ? { ...x, shortage: e.target.value } : x,
                      ),
                    )
                  }
                />
              </label>
            </div>
          ))}
          <div className="info">
            Shortages are explicit stock-loss reconciliations, not destination
            receipts. Only an owner or manager may approve them, with a reason.
          </div>
        </Form>
      </Panel>
    </>
  );
}
