"use client";
import Link from "next/link";
import { useRouter, useParams } from "next/navigation";
import { useState, useRef } from "react";
import {
  Upload,
  FileText,
  Zap,
  FileCheck,
  ShieldCheck,
  Plus,
  CheckCircle,
} from "lucide-react";
import { useResource, useWorkspace, date, type Row } from "./workspace";
import {
  DataTable,
  ActionLink,
  Loading,
  ErrorBox,
  Status,
  PageHeader,
  Panel,
} from "./ui";
import { DocumentUpload, ImportWizard, InvoiceReview } from "./invoice-tools";

function Invoice3DGraphic() {
  return (
    <svg width="120" height="110" viewBox="0 0 140 130" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="invDocBg" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#ffffff" />
          <stop offset="100%" stopColor="#f1f5f9" />
        </linearGradient>
        <linearGradient id="invAccent" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <filter id="invShadow" x="-10%" y="-10%" width="130%" height="130%">
          <feDropShadow dx="0" dy="8" stdDeviation="8" floodColor="#0f172a" floodOpacity="0.08" />
        </filter>
      </defs>
      {/* Background card */}
      <rect x="25" y="15" width="80" height="100" rx="8" fill="#e2e8f0" transform="rotate(-6 65 65)" opacity="0.6" />
      {/* Foreground 3D Invoice Card */}
      <rect x="35" y="10" width="80" height="105" rx="8" fill="url(#invDocBg)" stroke="#cbd5e1" strokeWidth="1.2" filter="url(#invShadow)" />
      {/* Header bar */}
      <rect x="45" y="22" width="30" height="5" rx="2.5" fill="url(#invAccent)" />
      <rect x="85" y="22" width="20" height="5" rx="2.5" fill="#e2e8f0" />
      {/* Divider */}
      <line x1="45" y1="36" x2="105" y2="36" stroke="#e2e8f0" strokeWidth="1" strokeDasharray="2 2" />
      {/* Item rows */}
      <rect x="45" y="45" width="40" height="4" rx="2" fill="#94a3b8" />
      <rect x="95" y="45" width="10" height="4" rx="2" fill="#64748b" />
      
      <rect x="45" y="56" width="34" height="4" rx="2" fill="#cbd5e1" />
      <rect x="95" y="56" width="10" height="4" rx="2" fill="#64748b" />
      
      <rect x="45" y="67" width="44" height="4" rx="2" fill="#cbd5e1" />
      <rect x="95" y="67" width="10" height="4" rx="2" fill="#64748b" />
      {/* Total row */}
      <rect x="45" y="82" width="25" height="5" rx="2" fill="#1e293b" />
      <rect x="85" y="82" width="20" height="5" rx="2.5" fill="#2563eb" />
      {/* Verified Stamp Badge */}
      <circle cx="98" cy="98" r="14" fill="#10b981" />
      <path d="M94 98 L97 101 L103 95" stroke="#ffffff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Invoices() {
  const resource = useResource("/documents");
  const { api, business, branch, setNotice } = useWorkspace();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleFileUpload = async (file: File) => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const fd = new FormData();
      fd.append("file", file);
      await api(`/businesses/${business}/branches/${branch}/documents`, "POST", fd);
      setNotice(`Invoice "${file.name}" uploaded successfully for extraction & verification.`);
      resource.reload();
    } catch (err: any) {
      setError(err.message || "Failed to process invoice");
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="invoices-page">
      {/* Page Title Header */}
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Upload Supplier Invoice</h1>
          <p className="overview-subtitle">
            Extract items, prices and taxes automatically.
          </p>
        </div>
        <div className="overview-header-actions">
          <Link href="/purchasing/invoices/import" className="period-dropdown-btn">
            <Upload size={14} />
            Import spreadsheet
          </Link>
        </div>
      </div>

      <ErrorBox error={error || resource.error} />

      {/* 2. Central Upload Card matching Page 2 blueprint */}
      <div className="invoice-upload-container">
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: "24px", flexWrap: "wrap" }}>
          {/* Left Dropzone Area */}
          <div
            className="invoice-dropzone"
            style={{ flex: 1, minWidth: "300px" }}
            onClick={() => fileInputRef.current?.click()}
            onDragOver={(e) => e.preventDefault()}
            onDrop={(e) => {
              e.preventDefault();
              if (e.dataTransfer.files?.[0]) {
                handleFileUpload(e.dataTransfer.files[0]);
              }
            }}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: "none" }}
              accept=".pdf,.jpg,.jpeg,.png,.json"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleFileUpload(e.target.files[0]);
                }
              }}
            />
            <div className="dropzone-icon-3d">
              <Upload size={28} />
            </div>
            <div className="dropzone-title">
              {uploading ? "Extracting invoice data..." : "Drag & drop invoice (PDF, JPG, PNG) or click to browse"}
            </div>
            <div className="dropzone-sub">
              Fast automatic line-item parsing, tax split & anomaly verification
            </div>
            <span className="dropzone-size-pill">Max size: 10 MB</span>
          </div>

          {/* Right 3D Visual Invoice graphic */}
          <div style={{ padding: "0 20px", display: "flex", flexDirection: "column", alignItems: "center" }}>
            <Invoice3DGraphic />
            <span style={{ fontSize: "11px", fontWeight: 600, color: "#64748b", marginTop: "8px" }}>
              Instant Arithmetic Check
            </span>
          </div>
        </div>

        {/* 3 Feature Pills */}
        <div className="invoice-feature-pills">
          <div className="invoice-feature-pill">
            <Zap size={14} color="#2563eb" />
            <span><strong>Auto-data extraction</strong> (items, prices, quantity)</span>
          </div>
          <div className="invoice-feature-pill">
            <FileCheck size={14} color="#10b981" />
            <span><strong>GST e-invoice support</strong> (JSON / IRN)</span>
          </div>
          <div className="invoice-feature-pill">
            <ShieldCheck size={14} color="#8b5cf6" />
            <span><strong>Review & verify</strong> before finalizing</span>
          </div>
        </div>
      </div>

      {/* Invoices List / Table */}
      <div className="card-panel">
        <div className="panel-header-row">
          <div className="panel-title-group">
            <div className="panel-icon-wrap" style={{ background: "#eff6ff", color: "#2563eb" }}>
              <FileText size={18} />
            </div>
            <div className="panel-title-text">
              <h3>Recent Invoices & Documents</h3>
              <p>Review source bills, resolve mappings, and track price anomalies.</p>
            </div>
          </div>
        </div>

        {(resource.data || []).length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 20px" }}>
            <FileText size={36} color="#94a3b8" style={{ margin: "0 auto 12px" }} />
            <h4 style={{ margin: "0 0 6px", fontSize: "15px", color: "#0f172a" }}>No Invoices Uploaded Yet</h4>
            <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>
              Upload your first supplier invoice above to extract prices and protect margins.
            </p>
          </div>
        ) : (
          <DataTable
            rows={resource.data || []}
            columns={[
              {
                key: "name",
                label: "Document",
                render: (d) => (
                  <Link
                    className="record-link"
                    href={"/purchasing/invoices/" + d.id}
                  >
                    <span className="document-thumbnail">
                      <FileText size={18} />
                    </span>
                    <span>
                      <strong>{d.name}</strong>
                      <small style={{ display: "block", color: "#64748b" }}>
                        {d.mime === "application/json"
                          ? "Structured GST e-invoice"
                          : "Supplier document"}
                      </small>
                    </span>
                  </Link>
                ),
              },
              {
                key: "created",
                label: "Received",
                render: (d) => date(d.created),
              },
              {
                key: "status",
                label: "State",
                render: (d) => <Status value={d.status} />,
              },
              { key: "version", label: "Version" },
              {
                key: "action",
                label: "",
                render: (d) => (
                  <ActionLink secondary href={"/purchasing/invoices/" + d.id}>
                    {d.status === "verified" ? "View / correct" : "Review invoice"}
                  </ActionLink>
                ),
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}

export function UploadInvoice() {
  const w = useWorkspace(),
    router = useRouter(),
    overview = useResource(w.base + "/overview");
  const api = (p: string, m?: string, b?: unknown) =>
    w.api(p.startsWith(w.base) ? p.slice(w.base.length) : p, m, b);
  return (
    <>
      <PageHeader
        title="Upload invoice"
        description="Extract items, prices and taxes from PDF or scanned documents."
        back="/purchasing/invoices"
      />
      <Panel title="Source document" className="form-panel">
        <DocumentUpload
          api={api}
          base={w.base}
          consent={overview.data?.business?.settings?.ocr_consent || false}
          done={async () => {
            w.setNotice(
              "Document uploaded. Open it to review extraction or enter fields manually."
            );
            router.push("/purchasing/invoices");
          }}
        />
      </Panel>
    </>
  );
}

export function ImportData() {
  const w = useWorkspace(),
    router = useRouter();
  const api = (p: string, m?: string, b?: unknown) =>
    w.api(p.startsWith(w.base) ? p.slice(w.base.length) : p, m, b);
  return (
    <>
      <PageHeader
        title="Import business data"
        description="Preview the source, map columns, and fix errors before committing an atomic import."
        back="/purchasing/invoices"
      />
      <Panel title="Spreadsheet import" className="form-panel">
        <ImportWizard
          api={api}
          base={w.base}
          done={async () => {
            w.setNotice("Import completed successfully");
            router.push("/purchasing/invoices");
          }}
        />
      </Panel>
    </>
  );
}

export function ReviewInvoice() {
  const params = useParams<{ id: string }>(),
    id = params?.id,
    w = useWorkspace(),
    router = useRouter(),
    doc = useResource(`${w.base}/documents/${id}`),
    prod = useResource(`${w.base}/products`),
    sup = useResource(`${w.base}/suppliers`);
  const api = (p: string, m?: string, b?: unknown) =>
    w.api(p.startsWith(w.base) ? p.slice(w.base.length) : p, m, b);

  if (doc.loading || prod.loading || sup.loading) return <Loading />;
  if (doc.error || prod.error || sup.error)
    return <ErrorBox error={doc.error || prod.error || sup.error || ""} />;
  if (!doc.data) return <ErrorBox error="Document not found" />;

  return (
    <>
      <PageHeader
        title={`Review ${doc.data.file_name || "Invoice"}`}
        description="Verify extracted line items, prices and supplier matches before committing to inventory."
        back="/purchasing/invoices"
      />
      <Panel title="Verification & Mapping" className="form-panel">
        <InvoiceReview
          document={doc.data}
          products={prod.data || []}
          suppliers={sup.data || []}
          base={w.base}
          api={api}
          done={async (verified) => {
            await api(`${w.base}/documents/${id}/verify`, "POST", verified);
            w.setNotice("Invoice verified and inventory updated.");
            router.push("/purchasing/invoices");
          }}
        />
      </Panel>
    </>
  );
}
