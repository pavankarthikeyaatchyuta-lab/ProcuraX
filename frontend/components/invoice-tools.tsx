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
    [busy, setBusy] = useState(false);
  const update = (i: number, key: string, value: string) =>
    setLines(lines.map((l, n) => (n === i ? { ...l, [key]: value } : l)));
  return (
    <div className="review-layout">
      <div className="document-preview">
        {d.mime === "application/json" ? (
          <pre>{JSON.stringify(e.source_json || e, null, 2)}</pre>
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
            Supplier
            <select
              name="supplier_id"
              required
              defaultValue={
                e.supplier_id ||
                suppliers.find((s) => s.gstin === e.supplier_gstin)?.id ||
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
                    {p.name} · {p.size} · {p.variant}
                  </option>
                ))}
              </select>
            </label>
            <button
              type="button"
              className="text-button"
              onClick={async () => {
                try {
                  const suggestions = await api(
                    base +
                      "/products/match/suggest?text=" +
                      encodeURIComponent(l.raw_description),
                  );
                  setError(
                    "Suggestions (confirm pack/variant manually): " +
                      (suggestions as unknown as Row[])
                        .map(
                          (s) =>
                            `${s.name || s.product_id} ${Math.round(s.confidence * 100)}%`,
                        )
                        .join("; "),
                  );
                } catch (err) {
                  setError((err as Error).message);
                }
              }}
            >
              Suggest a mapping
            </button>
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
