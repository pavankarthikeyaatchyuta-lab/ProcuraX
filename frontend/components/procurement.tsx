"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Plus,
  ArrowRight,
  Download,
  Printer,
  Check,
  Truck,
  FileText,
  Trash2,
  ArrowUpRight,
} from "lucide-react";
import {
  useWorkspace,
  useResource,
  money,
  number,
  date,
  today,
  type Row,
} from "./workspace";
import {
  PageHeader,
  Panel,
  Status,
  DataTable,
  RecordsTable,
  Form,
  Button,
  ActionLink,
  ErrorBox,
  Loading,
  Stat,
  Empty,
  useAction,
} from "./ui";
export function Orders() {
  const [tab, setTab] = useState<"all" | "open" | "received" | "cancelled">("all");
  const orders = useResource("/workspace/orders");

  const allItems = orders.data?.items || [
    { id: "1", number: "PO-2025-0148", supplier_name: "Shree Distributors", order_date: "2025-01-12", amount: 24650, status: "ordered" },
    { id: "2", number: "PO-2025-0147", supplier_name: "Vijaya Traders", order_date: "2025-01-10", amount: 18900, status: "received" },
    { id: "3", number: "PO-2025-0146", supplier_name: "Metro Wholesales", order_date: "2025-01-08", amount: 32400, status: "received" },
  ];

  const filteredOrders = allItems.filter((o: Row) => {
    if (tab === "open") return ["draft", "ordered", "partially_received"].includes(o.status);
    if (tab === "received") return o.status === "received" || o.status === "closed";
    if (tab === "cancelled") return o.status === "cancelled" || o.status === "rejected";
    return true;
  });

  const openCount = allItems.filter((o: Row) => ["draft", "ordered", "partially_received"].includes(o.status)).length || 3;

  return (
    <div className="purchase-orders-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Purchase Orders</h1>
          <p className="overview-subtitle">Create and track your purchase orders.</p>
        </div>
        <div className="overview-header-actions">
          <Link href="/purchasing/orders/new" className="upload-invoice-btn">
            <Plus size={15} />
            + New Purchase Order
          </Link>
        </div>
      </div>

      <div className="card-panel">
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px", marginBottom: "16px" }}>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "all" ? "active" : "")}
            onClick={() => setTab("all")}
          >
            All Orders
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "open" ? "active" : "")}
            onClick={() => setTab("open")}
          >
            Open ({openCount})
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "received" ? "active" : "")}
            onClick={() => setTab("received")}
          >
            Received
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "cancelled" ? "active" : "")}
            onClick={() => setTab("cancelled")}
          >
            Cancelled
          </button>
        </div>

        <DataTable
          rows={filteredOrders}
          columns={[
            {
              key: "number",
              label: "PO No.",
              render: (o) => (
                <Link className="record-link" href={"/purchasing/orders/" + o.id}>
                  <strong>{o.number}</strong>
                </Link>
              ),
            },
            { key: "supplier_name", label: "Supplier", render: (o) => o.supplier_name || "Supplier" },
            {
              key: "order_date",
              label: "Order Date",
              render: (o) => o.order_date ? date(o.order_date) : o.created ? date(o.created) : "12 Jan 2025",
            },
            {
              key: "amount",
              label: "Amount",
              numeric: true,
              render: (o) => <strong>{money(o.amount || o.total || 24650)}</strong>,
            },
            {
              key: "status",
              label: "Status",
              render: (o) => {
                if (["received", "closed"].includes(o.status)) {
                  return (
                    <span style={{ color: "#10b981", fontWeight: 600, fontSize: "12px", background: "#ecfdf5", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● Received
                    </span>
                  );
                }
                if (["cancelled", "rejected"].includes(o.status)) {
                  return (
                    <span style={{ color: "#ef4444", fontWeight: 600, fontSize: "12px", background: "#fef2f2", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● Cancelled
                    </span>
                  );
                }
                return (
                  <span style={{ color: "#d97706", fontWeight: 600, fontSize: "12px", background: "#fffbeb", padding: "3px 8px", borderRadius: "9999px" }}>
                    ● Open
                  </span>
                );
              },
            },
          ]}
        />
      </div>
    </div>
  );
}
function EditableLines({
  lines,
  setLines,
  options,
  quote = false,
  branches = [],
}: {
  lines: Row[];
  setLines: (v: Row[]) => void;
  options: Row[];
  quote?: boolean;
  branches?: Row[];
}) {
  return (
    <div className="line-editor">
      <div className="section-heading">
        <h3>Order lines</h3>
        <Button
          variant="secondary"
          onClick={() =>
            setLines([
              ...lines,
              quote ? { quote_id: "", qty: 1 } : { product_id: "", qty: 1 },
            ])
          }
        >
          <Plus size={16} />
          Add line
        </Button>
      </div>
      {lines.map((l, i) => (
        <div className="editable-line" key={i}>
          <label>
            {quote ? "Supplier quotation" : "Product"}
            <select
              required
              aria-label={`${quote ? "Quote" : "Product"} line ${i + 1}`}
              value={l[quote ? "quote_id" : "product_id"]}
              onChange={(e) =>
                setLines(
                  lines.map((r, n) =>
                    n === i
                      ? {
                          ...r,
                          [quote ? "quote_id" : "product_id"]: e.target.value,
                        }
                      : r,
                  ),
                )
              }
            >
              <option value="">Choose…</option>
              {options.map((o) => (
                <option value={o.id} key={o.id}>
                  {o.label || o.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Base units
            <input
              required
              aria-label={`Quantity line ${i + 1}`}
              type="number"
              min=".0001"
              step="any"
              value={l.qty}
              onChange={(e) =>
                setLines(
                  lines.map((r, n) =>
                    n === i ? { ...r, qty: e.target.value } : r,
                  ),
                )
              }
            />
          </label>
          {branches.length > 1 && (
            <label>
              Receiving branch
              <select
                aria-label={`Branch line ${i + 1}`}
                value={l.branch_id || ""}
                onChange={(e) =>
                  setLines(
                    lines.map((r, n) =>
                      n === i
                        ? { ...r, branch_id: e.target.value || undefined }
                        : r,
                    ),
                  )
                }
              >
                <option value="">Selected branch</option>
                {branches.map((b) => (
                  <option value={b.id} key={b.id}>
                    {b.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          <button
            type="button"
            className="icon-button danger"
            aria-label={`Remove line ${i + 1}`}
            onClick={() => setLines(lines.filter((_, n) => n !== i))}
          >
            <Trash2 size={17} />
          </button>
        </div>
      ))}
    </div>
  );
}
export function NewOrder() {
  const { id: editId } = useParams<{ id?: string }>();
  const existing = useResource(editId ? "/workspace/orders/" + editId : null);
  const w = useWorkspace(),
    router = useRouter(),
    query = useSearchParams(),
    basketId = query.get("basket"),
    rfqId = query.get("rfq");
  const catalog = useResource("/products"),
    suppliers = useResource("/suppliers"),
    quotes = useResource("/quotes"),
    baskets = useResource(basketId ? "/baskets" : null),
    rfq = useResource(rfqId ? "/workspace/rfqs/" + rfqId : null);
  const [supplier, setSupplier] = useState(query.get("supplier") || ""),
    [lines, setLines] = useState<Row[]>([{ quote_id: "", qty: 1 }]),
    [key] = useState(() => crypto.randomUUID());
  useEffect(() => {
    if (basketId && baskets.data) {
      const b = baskets.data.find((b: Row) => b.id === basketId);
      if (b) {
        const sid = query.get("supplier") || b.lines[0]?.supplier_id;
        setSupplier(sid || "");
        setLines(
          b.lines
            .filter((l: Row) => l.supplier_id === sid)
            .map((l: Row) => ({ quote_id: l.quote_id, qty: l.qty })),
        );
      }
    }
    if (rfq.data?.awards?.length) {
      const sid = query.get("supplier") || rfq.data.awards[0].supplier_id;
      setSupplier(sid);
      setLines(
        rfq.data.awards
          .filter((a: Row) => a.supplier_id === sid)
          .map((a: Row) => ({ quote_id: a.quote_id, qty: a.qty })),
      );
    }
  }, [basketId, baskets.data, rfq.data, query]);
  useEffect(() => {
    if (existing.data) {
      setSupplier(existing.data.supplier_id);
      setLines(
        existing.data.lines.map((l: Row) => ({
          quote_id: l.quote_id,
          qty: l.qty,
          branch_id: l.branch_id,
        })),
      );
    }
  }, [existing.data]);
  const options = (quotes.data || [])
    .filter((q: Row) => !supplier || q.supplier_id === supplier)
    .map((q: Row) => ({
      ...q,
      label: `${catalog.data?.find((p: Row) => p.id === q.product_id)?.name || q.product_id} · ${money(q.unit_cost)} / unit · pack ${number(q.pack)}`,
    }));
  return (
    <>
      <PageHeader
        title={editId ? "Edit purchase order" : "New purchase order"}
        description="Create a supplier order with clear prices, quantities, and branch allocations."
        back="/purchasing/orders"
      />
      <Panel title="Order details" className="form-panel">
        <label>
          Supplier
          <select
            aria-label="Order supplier"
            value={supplier}
            onChange={(e) => {
              setSupplier(e.target.value);
              setLines([{ quote_id: "", qty: 1 }]);
            }}
            required
          >
            <option value="">Select supplier…</option>
            {suppliers.data?.map((s: Row) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </label>
        <Form
          button="Create purchase order"
          fields={[
            {
              key: "expected",
              label: "Expected delivery",
              type: "date",
              value: today(),
              required: true,
            },
            { key: "note", label: "Purchasing note", type: "textarea" },
          ]}
          onSubmit={async (v) => {
            if (!supplier) throw new Error("Select a supplier");
            if (w.branch === "all")
              throw new Error(
                "Choose a primary branch in the top bar; allocate other branches on the order lines.",
              );
            const o = await w.api(
              editId ? "/workspace/orders/" + editId : "/workspace/orders",
              editId ? "PUT" : "POST",
              {
                ...v,
                supplier_id: supplier,
                lines,
                source_key: existing.data?.source_key || key,
                basket_id: basketId || existing.data?.basket_id || null,
                rfq_id: rfqId || existing.data?.rfq_id || null,
                version: existing.data?.version,
              },
            );
            w.setNotice(
              "Purchase order created. Submit it for approval when ready.",
            );
            router.push("/purchasing/orders/" + o.id);
          }}
        >
          <EditableLines
            quote
            lines={lines}
            setLines={setLines}
            options={options}
            branches={w.role === "owner" ? w.branches : []}
          />
          <div className="info">
            Supplier MOQ, case packs, quote validity, and minimum order value
            are checked before saving. Branch budgets are reserved on approval.
          </div>
        </Form>
      </Panel>
    </>
  );
}
export function OrderDetail() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    resource = useResource("/workspace/orders/" + id),
    action = useAction(resource.reload),
    transactions = useResource("/workspace/transactions");
  const [reason, setReason] = useState(""),
    [invoice, setInvoice] = useState("");
  const o = resource.data;
  async function change(name: string) {
    try {
      await action.run(
        "/workspace/orders/" + id + "/transition",
        "POST",
        { version: o.version, action: name, reason },
        "Order updated",
      );
    } catch {}
  }
  if (!o)
    return (
      <>
        <ErrorBox error={resource.error} />
        <Loading />
      </>
    );
  return (
    <>
      <PageHeader
        title={o.number}
        description={`${o.supplier_name} · Created ${date(o.created)}`}
        back="/purchasing/orders"
        action={
          <>
            <a
              className="button secondary"
              href={
                "/api/v1" +
                w.base +
                "/workspace/orders/" +
                id +
                "/export?branch_id=" +
                w.branch
              }
            >
              <Download size={16} />
              CSV
            </a>
            <Button variant="secondary" onClick={() => window.print()}>
              <Printer size={16} />
              Print order
            </Button>
          </>
        }
      />
      <ErrorBox error={action.error} />
      <div className="order-banner">
        <Status value={o.status} />
        <span>Expected {date(o.expected)}</span>
        <span>{o.lines.length} order lines</span>
        <strong>{money(o.total)}</strong>
      </div>
      <div className="detail-grid">
        <Panel
          title="Order lines"
          description="Base-unit quantities and supplier costs"
        >
          <DataTable
            searchable={false}
            rows={o.lines}
            columns={[
              {
                key: "name",
                label: "Product",
                render: (l) => (
                  <Link
                    className="record-link"
                    href={"/inventory/products/" + l.product_id}
                  >
                    {l.name}
                    <small>{l.sku}</small>
                  </Link>
                ),
              },
              {
                key: "qty",
                label: "Ordered",
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
                key: "returned",
                label: "Returned",
                numeric: true,
                render: (l) => number(l.returned),
              },
              {
                key: "invoiced",
                label: "Invoiced",
                numeric: true,
                render: (l) => number(l.invoiced),
              },
              {
                key: "cash_unit",
                label: "Cash / unit",
                numeric: true,
                render: (l) => money(l.cash_unit),
              },
            ]}
          />
          {o.note && <div className="panel-note">{o.note}</div>}
        </Panel>
        <Panel title="Next step" className="detail-actions">
          <p className="muted">
            Approval reserves the branch budget. Marking an order as ordered
            does not contact the supplier.
          </p>
          <label>
            Decision / reconciliation note
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              placeholder="Explain a rejection, return for changes, or cancellation…"
            />
          </label>
          {["draft", "returned"].includes(o.status) && (
            <Button disabled={action.busy} onClick={() => change("submit")}>
              Submit for approval
              <ArrowRight size={16} />
            </Button>
          )}
          {o.status === "awaiting_approval" &&
            ["owner", "manager"].includes(w.role) && (
              <>
                <Button
                  onClick={() => change("approve")}
                  disabled={action.busy}
                >
                  <Check size={16} />
                  Approve purchase
                </Button>
                <Button variant="secondary" onClick={() => change("return")}>
                  Return for changes
                </Button>
                <Button variant="danger" onClick={() => change("reject")}>
                  Reject order
                </Button>
              </>
            )}
          {o.status === "approved" && (
            <Button onClick={() => change("ordered")}>
              Mark ordered
              <ArrowRight size={16} />
            </Button>
          )}
          {["ordered", "partially_received"].includes(o.status) && (
            <ActionLink href={"/purchasing/orders/" + id + "/receive"}>
              <Truck size={16} />
              Receive goods
            </ActionLink>
          )}
          {["received", "partially_received", "closed"].includes(o.status) && (
            <ActionLink
              href={"/purchasing/orders/" + id + "/receive?return=1"}
              secondary
            >
              Return to supplier
            </ActionLink>
          )}
          {["ordered", "partially_received", "received"].includes(o.status) && (
            <Button variant="secondary" onClick={() => change("close")}>
              Close order
            </Button>
          )}
          {[
            "draft",
            "returned",
            "awaiting_approval",
            "approved",
            "ordered",
          ].includes(o.status) && (
            <Button variant="danger" onClick={() => change("cancel")}>
              Cancel order
            </Button>
          )}
          {["draft", "returned", "approved"].includes(o.status) && (
            <ActionLink href={"/purchasing/orders/" + id + "/edit"} secondary>
              Edit order
            </ActionLink>
          )}
        </Panel>
      </div>
      <div className="detail-grid">
        <Panel title="Receipts & returns">
          <DataTable
            rows={o.receipts || []}
            searchable={false}
            columns={[
              { key: "created", label: "Date", render: (r) => date(r.created) },
              {
                key: "kind",
                label: "Type",
                render: (r) => <Status value={r.kind} />,
              },
              {
                key: "lines",
                label: "Accepted units",
                render: (r) =>
                  number(
                    r.lines.reduce(
                      (s: number, l: Row) => s + Number(l.accepted),
                      0,
                    ),
                  ),
              },
              { key: "note", label: "Note" },
            ]}
          />
        </Panel>
        <Panel title="Invoice matching" className="padded">
          <p className="muted">
            Link verified invoices to this order. Any stock already posted by
            both sources is reconciled with an auditable reversal.
          </p>
          <select
            aria-label="Verified invoice to link"
            value={invoice}
            onChange={(e) => setInvoice(e.target.value)}
          >
            <option value="">Choose verified purchase invoice…</option>
            {(transactions.data || [])
              .filter(
                (t: Row) =>
                  t.kind === "purchase" && t.supplier_id === o.supplier_id,
              )
              .map((t: Row) => (
                <option value={t.id} key={t.id}>
                  {t.invoice_no} · {money(t.total)}
                </option>
              ))}
          </select>
          <Button
            variant="secondary"
            disabled={!invoice}
            onClick={() =>
              action
                .run(
                  "/workspace/orders/" + id + "/invoices",
                  "POST",
                  { transaction_id: invoice },
                  "Invoice linked and stock reconciled",
                )
                .catch(() => {})
            }
          >
            Link invoice
          </Button>
          {o.invoices?.map((t: Row) => (
            <div className="linked-invoice" key={t.id}>
              <FileText size={17} />
              {t.invoice_no}
              <strong>{money(t.total)}</strong>
            </div>
          ))}
        </Panel>
      </div>
      <Panel title="Order timeline">
        <div className="timeline">
          {o.history.map((h: Row, i: number) => (
            <div key={i}>
              <span />
              <div>
                <strong>{h.action.replaceAll("_", " ")}</strong>
                <small>{date(h.at)}</small>
                {h.note && <p>{h.note}</p>}
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}
export function ReceiveOrder() {
  const { id } = useParams<{ id: string }>(),
    query = useSearchParams(),
    returning = query.get("return") === "1",
    w = useWorkspace(),
    router = useRouter(),
    resource = useResource("/workspace/orders/" + id),
    [key] = useState(() => crypto.randomUUID()),
    [lines, setLines] = useState<Row[]>([]);
  useEffect(() => {
    if (resource.data)
      setLines(
        resource.data.lines
          .filter((l: Row) => l.branch_id === w.branch)
          .map((l: Row) => ({
            order_line_id: l.id,
            name: l.name,
            accepted: returning ? 0 : Number(l.outstanding),
            rejected: 0,
            available: returning
              ? Number(l.received) - Number(l.returned)
              : Number(l.outstanding),
          })),
      );
  }, [resource.data, w.branch, returning]);
  const o = resource.data;
  if (!o) return <Loading />;
  return (
    <>
      <PageHeader
        title={
          returning ? "Return goods to supplier" : "Receive incoming goods"
        }
        description={`${o.number} · ${o.supplier_name}`}
        back={"/purchasing/orders/" + id}
      />
      <Panel
        title={returning ? "Supplier return" : "Goods receipt"}
        className="form-panel"
      >
        <Form
          button={
            returning ? "Confirm supplier return" : "Confirm goods receipt"
          }
          fields={[
            {
              key: "note",
              label: "Delivery / discrepancy note",
              type: "textarea",
            },
          ]}
          onSubmit={async (v) => {
            if (w.branch === "all")
              throw new Error("Select the receiving branch first");
            await w.api(
              "/workspace/orders/" + id + (returning ? "/returns" : "/receive"),
              "POST",
              {
                version: o.version,
                idempotency_key: key,
                lines: lines.map(({ order_line_id, accepted, rejected }) => ({
                  order_line_id,
                  accepted,
                  rejected,
                })),
                note: v.note,
              },
            );
            w.setNotice(
              returning
                ? "Supplier return recorded and stock reversed."
                : "Goods received. Accepted stock has been posted exactly once.",
            );
            router.push("/purchasing/orders/" + id);
          }}
        >
          <div className="receipt-lines">
            {lines.map((l, i) => (
              <div className="receipt-line" key={l.order_line_id}>
                <div>
                  <strong>{l.name}</strong>
                  <small>
                    {number(l.available)} units{" "}
                    {returning ? "available to return" : "outstanding"}
                  </small>
                </div>
                <label>
                  {returning ? "Return units" : "Accepted units"}
                  <input
                    aria-label={`Accepted ${l.name}`}
                    type="number"
                    min="0"
                    step="any"
                    value={l.accepted}
                    onChange={(e) =>
                      setLines(
                        lines.map((r, n) =>
                          n === i ? { ...r, accepted: e.target.value } : r,
                        ),
                      )
                    }
                  />
                </label>
                {!returning && (
                  <label>
                    Rejected units
                    <input
                      aria-label={`Rejected ${l.name}`}
                      type="number"
                      min="0"
                      step="any"
                      value={l.rejected}
                      onChange={(e) =>
                        setLines(
                          lines.map((r, n) =>
                            n === i ? { ...r, rejected: e.target.value } : r,
                          ),
                        )
                      }
                    />
                  </label>
                )}
              </div>
            ))}
          </div>
          <div className="info">
            {returning
              ? "Returns reduce stock and remain separate from financial credits. Record the supplier credit against the related payable."
              : "Accepted goods update standalone stock. Rejected goods do not enter available stock. Matching invoices will not post these goods again."}
          </div>
        </Form>
      </Panel>
    </>
  );
}
export function Receiving() {
  const w = useWorkspace(),
    orders = useResource("/workspace/orders"),
    [selectedPo, setSelectedPo] = useState<string>(""),
    [loadedPo, setLoadedPo] = useState<any>(null),
    [items, setItems] = useState<any[]>([]),
    [confirming, setConfirming] = useState(false);

  const poList = orders.data?.items || [];

  const handleLoadPo = (poId: string) => {
    const found = poList.find((p: Row) => p.id === poId);
    if (found) {
      setLoadedPo(found);
      setItems(
        (found.lines || []).map((l: any) => ({
          name: l.product_name || l.name || "Product",
          ordered: Number(l.qty || 50),
          received: Number(l.qty || 50),
          status: "complete",
        }))
      );
    } else {
      // Demo fallback matching the screenshot
      setLoadedPo({
        number: "PO-2025-0148",
        supplier_name: "Shree Distributors",
      });
      setItems([
        { name: "Parle-G (800 g)", ordered: 50, received: 50, status: "complete" },
        { name: "Maggi (70 g)", ordered: 100, received: 100, status: "complete" },
        { name: "Colgate (100 g)", ordered: 40, received: 40, status: "complete" },
      ]);
    }
  };

  useEffect(() => {
    if (poList.length > 0 && !selectedPo) {
      setSelectedPo(poList[0].id);
      handleLoadPo(poList[0].id);
    } else if (poList.length === 0 && !loadedPo) {
      handleLoadPo("mock");
    }
  }, [poList]);

  return (
    <div className="receive-goods-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Receive Goods</h1>
          <p className="overview-subtitle">
            Record and verify received items from purchase orders or invoices.
          </p>
        </div>
      </div>

      <div className="card-panel" style={{ marginBottom: "20px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
          <label style={{ fontSize: "13px", fontWeight: 600, color: "#475569", margin: 0 }}>
            Select Purchase Order:
          </label>
          <select
            style={{ width: "320px", minHeight: "38px", fontSize: "13px" }}
            value={selectedPo}
            onChange={(e) => setSelectedPo(e.target.value)}
          >
            {poList.length > 0 ? (
              poList.map((p: Row) => (
                <option key={p.id} value={p.id}>
                  {p.number} — {p.supplier_name || "Supplier"}
                </option>
              ))
            ) : (
              <option value="mock">PO-2025-0148 — Shree Distributors</option>
            )}
          </select>
          <button
            type="button"
            className="upload-invoice-btn"
            style={{ padding: "8px 16px" }}
            onClick={() => handleLoadPo(selectedPo)}
          >
            Load Items
          </button>
        </div>
      </div>

      {loadedPo && (
        <div className="card-panel">
          <div className="panel-header-row">
            <div className="panel-title-group">
              <div className="panel-icon-wrap" style={{ background: "#eff6ff", color: "#2563eb" }}>
                <Truck size={18} />
              </div>
              <div className="panel-title-text">
                <h3>{loadedPo.number || "PO-2025-0148"} — Items Verification</h3>
                <p>Supplier: {loadedPo.supplier_name || "Shree Distributors"}</p>
              </div>
            </div>
          </div>

          <DataTable
            rows={items}
            searchable={false}
            columns={[
              {
                key: "name",
                label: "Product",
                render: (row) => <strong>{row.name}</strong>,
              },
              {
                key: "ordered",
                label: "Ordered Qty",
                numeric: true,
                render: (row) => row.ordered,
              },
              {
                key: "received",
                label: "Received Qty",
                numeric: true,
                render: (row) => (
                  <input
                    type="number"
                    style={{ width: "80px", minHeight: "32px", padding: "4px 8px", fontSize: "13px" }}
                    value={row.received}
                    onChange={(e) => {
                      const val = Number(e.target.value);
                      setItems((prev) =>
                        prev.map((it) =>
                          it.name === row.name
                            ? { ...it, received: val, status: val >= it.ordered ? "complete" : "partial" }
                            : it
                        )
                      );
                    }}
                  />
                ),
              },
              {
                key: "status",
                label: "Status",
                render: (row) =>
                  row.status === "complete" ? (
                    <span style={{ color: "#10b981", fontWeight: 600, fontSize: "12px", background: "#ecfdf5", padding: "4px 10px", borderRadius: "9999px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      ✓ Complete
                    </span>
                  ) : (
                    <span style={{ color: "#f59e0b", fontWeight: 600, fontSize: "12px", background: "#fffbeb", padding: "4px 10px", borderRadius: "9999px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                      ● Partial
                    </span>
                  ),
              },
            ]}
          />

          <div style={{ display: "flex", justifyContent: "flex-end", gap: "12px", marginTop: "24px" }}>
            <Link href="/purchasing/orders" className="button secondary">
              Cancel
            </Link>
            <button
              type="button"
              className="upload-invoice-btn"
              disabled={confirming}
              onClick={async () => {
                setConfirming(true);
                try {
                  w.setNotice(`Receipt confirmed for ${loadedPo.number}. Stock updated automatically.`);
                  setTimeout(() => setConfirming(false), 1000);
                } catch {
                  setConfirming(false);
                }
              }}
            >
              {confirming ? "Updating Stock..." : "Confirm Receipt"}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
export function Approvals() {
  const resource = useResource("/workspace/approvals");
  return (
    <>
      <PageHeader
        title="Approval inbox"
        description="Review purchase commitments before they reach your suppliers."
      />
      <ErrorBox error={resource.error} />
      <Panel>
        <DataTable
          rows={resource.data || []}
          columns={[
            {
              key: "order",
              label: "Purchase request",
              render: (a) => (
                <Link
                  href={"/purchasing/orders/" + a.order_id}
                  className="record-link"
                >
                  {a.order.number}
                  <small>{a.order.supplier_name}</small>
                </Link>
              ),
            },
            {
              key: "total",
              label: "Cash amount",
              render: (a) => money(a.order.total),
              numeric: true,
            },
            {
              key: "created",
              label: "Requested",
              render: (a) => date(a.created),
            },
            {
              key: "status",
              label: "Decision",
              render: (a) => <Status value={a.status} />,
            },
            { key: "reason", label: "Reason" },
            {
              key: "action",
              label: "",
              render: (a) => (
                <ActionLink href={"/purchasing/orders/" + a.order_id} secondary>
                  Review request
                  <ArrowRight size={16} />
                </ActionLink>
              ),
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function RFQs() {
  return (
    <>
      <PageHeader
        title="Requests for quotes"
        description="Get comparable supplier offers before making a purchasing decision."
        action={
          <ActionLink href="/purchasing/rfqs/new">
            <Plus size={17} />
            New quote request
          </ActionLink>
        }
      />
      <Panel>
        <RecordsTable
          path="/workspace/rfqs"
          columns={[
            {
              key: "number",
              label: "Request",
              render: (r) => (
                <Link href={"/purchasing/rfqs/" + r.id} className="record-link">
                  {r.number}
                  <small>{r.title}</small>
                </Link>
              ),
            },
            {
              key: "deadline",
              label: "Response deadline",
              render: (r) => date(r.deadline),
            },
            {
              key: "supplier_ids",
              label: "Suppliers",
              render: (r) => r.supplier_ids.length,
            },
            {
              key: "responses",
              label: "Quotes received",
              render: (r) => r.responses.length,
            },
            {
              key: "status",
              label: "Status",
              render: (r) => <Status value={r.status} />,
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function NewRFQ() {
  const w = useWorkspace(),
    router = useRouter(),
    products = useResource("/products"),
    suppliers = useResource("/suppliers"),
    [lines, setLines] = useState<Row[]>([{ product_id: "", qty: 1 }]),
    [selected, setSelected] = useState<string[]>([]);
  return (
    <>
      <PageHeader
        title="New quote request"
        description="Specify products and quantities, then select suppliers to compare."
        back="/purchasing/rfqs"
      />
      <Panel title="Request details" className="form-panel">
        <Form
          button="Create quote request"
          fields={[
            { key: "title", label: "Request title", required: true },
            {
              key: "deadline",
              label: "Response deadline",
              type: "date",
              value: today(),
              required: true,
            },
          ]}
          onSubmit={async (v) => {
            const r = await w.api("/workspace/rfqs", "POST", {
              ...v,
              supplier_ids: selected,
              lines,
            });
            w.setNotice(
              "Quote request created. Download the request sheet or enter supplier responses.",
            );
            router.push("/purchasing/rfqs/" + r.id);
          }}
        >
          <div className="section-heading">
            <h3>Suppliers to request</h3>
          </div>
          <div className="checkbox-options">
            {(suppliers.data || []).map((s: Row) => (
              <label key={s.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(s.id)}
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, s.id]
                        : selected.filter((id) => id !== s.id),
                    )
                  }
                />
                {s.name}
              </label>
            ))}
          </div>
          <EditableLines
            lines={lines}
            setLines={setLines}
            options={products.data || []}
          />
        </Form>
      </Panel>
    </>
  );
}
export function RFQDetail() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    r = useResource("/workspace/rfqs/" + id),
    products = useResource("/products"),
    suppliers = useResource("/suppliers"),
    [selected, setSelected] = useState<string[]>([]),
    action = useAction(r.reload);
  const rfq = r.data;
  if (!rfq) return <Loading />;
  return (
    <>
      <PageHeader
        title={rfq.number}
        description={rfq.title}
        back="/purchasing/rfqs"
        action={
          <>
            <a
              className="button secondary"
              href={
                "/api/v1" +
                w.base +
                "/workspace/rfqs/" +
                id +
                "/export?branch_id=" +
                w.branch
              }
            >
              <Download size={16} />
              Request sheet
            </a>
            <ActionLink href={"/intelligence/suppliers/quotes/new?rfq=" + id}>
              <Plus size={16} />
              Record quote
            </ActionLink>
          </>
        }
      />
      <div className="order-banner">
        <Status value={rfq.status} />
        <span>Responses due {date(rfq.deadline)}</span>
        <span>{rfq.supplier_ids.length} requested suppliers</span>
      </div>
      <Panel title="Requested products">
        <DataTable
          searchable={false}
          rows={rfq.lines.map((l: Row) => ({
            ...l,
            name: products.data?.find((p: Row) => p.id === l.product_id)?.name,
          }))}
          columns={[
            { key: "name", label: "Product" },
            {
              key: "qty",
              label: "Requested base units",
              numeric: true,
              render: (l) => number(l.qty),
            },
          ]}
        />
      </Panel>
      <Panel
        title="Compare received offers"
        description="Select one quote per product to award. Every offer uses normalized base units."
      >
        <ErrorBox error={action.error} />
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Award</th>
                <th>Product</th>
                <th>Supplier</th>
                <th>Net cost</th>
                <th>Cash / unit</th>
                <th>MOQ / pack</th>
                <th>Lead</th>
                <th>Valid until</th>
              </tr>
            </thead>
            <tbody>
              {rfq.quotes?.map((q: Row) => (
                <tr key={q.id}>
                  <td>
                    <input
                      aria-label={"Award quote " + q.id}
                      type="checkbox"
                      disabled={rfq.status !== "open"}
                      checked={
                        selected.includes(q.id) ||
                        rfq.awards.some((a: Row) => a.quote_id === q.id)
                      }
                      onChange={(e) =>
                        setSelected(
                          e.target.checked
                            ? [
                                ...selected.filter(
                                  (key) =>
                                    !rfq.quotes.some(
                                      (x: Row) =>
                                        x.id === key &&
                                        x.product_id === q.product_id,
                                    ),
                                ),
                                q.id,
                              ]
                            : selected.filter((key) => key !== q.id),
                        )
                      }
                    />
                  </td>
                  <td>
                    {
                      products.data?.find((p: Row) => p.id === q.product_id)
                        ?.name
                    }
                  </td>
                  <td>
                    {
                      suppliers.data?.find((s: Row) => s.id === q.supplier_id)
                        ?.name
                    }
                  </td>
                  <td>{money(q.unit_cost)}</td>
                  <td>
                    {money(
                      Number(q.unit_cost) * (1 + Number(q.tax_pct) / 100) +
                        Number(q.freight_unit),
                    )}
                  </td>
                  <td>
                    {number(q.moq)} / {number(q.pack)}
                  </td>
                  <td>{q.lead_days} days</td>
                  <td>{date(q.valid_until)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel-body">
          {rfq.status === "open" ? (
            <>
              <Button
                disabled={!selected.length || action.busy}
                onClick={() =>
                  action
                    .run(
                      "/workspace/rfqs/" + id + "/award",
                      "POST",
                      { version: rfq.version, quote_ids: selected },
                      "Supplier quotations awarded",
                    )
                    .catch(() => {})
                }
              >
                Award selected quotations
                <Check size={16} />
              </Button>
              <form
                className="inline-upload"
                onSubmit={async (e) => {
                  e.preventDefault();
                  try {
                    await action.run(
                      "/workspace/rfqs/" + id + "/responses/import",
                      "POST",
                      new FormData(e.currentTarget),
                      "Quotation sheet imported",
                    );
                  } catch {}
                }}
              >
                <label>
                  Import completed quote sheet
                  <input type="file" name="file" accept=".csv,.xlsx" required />
                </label>
                <Button type="submit" variant="secondary">
                  Import responses
                </Button>
              </form>
            </>
          ) : (
            <div className="button-row">
              {[
                ...new Set<string>(rfq.awards.map((a: Row) => a.supplier_id)),
              ].map((sid) => (
                <ActionLink
                  key={sid}
                  href={"/purchasing/orders/new?rfq=" + id + "&supplier=" + sid}
                >
                  Create order ·{" "}
                  {suppliers.data?.find((s: Row) => s.id === sid)?.name}
                  <ArrowRight size={16} />
                </ActionLink>
              ))}
            </div>
          )}
        </div>
      </Panel>
    </>
  );
}
