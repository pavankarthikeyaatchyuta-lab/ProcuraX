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
  Camera,
  X,
  RefreshCw,
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
  const [filterStatus, setFilterStatus] = useState<"all" | "review" | "verified">("all");
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [facingMode, setFacingMode] = useState<"environment" | "user">("environment");

  const fileInputRef = useRef<HTMLInputElement>(null);
  const cameraInputRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

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

  const startCamera = async (mode: "environment" | "user" = facingMode) => {
    setCameraError("");
    setIsCameraOpen(true);
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((track) => track.stop());
      }
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        cameraInputRef.current?.click();
        setIsCameraOpen(false);
        return;
      }
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: mode,
          width: { ideal: 1920 },
          height: { ideal: 1080 },
        },
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.play();
      }
    } catch (err: any) {
      console.error("Camera access error:", err);
      setCameraError(err.message || "Unable to access camera. Please allow camera permissions or use mobile capture.");
    }
  };

  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    setIsCameraOpen(false);
    setCameraError("");
  };

  const switchCamera = () => {
    const nextMode = facingMode === "environment" ? "user" : "environment";
    setFacingMode(nextMode);
    startCamera(nextMode);
  };

  const capturePhoto = () => {
    if (!videoRef.current) return;
    const video = videoRef.current;
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext("2d");
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob(
        (blob) => {
          if (blob) {
            const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
            const file = new File([blob], `invoice-camera-${timestamp}.jpg`, {
              type: "image/jpeg",
            });
            stopCamera();
            handleFileUpload(file);
          }
        },
        "image/jpeg",
        0.95
      );
    }
  };

  return (
    <div className="invoices-page">
      {/* Hidden native camera capture input for mobile devices */}
      <input
        type="file"
        ref={cameraInputRef}
        style={{ display: "none" }}
        accept="image/*"
        capture="environment"
        onChange={(e) => {
          if (e.target.files?.[0]) {
            handleFileUpload(e.target.files[0]);
          }
        }}
      />

      {/* Page Title Header */}
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Upload Supplier Invoice</h1>
          <p className="overview-subtitle">
            Extract items, prices and taxes automatically.
          </p>
        </div>
        <div className="overview-header-actions" style={{ display: "flex", gap: "10px", alignItems: "center" }}>
          <button
            type="button"
            className="camera-scan-btn"
            onClick={() => startCamera()}
            title="Scan or capture invoice using camera"
          >
            <Camera size={15} />
            Scan with Camera
          </button>
          <Link href="/purchasing/invoices/import" className="period-dropdown-btn">
            <Upload size={14} />
            Import spreadsheet
          </Link>
        </div>
      </div>

      <ErrorBox error={error || resource.error} />

      {/* Camera Live Modal Overlay */}
      {isCameraOpen && (
        <div className="modal-overlay" onClick={stopCamera}>
          <div className="camera-modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                <div style={{ width: "36px", height: "36px", borderRadius: "10px", background: "#eff6ff", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center" }}>
                  <Camera size={20} />
                </div>
                <div>
                  <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>Camera Document Scanner</h3>
                  <p style={{ margin: 0, fontSize: "12px", color: "#64748b" }}>Align the bill within the guides and snap</p>
                </div>
              </div>
              <button
                type="button"
                onClick={stopCamera}
                style={{ background: "transparent", border: "none", color: "#64748b", cursor: "pointer", padding: "4px" }}
              >
                <X size={20} />
              </button>
            </div>

            {cameraError ? (
              <div style={{ margin: "20px 0", padding: "16px", background: "#fef2f2", border: "1px solid #fecaca", borderRadius: "10px", color: "#b91c1c", fontSize: "13px" }}>
                <p style={{ margin: "0 0 12px", fontWeight: 600 }}>{cameraError}</p>
                <button
                  type="button"
                  className="camera-scan-btn"
                  onClick={() => {
                    stopCamera();
                    cameraInputRef.current?.click();
                  }}
                >
                  <Camera size={14} /> Open Device Camera Picker
                </button>
              </div>
            ) : (
              <>
                <div className="camera-viewfinder-wrapper">
                  <video
                    ref={videoRef}
                    autoPlay
                    playsInline
                    muted
                    style={{ transform: facingMode === "user" ? "scaleX(-1)" : "none" }}
                  />
                  <div className="camera-guide-frame" />
                  <div className="camera-guide-text">Position invoice edges inside guide frame</div>
                </div>

                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px" }}>
                  <button
                    type="button"
                    onClick={switchCamera}
                    className="period-dropdown-btn"
                    title="Switch camera"
                  >
                    <RefreshCw size={14} /> Flip Camera
                  </button>
                  <button
                    type="button"
                    onClick={capturePhoto}
                    className="camera-scan-btn"
                    style={{ padding: "10px 22px", fontSize: "14px" }}
                  >
                    <Camera size={16} /> Snap & Extract
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
      )}

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
            <div className="dropzone-actions-row" style={{ display: "flex", gap: "8px", justifyContent: "center", alignItems: "center", marginTop: "12px", flexWrap: "wrap" }}>
              <button
                type="button"
                className="camera-scan-btn compact"
                onClick={(e) => {
                  e.stopPropagation();
                  startCamera();
                }}
                style={{ padding: "6px 14px", fontSize: "12px", borderRadius: "8px" }}
              >
                <Camera size={13} /> Snap with Camera
              </button>
              <button
                type="button"
                className="period-dropdown-btn compact"
                onClick={(e) => {
                  e.stopPropagation();
                  fileInputRef.current?.click();
                }}
                style={{ padding: "6px 14px", fontSize: "12px", borderRadius: "8px" }}
              >
                <Upload size={13} /> Pick File
              </button>
              <span className="dropzone-size-pill" style={{ padding: "3px 8px", fontSize: "10px" }}>Max 10 MB</span>
            </div>
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

      {/* Mobile Filter Tabs */}
      <div className="mobile-filter-pills">
        <button
          type="button"
          className={`mobile-filter-pill ${filterStatus === "all" ? "active" : ""}`}
          onClick={() => setFilterStatus("all")}
        >
          All ({(resource.data || []).length})
        </button>
        <button
          type="button"
          className={`mobile-filter-pill ${filterStatus === "review" ? "active" : ""}`}
          onClick={() => setFilterStatus("review")}
        >
          Needs Review ({(resource.data || []).filter((d: any) => d.status !== "verified" && d.status !== "approved").length})
        </button>
        <button
          type="button"
          className={`mobile-filter-pill ${filterStatus === "verified" ? "active" : ""}`}
          onClick={() => setFilterStatus("verified")}
        >
          Verified ({(resource.data || []).filter((d: any) => d.status === "verified" || d.status === "approved").length})
        </button>
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

        {((resource.data || []).filter((d: any) => {
          if (filterStatus === "verified") return d.status === "verified" || d.status === "approved";
          if (filterStatus === "review") return d.status !== "verified" && d.status !== "approved";
          return true;
        })).length === 0 ? (
          <div style={{ textAlign: "center", padding: "40px 20px" }}>
            <FileText size={36} color="#94a3b8" style={{ margin: "0 auto 12px" }} />
            <h4 style={{ margin: "0 0 6px", fontSize: "15px", color: "#0f172a" }}>No Matching Invoices</h4>
            <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>
              Upload your supplier invoice above to extract prices and protect margins.
            </p>
          </div>
        ) : (
          <DataTable
            rows={(resource.data || []).filter((d: any) => {
              if (filterStatus === "verified") return d.status === "verified" || d.status === "approved";
              if (filterStatus === "review") return d.status !== "verified" && d.status !== "approved";
              return true;
            })}
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
