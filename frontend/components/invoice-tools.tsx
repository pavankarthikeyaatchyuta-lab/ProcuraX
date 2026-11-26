"use client";
import Link from "next/link";
import { useState, type FormEvent } from "react";
import {
  Plus,
  X,
  Check,
  ArrowRight,
  Download,
  ShieldCheck,
} from "lucide-react";
import { Badge, Table } from "./ui";
import { today, useWorkspace, type Row } from "./workspace";
export function ImportWizard({
  api,
  base,
  done,
}: {
  api: (p: string, m?: string, b?: unknown) => Promise<Row>;
  base: string;
  done: () => Promise<void>;
}) {
  const [kind, setKind] = useState("products"),
    [preview, setPreview] = useState<Row | null>(null),
    [mapping, setMapping] = useState<Row>({}),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  async function upload(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      const fd = new FormData(e.currentTarget);
      const p = await api(base + "/imports/preview", "POST", fd);
      setPreview(p);
      setMapping(p.mapping);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="wizard">
      <p>
        Imports are atomic: if a row fails validation, nothing is posted. Stable
        source keys prevent duplicate imports.
      </p>
      {!preview ? (
        <form onSubmit={upload}>
          <label>
            Data type
            <select
              name="kind"
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {[
                "products",
                "suppliers",
                "opening_stock",
                "purchases",
                "sales",
                "returns",
                "adjustments",
              ].map((k) => (
                <option key={k}>{k}</option>
              ))}
            </select>
          </label>
          <a
            className="text-button"
            href={"/api/v1" + base + "/imports/templates/" + kind}
          >
            <Download size={15} />
            Download CSV template
          </a>
          <label>
            CSV or XLSX
            <input type="file" name="file" accept=".csv,.xlsx" required />
          </label>
          <button className="primary" disabled={busy}>
            {busy ? "Validating…" : "Preview & map columns"}
          </button>
        </form>
      ) : (
        <>
          <Badge>{preview.total_rows} rows</Badge>
          <div className="form-grid">
            {preview.fields.map((f: string) => (
              <label key={f}>
                {f}
                <select
                  value={mapping[f] || ""}
                  onChange={(e) =>
                    setMapping({ ...mapping, [f]: e.target.value })
                  }
                >
                  <option value="">Not mapped</option>
                  {preview.columns.map((c: string) => (
                    <option key={c}>{c}</option>
                  ))}
                </select>
              </label>
            ))}
          </div>
          <Table heads={preview.columns}>
            {preview.preview.slice(0, 5).map((r: Row, i: number) => (
              <tr key={i}>
                {preview.columns.map((c: string) => (
                  <td key={c}>{r[c]}</td>
                ))}
              </tr>
            ))}
          </Table>
          <button
            className="primary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError("");
              try {
                await api(base + `/imports/${preview.id}/commit`, "POST", {
                  mapping,
                });
                await done();
              } catch (e) {
                setError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            Commit validated import
          </button>
        </>
      )}
      {error && (
        <div className="error" role="alert">
          {error}
        </div>
      )}
    </div>
  );
}
export function DocumentUpload({
  api,
  base,
  consent,
  done,
}: {
  api: (p: string, m?: string, b?: unknown) => Promise<Row>;
  base: string;
  consent: boolean;
  done: () => Promise<void>;
}) {
  const [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  return (
    <form
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        try {
          await api(base + "/documents", "POST", new FormData(e.currentTarget));
          await done();
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="info">
        <ShieldCheck size={20} />
        <span>
          <strong>Direct GST e-invoice JSON extraction active.</strong>{" "}
          {consent ? (
            "OCR document processing consent is enabled for image and PDF bills."
          ) : (
            <>
              OCR consent for PDF/scanned images is currently disabled.{" "}
              <Link href="/administration/settings" style={{ textDecoration: "underline", color: "inherit", fontWeight: 600 }}>
                Enable in Settings
              </Link>{" "}
              to process physical bills, or upload GST e-invoice JSON directly.
            </>
          )}
        </span>
      </div>
      <label>
        Supplier invoice · up to 10 MB
        <input
          type="file"
          name="file"
          accept=".json,.pdf,.jpg,.jpeg,.png"
          required
        />
      </label>
      {error && <div className="error">{error}</div>}
      <button className="primary" disabled={busy}>
        {busy ? "Uploading…" : "Upload for verification"}
      </button>
    </form>
  );
}

export function InvoiceReview({
  document: d,
  products,
  suppliers,
  base,
  api,
  done,
}: {
  document: Row;
  products: Row[];
  suppliers: Row[];
  base: string;
  api: (p: string, m?: string, b?: unknown) => Promise<Row>;
  done: (v: Row) => Promise<unknown>;
}) {
  const { branch } = useWorkspace();
  const e =
      d.status === "verified"
        ? [...d.versions].reverse().find((v: Row) => v.verified)?.verified ||
          d.extracted
        : d.extracted || {},
    [lines, setLines] = useState<Row[]>(
      e.lines?.length
        ? e.lines.map((l: Row) => ({
            ...l,
            factor: l.factor || 1,
            unit: l.unit || "unit",
            raw_description: l.raw_description || "",
            discount: l.discount || 0,
            tax_pct: l.tax_pct || 0,
            freight: l.freight || 0,
          }))
        : [
            {
              product_id: "",
              raw_description: "",
              qty: 1,
              rate: 0,
              unit: "unit",
              factor: 1,
              discount: 0,
              tax_pct: 0,
              freight: 0,
            },
          ],
    ),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [lineSuggestions, setLineSuggestions] = useState<Record<number, Row[]>>({});
  const update = (i: number, key: string, value: string) =>
    setLines(lines.map((l, n) => (n === i ? { ...l, [key]: value } : l)));

  // Calculate live reconciled totals
  const calculatedGrandTotal = lines.reduce((sum, l) => {
    const qty = Number(l.qty) || 0;
    const rate = Number(l.rate) || 0;
    const discount = Number(l.discount) || 0;
    const taxPct = Number(l.tax_pct) || 0;
    const freight = Number(l.freight) || 0;
    const baseAmount = Math.max(0, qty * rate - discount);
    const taxAmount = (baseAmount * taxPct) / 100;
    return sum + baseAmount + taxAmount + freight;
  }, 0);
  const extractedTotal = Number(e.total) || 0;
  const isReconciled = extractedTotal > 0 && Math.abs(calculatedGrandTotal - extractedTotal) < 1.0;

  return (
    <div className="review-layout">
      <div className="document-preview">
        {d.mime === "application/json" ? (
          <pre>{JSON.stringify(e.source_json || e, null, 2)}</pre>
        ) : d.mime?.startsWith("image/") ? (
          <img
            src={"/api/v1" + base + `/documents/${d.id}/file?branch_id=${branch}`}
            alt="Original invoice"
            style={{ width: "100%", height: "auto", maxHeight: "100%", objectFit: "contain", borderRadius: "8px" }}
          />
        ) : (
          <iframe
            title="Original invoice"
            src={
              "/api/v1" + base + `/documents/${d.id}/file?branch_id=${branch}`
            }
          />
        )}
      </div>
      <form
        onSubmit={async (event) => {
          event.preventDefault();
          setBusy(true);
          setError("");
          const values = Object.fromEntries(new FormData(event.currentTarget));
          try {
            await done({
              ...values,
              version: d.version,
              lines: lines.map((l) => ({
                product_id: l.product_id,
                raw_description: l.raw_description,
                qty: l.qty,
                factor: l.factor || 1,
                unit: l.unit || "unit",
                rate: l.rate,
                discount: l.discount || 0,
                tax_pct: l.tax_pct || 0,
                freight: l.freight || 0,
              })),
            });
          } catch (err) {
            setError((err as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        <div className="form-grid">
          <label>
            <span style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "8px", flexWrap: "wrap", marginBottom: "4px" }}>
              <span>Supplier</span>
              {e.supplier_name && (
                <span style={{ fontSize: "11px", color: "#2563eb", background: "#eff6ff", padding: "2px 8px", borderRadius: "10px", border: "1px solid #dbeafe", fontWeight: 500 }}>
                  Extracted: {e.supplier_name} {e.supplier_gstin ? `(${e.supplier_gstin})` : ""}
                </span>
              )}
            </span>
            <select
              name="supplier_id"
              required
              defaultValue={
                e.supplier_id ||
                suppliers.find((s) => s.gstin === e.supplier_gstin || s.name?.toLowerCase() === e.supplier_name?.toLowerCase())?.id ||
                ""
              }
            >
              <option value="">Map supplier…</option>
              {suppliers.map((s) => (
                <option value={s.id} key={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            Invoice number
            <input
              name="invoice_no"
              defaultValue={e.invoice_no || ""}
              required
            />
          </label>
          <label>
            Invoice date
            <input
              name="date"
              type="date"
              defaultValue={e.date || today()}
              required
            />
          </label>
          <label>
            Invoice grand total (₹)
            <input
              name="total"
              type="number"
              step=".01"
              defaultValue={e.total || ""}
              required
            />
          </label>
        </div>
        <p className="muted">
          Confirm the exact variant and base-unit conversion. Low-confidence
          fields remain your responsibility to verify.
        </p>
        {lines.map((l, i) => (
          <div className="review-line" key={i}>
            <div className="line-heading">
              <strong>Line {i + 1}</strong>
              <Badge tone={l.confidence >= 0.9 ? "green" : "amber"}>
                {l.confidence != null
                  ? `${Math.round(l.confidence * 100)}% parser confidence`
                  : "Manual entry"}
              </Badge>
              <button
                type="button"
                className="icon-button"
                aria-label={`Remove line ${i + 1}`}
                onClick={() => setLines(lines.filter((_, n) => n !== i))}
              >
                <X size={15} />
              </button>
            </div>
            <label>
              Raw description
              <input
                value={l.raw_description}
                onChange={(e) => update(i, "raw_description", e.target.value)}
              />
            </label>
            <label>
              Canonical product
              <select
                value={l.product_id || ""}
                required
                onChange={(e) => update(i, "product_id", e.target.value)}
              >
                <option value="">Confirm product…</option>
                {products.map((p) => (
                  <option value={p.id} key={p.id}>
                    {[p.name, p.size, p.variant].filter(Boolean).join(" · ")}
                  </option>
                ))}
              </select>
            </label>
            <div style={{ margin: "6px 0 10px" }}>
              <button
                type="button"
                className="text-button"
                style={{ fontSize: "12px", color: "#2563eb", fontWeight: 600, padding: "2px 0" }}
                onClick={async () => {
                  try {
                    const suggestions = await api(
                      base +
                        "/products/match/suggest?text=" +
                        encodeURIComponent(l.raw_description),
                    );
                    setLineSuggestions((prev) => ({
                      ...prev,
                      [i]: (suggestions as unknown as Row[]) || [],
                    }));
                  } catch (err) {
                    setError((err as Error).message);
                  }
                }}
              >
                Suggest a mapping
              </button>
              {lineSuggestions[i] && lineSuggestions[i].length > 0 && (
                <div style={{ display: "flex", gap: "6px", flexWrap: "wrap", marginTop: "6px" }}>
                  <span style={{ fontSize: "11px", color: "#64748b", alignSelf: "center" }}>Click to map:</span>
                  {lineSuggestions[i].map((s: Row) => (
                    <button
                      key={s.product_id || s.name}
                      type="button"
                      onClick={() => update(i, "product_id", s.product_id || "")}
                      style={{
                        background: l.product_id === s.product_id ? "#2563eb" : "#eff6ff",
                        color: l.product_id === s.product_id ? "#ffffff" : "#2563eb",
                        border: "1px solid #bfdbfe",
                        borderRadius: "14px",
                        padding: "3px 10px",
                        fontSize: "11.5px",
                        cursor: "pointer",
                        fontWeight: 500,
                      }}
                    >
                      {s.name || s.product_id} ({Math.round((s.confidence || 0) * 100)}%)
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="form-grid">
              {[
                ["qty", "Invoice quantity"],
                ["factor", "Base units / invoice unit"],
                ["rate", "Rate / invoice unit (₹)"],
                ["discount", "Line discount (₹)"],
                ["tax_pct", "GST %"],
                ["freight", "Allocated freight (₹)"],
              ].map(([key, label]) => (
                <label key={key}>
                  {label}
                  <input
                    type="number"
                    step="any"
                    value={l[key]}
                    onChange={(e) => update(i, key, e.target.value)}
                    required
                  />
                </label>
              ))}
            </div>
          </div>
        ))}
        <button
          type="button"
          className="secondary"
          onClick={() =>
            setLines([
              ...lines,
              {
                product_id: "",
                raw_description: "",
                qty: 1,
                rate: 0,
                factor: 1,
                unit: "unit",
                discount: 0,
                tax_pct: 0,
                freight: 0,
              },
            ])
          }
        >
          <Plus size={15} />
          Add line
        </button>

        {/* Live Arithmetic Reconciliation Summary */}
        <div
          style={{
            margin: "18px 0 10px",
            padding: "14px 18px",
            background: isReconciled ? "#f0fdf4" : "#fefce8",
            border: `1px solid ${isReconciled ? "#bbf7d0" : "#fef08a"}`,
            borderRadius: "10px",
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            flexWrap: "wrap",
            gap: "10px",
          }}
        >
          <div>
            <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", letterSpacing: "0.04em", color: isReconciled ? "#15803d" : "#a16207" }}>
              {isReconciled ? "✓ Arithmetic Reconciled" : "Arithmetic Check"}
            </div>
            <div style={{ fontSize: "13px", color: "#334155", marginTop: "2px" }}>
              Lines Total: <strong>₹{calculatedGrandTotal.toFixed(2)}</strong>
              {extractedTotal > 0 && (
                <span style={{ marginLeft: "12px", color: "#64748b" }}>
                  Invoice Stated Total: <strong>₹{extractedTotal.toFixed(2)}</strong>
                </span>
              )}
            </div>
          </div>
          <div style={{ fontSize: "12px", fontWeight: 600, color: isReconciled ? "#15803d" : "#ca8a04" }}>
            {isReconciled
              ? "Totals match source document perfectly"
              : extractedTotal > 0
                ? `Difference: ₹${Math.abs(calculatedGrandTotal - extractedTotal).toFixed(2)}`
                : "Checking line items..."}
          </div>
        </div>

        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        <button className="primary" disabled={busy || !lines.length}>
          {busy ? "Verifying…" : "Verify & record purchase"}
          <Check size={16} />
        </button>
      </form>
    </div>
  );
}
