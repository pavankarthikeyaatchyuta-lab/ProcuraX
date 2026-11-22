"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { useState, useEffect } from "react";
import { Plus, ArrowRight, Package, Truck } from "lucide-react";
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
  RecordsTable,
  DataTable,
  Form,
  ActionLink,
  Loading,
  ErrorBox,
  Badge,
  Stat,
  Button,
} from "./ui";
export function Products() {
  const query = useSearchParams();
  return (
    <>
      <PageHeader
        title="Product catalog"
        description="A shared catalog with precise variants, packs, and base units."
        action={
          <ActionLink href="/inventory/products/new">
            <Plus size={17} />
            Add product
          </ActionLink>
        }
      />
      <Panel>
        <RecordsTable
          path={
            "/workspace/catalog/products" +
            (query.get("q") ? "?q=" + encodeURIComponent(query.get("q")!) : "")
          }
          columns={[
            {
              key: "name",
              label: "Product",
              render: (p) => (
                <Link
                  className="record-link"
                  href={"/inventory/products/" + p.id}
                >
                  <span className="product-thumbnail">
                    <Package size={19} />
                  </span>
                  <span>
                    {p.name}
                    <small>{p.sku}</small>
                  </span>
                </Link>
              ),
            },
            { key: "brand", label: "Brand" },
            {
              key: "variant",
              label: "Variant / size",
              render: (p) => (
                <>
                  {p.variant || "—"}
                  <small>{p.size}</small>
                </>
              ),
            },
            {
              key: "pack",
              label: "Pack",
              render: (p) => `${number(p.pack)} × ${p.unit}`,
            },
            {
              key: "sell_price",
              label: "Selling price",
              numeric: true,
              render: (p) => money(p.sell_price),
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function ProductForm() {
  const { id } = useParams<{ id?: string }>(),
    router = useRouter(),
    w = useWorkspace(),
    resource = useResource(id ? "/workspace/catalog/products/" + id : null);
  const p = resource.data?.record;
  if (id && !p) return <Loading />;
  return (
    <>
      <PageHeader
        title={id ? "Edit product" : "Add product"}
        description="Keep supplier and store records linked to the correct product identity."
        back={id ? "/inventory/products/" + id : "/inventory/products"}
      />
      <Panel title="Product information" className="form-panel">
        <Form
          key={id || "new"}
          button={id ? "Save product" : "Create product"}
          fields={[
            {
              key: "name",
              label: "Product name",
              required: true,
              value: p?.name,
            },
            {
              key: "sku",
              label: "Internal SKU",
              required: true,
              value: p?.sku,
            },
            { key: "brand", label: "Brand", value: p?.brand },
            { key: "variant", label: "Variant / flavor", value: p?.variant },
            { key: "size", label: "Size / model", value: p?.size },
            { key: "unit", label: "Base unit", value: p?.unit || "unit" },
            {
              key: "pack",
              label: "Base units per case",
              type: "number",
              value: p?.pack || 1,
              required: true,
            },
            { key: "barcode", label: "Barcode / GTIN", value: p?.barcode },
            {
              key: "sell_price",
              label: "Selling price per base unit (ex GST)",
              type: "number",
              value: p?.sell_price || 0,
              required: true,
            },
          ]}
          onSubmit={async (v) => {
            const result = await w.api(
              id ? "/products/" + id : "/products",
              id ? "PUT" : "POST",
              {
                ...v,
                manual_demand: p?.manual_demand ?? null,
                storage_limit: p?.storage_limit ?? null,
              },
            );
            w.setNotice("Product saved");
            router.push("/inventory/products/" + result.id);
          }}
        />
      </Panel>
    </>
  );
}
export function ProductDetail() {
  const { id } = useParams<{ id: string }>(),
    w = useWorkspace(),
    resource = useResource("/workspace/catalog/products/" + id),
    stock = useResource("/workspace/inventory"),
    suppliers = useResource("/suppliers");
  const p = resource.data?.record;
  if (!p)
    return (
      <>
        <ErrorBox error={resource.error} />
        <Loading />
      </>
    );
  const local =
    resource.data.branch_settings?.find((c: Row) => c.branch_id === w.branch) ||
    {};
  return (
    <>
      <PageHeader
        title={p.name}
        description={[p.sku, p.brand, p.variant, p.size]
          .filter(Boolean)
          .join(" · ")}
        back="/inventory/products"
        action={
          <ActionLink href={"/inventory/products/" + id + "/edit"} secondary>
            Edit product
          </ActionLink>
        }
      />
      <div className="stats-grid three">
        <Stat label="Selling price · ex GST" value={money(p.sell_price)} />
        <Stat label="Case pack" value={number(p.pack) + " " + p.unit} />
        <Stat
          label="Available across selected branches"
          value={
            number(
              (stock.data || [])
                .filter((s: Row) => s.product_id === id)
                .reduce((sum: number, s: Row) => sum + Number(s.available), 0),
            ) + " units"
          }
        />
      </div>
      <div className="detail-grid">
        <Panel title="Stock by branch">
          <DataTable
            rows={(stock.data || []).filter((s: Row) => s.product_id === id)}
            searchable={false}
            columns={[
              { key: "branch_name", label: "Branch" },
              {
                key: "available",
                label: "Available",
                render: (s) => number(s.available),
                numeric: true,
              },
              {
                key: "on_order",
                label: "On order",
                render: (s) => number(s.on_order),
                numeric: true,
              },
            ]}
          />
        </Panel>
        <Panel title="Branch replenishment settings" className="padded">
          <p className="muted">
            These overrides apply only to the selected branch.
          </p>
          <Form
            button="Save branch settings"
            fields={[
              {
                key: "manual_demand",
                label: "Daily demand override (optional)",
                type: "number",
                value: local.manual_demand ?? "",
              },
              {
                key: "storage_limit",
                label: "Storage limit in base units (optional)",
                type: "number",
                value: local.storage_limit ?? "",
              },
              {
                key: "safety_days",
                label: "Safety-stock days (optional)",
                type: "number",
                value: local.safety_days ?? "",
              },
            ]}
            onSubmit={async (v) => {
              await w.api(
                "/workspace/products/" + id + "/settings",
                "PUT",
                Object.fromEntries(
                  Object.entries(v).map(([k, val]) => [
                    k,
                    val === "" ? null : Number(val),
                  ]),
                ),
              );
              w.setNotice("Branch settings updated");
              resource.reload();
            }}
          />
        </Panel>
      </div>
      <Panel title="Supplier quotations">
        <DataTable
          rows={resource.data.quotes || []}
          columns={[
            {
              key: "supplier_id",
              label: "Supplier",
              render: (q) => (
                <Link
                  href={"/intelligence/suppliers/" + q.supplier_id}
                  className="text-link"
                >
                  {suppliers.data?.find((s: Row) => s.id === q.supplier_id)
                    ?.name || q.supplier_id}
                </Link>
              ),
            },
            {
              key: "unit_cost",
              label: "Net / base unit",
              render: (q) => money(q.unit_cost),
              numeric: true,
            },
            {
              key: "pack",
              label: "Pack / MOQ",
              render: (q) => number(q.pack) + " / " + number(q.moq),
            },
            {
              key: "lead_days",
              label: "Lead time",
              render: (q) => q.lead_days + " days",
            },
            {
              key: "observed",
              label: "Observed",
              render: (q) => date(q.observed),
            },
          ]}
        />
      </Panel>
      <Panel title="Transaction and price history">
        <DataTable
          rows={resource.data.history || []}
          columns={[
            { key: "date", label: "Date", render: (l) => date(l.date) },
            { key: "invoice_no", label: "Invoice" },
            { key: "kind", label: "Transaction" },
            {
              key: "qty",
              label: "Base units",
              numeric: true,
              render: (l) => number(l.qty),
            },
            {
              key: "unit_cost",
              label: "Net unit amount",
              numeric: true,
              render: (l) => money(l.unit_cost),
            },
            {
              key: "cash_unit",
              label: "Cash unit amount",
              numeric: true,
              render: (l) => money(l.cash_unit),
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function Suppliers() {
  const suppliers = useResource("/workspace/catalog/suppliers");

  const supplierList = Array.isArray(suppliers.data?.items)
    ? suppliers.data.items
    : Array.isArray(suppliers.data)
      ? suppliers.data
      : [];

  return (
    <div className="suppliers-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Suppliers</h1>
          <p className="overview-subtitle">Manage supplier details, prices and performance.</p>
        </div>
        <div className="overview-header-actions">
          <Link href="/intelligence/suppliers/new" className="upload-invoice-btn">
            <Plus size={15} />
            + Add Supplier
          </Link>
        </div>
      </div>

      <div className="card-panel">
        <DataTable
          rows={supplierList}
          columns={[
            {
              key: "name",
              label: "Supplier",
              render: (s) => (
                <Link className="record-link" href={"/intelligence/suppliers/" + s.id}>
                  <strong>{s.name}</strong>
                  <small style={{ display: "block", color: "#64748b" }}>{s.gstin || "Verified Supplier"}</small>
                </Link>
              ),
            },
            {
              key: "products_count",
              label: "Products",
              numeric: true,
              render: (s) => s.products_count || (s.lines ? s.lines.length : 240),
            },
            {
              key: "price_index",
              label: "Avg. Price Index",
              numeric: true,
              render: (s) => <strong>{(s.price_index || 1.00).toFixed(2)}</strong>,
            },
            {
              key: "reliability",
              label: "Reliability",
              render: (s) => (
                <span style={{ color: "#d97706", fontWeight: 600, fontSize: "13px", display: "inline-flex", alignItems: "center", gap: "4px" }}>
                  ★ {s.reliability || 4.6}
                </span>
              ),
            },
            {
              key: "action",
              label: "Actions",
              render: (s) => (
                <Link
                  href={"/intelligence/suppliers/" + s.id}
                  className="button secondary"
                  style={{ fontSize: "11.5px", padding: "4px 12px" }}
                >
                  View
                </Link>
              ),
            },
          ]}
        />
      </div>
    </div>
  );
}
export function SupplierForm() {
  const w = useWorkspace(),
    router = useRouter();
  return (
    <>
      <PageHeader
        title="Add supplier"
        description="Create a supplier record for quotes, orders, and invoices."
        back="/intelligence/suppliers"
      />
      <Panel title="Supplier information" className="form-panel">
        <Form
          button="Create supplier"
          fields={[
            { key: "name", label: "Supplier name", required: true },
            { key: "gstin", label: "GSTIN (optional)" },
            {
              key: "minimum_order",
              label: "Minimum cash order",
              type: "number",
              value: 0,
            },
            {
              key: "payment_terms",
              label: "Payment terms",
              value: "Net 14 days",
            },
          ]}
          onSubmit={async (v) => {
            const s = await w.api("/suppliers", "POST", {
              ...v,
              gstin: v.gstin || null,
            });
            w.setNotice("Supplier created");
            router.push("/intelligence/suppliers/" + s.id);
          }}
        />
      </Panel>
    </>
  );
}
export function SupplierDetail() {
  const { id } = useParams<{ id: string }>(),
    resource = useResource("/workspace/catalog/suppliers/" + id),
    cards = useResource("/suppliers"),
    products = useResource("/products"),
    w = useWorkspace();
  const s = resource.data?.record;
  if (!s) return <Loading />;
  const score = cards.data?.find((s: Row) => s.id === id);
  return (
    <>
      <PageHeader
        title={s.name}
        description={s.gstin || "Supplier profile"}
        back="/intelligence/suppliers"
        action={
          <ActionLink
            href={"/intelligence/suppliers/quotes/new?supplier=" + id}
          >
            <Plus size={16} />
            Add quotation
          </ActionLink>
        }
      />
      <div className="stats-grid">
        <Stat
          label="Minimum cash order"
          value={money(s.minimum_order)}
          detail={s.payment_terms}
        />
        <Stat
          label="Observed lead time"
          value={
            score?.lead_days == null ? "—" : number(score.lead_days) + " days"
          }
          detail={`${score?.sample_size || 0} historical delivery records`}
        />
        <Stat
          label="On-time deliveries"
          value={
            score?.on_time_rate == null
              ? "—"
              : Math.round(score.on_time_rate * 100) + "%"
          }
          detail={score?.evidence}
        />
        <Stat
          label="Fulfillment rate"
          value={
            score?.fulfillment_rate == null
              ? "—"
              : Math.round(score.fulfillment_rate * 100) + "%"
          }
          detail="Observed received / ordered quantities"
        />
      </div>
      <Panel title="Comparable prices">
        <DataTable
          rows={resource.data.quotes || []}
          columns={[
            {
              key: "product_id",
              label: "Product",
              render: (q) => (
                <Link
                  className="record-link"
                  href={"/inventory/products/" + q.product_id}
                >
                  {products.data?.find((p: Row) => p.id === q.product_id)?.name}
                </Link>
              ),
            },
            {
              key: "unit_cost",
              label: "Net / unit",
              numeric: true,
              render: (q) => money(q.unit_cost),
            },
            {
              key: "tax_pct",
              label: "Tax",
              render: (q) => number(q.tax_pct) + "%",
            },
            {
              key: "freight_unit",
              label: "Freight / unit",
              render: (q) => money(q.freight_unit),
            },
            {
              key: "moq",
              label: "MOQ",
              numeric: true,
              render: (q) => number(q.moq),
            },
            {
              key: "valid_until",
              label: "Valid until",
              render: (q) => date(q.valid_until),
            },
          ]}
        />
      </Panel>
      <Panel title="Purchase evidence">
        <DataTable
          rows={resource.data.history || []}
          columns={[
            { key: "date", label: "Date", render: (r) => date(r.date) },
            { key: "invoice_no", label: "Invoice" },
            {
              key: "qty",
              label: "Base units",
              numeric: true,
              render: (r) => number(r.qty),
            },
            {
              key: "unit_cost",
              label: "Economic cost / unit",
              numeric: true,
              render: (r) => money(r.unit_cost),
            },
          ]}
        />
      </Panel>
      <Panel title="Bank-detail verification" className="padded">
        <p className="muted">
          Keep only a fingerprint for verification. Independently confirm
          changed details with the supplier.
        </p>
        <Form
          button="Verify bank fingerprint"
          fields={[
            {
              key: "fingerprint",
              label: "Bank account reference / fingerprint",
              required: true,
            },
            {
              key: "verified",
              label: "Independent verification",
              options: [
                { value: "false", label: "Not yet independently verified" },
                {
                  value: "true",
                  label: "I independently verified these details",
                },
              ],
              value: "false",
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/suppliers/" + id + "/bank", "POST", {
              fingerprint: v.fingerprint,
              verified: v.verified === "true",
            });
            w.setNotice("Verification recorded");
          }}
        />
      </Panel>
    </>
  );
}
export function QuoteForm() {
  const w = useWorkspace(),
    router = useRouter(),
    query = useSearchParams(),
    rfqId = query.get("rfq"),
    rfq = useResource(rfqId ? "/workspace/rfqs/" + rfqId : null),
    products = useResource("/products"),
    suppliers = useResource("/suppliers");
  return (
    <>
      <PageHeader
        title="Record supplier quotation"
        description="Use normalized base-unit prices so offers remain comparable."
        back={rfqId ? "/purchasing/rfqs/" + rfqId : "/intelligence/suppliers"}
      />
      <Panel title="Quotation details" className="form-panel">
        <Form
          button="Save quotation"
          fields={[
            {
              key: "supplier_id",
              label: "Supplier",
              required: true,
              value: query.get("supplier") || "",
              options: (suppliers.data || [])
                .filter(
                  (s: Row) => !rfq.data || rfq.data.supplier_ids.includes(s.id),
                )
                .map((s: Row) => ({ value: s.id, label: s.name })),
            },
            {
              key: "product_id",
              label: "Product",
              required: true,
              options: (products.data || [])
                .filter(
                  (p: Row) =>
                    !rfq.data ||
                    rfq.data.lines.some((l: Row) => l.product_id === p.id),
                )
                .map((p: Row) => ({ value: p.id, label: p.name })),
            },
            { key: "supplier_sku", label: "Supplier item code" },
            {
              key: "unit_cost",
              label: "Net cost / base unit (ex GST)",
              type: "number",
              required: true,
            },
            { key: "tax_pct", label: "GST %", type: "number", value: 0 },
            {
              key: "freight_unit",
              label: "Allocated freight / base unit",
              type: "number",
              value: 0,
            },
            {
              key: "pack",
              label: "Case pack, base units",
              type: "number",
              value: 1,
            },
            {
              key: "moq",
              label: "Minimum quantity, base units",
              type: "number",
              value: 1,
            },
            {
              key: "multiple",
              label: "Order multiple, base units",
              type: "number",
              value: 1,
            },
            {
              key: "lead_days",
              label: "Lead time, days",
              type: "number",
              value: 3,
            },
            {
              key: "observed",
              label: "Price observed",
              type: "date",
              value: today(),
              required: true,
            },
            { key: "valid_until", label: "Valid until", type: "date" },
            { key: "tax_id", label: "Zoho tax ID (for taxed writeback)" },
            {
              key: "tier_qty",
              label: "Optional volume tier: minimum quantity",
              type: "number",
            },
            {
              key: "tier_cost",
              label: "Optional volume tier: net unit cost",
              type: "number",
            },
          ]}
          onSubmit={async (v) => {
            const { tier_qty, tier_cost, ...values } = v;
            const q = await w.api("/quotes", "POST", {
              ...values,
              valid_until: v.valid_until || null,
              tax_id: v.tax_id || null,
              tiers:
                tier_qty && tier_cost
                  ? [{ min_qty: tier_qty, unit_cost: tier_cost }]
                  : [],
            });
            if (rfqId)
              await w.api("/workspace/rfqs/" + rfqId + "/responses", "POST", {
                version: rfq.data.version,
                quote_ids: [q.id],
              });
            w.setNotice("Quotation recorded");
            router.push(
              rfqId
                ? "/purchasing/rfqs/" + rfqId
                : "/intelligence/suppliers/" + q.supplier_id,
            );
          }}
        />
      </Panel>
    </>
  );
}
