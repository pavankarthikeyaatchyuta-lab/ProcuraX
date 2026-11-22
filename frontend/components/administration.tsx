"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import {
  Plus,
  Building2,
  Users,
  Check,
  ShieldCheck,
  RefreshCw,
  ArrowUpRight,
  Download,
  Bell,
  Wallet,
  FileText,
  Settings as SettingsIcon,
} from "lucide-react";
import {
  useResource,
  useWorkspace,
  money,
  number,
  date,
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
  Status,
  Badge,
  useAction,
} from "./ui";
export function Branches() {
  const w = useWorkspace(),
    staff = useResource(w.role === "owner" ? "/workspace/staff" : null);
  return (
    <>
      <PageHeader
        title="Branches & team"
        description="Shared catalogs. Separate stock, purchasing budgets, and staff permissions."
        action={
          <>
            <ActionLink href="/administration/branches/team" secondary>
              <Users size={16} />
              Assign staff
            </ActionLink>
            <ActionLink href="/administration/branches/new">
              <Plus size={16} />
              Add branch
            </ActionLink>
          </>
        }
      />
      <div className="branch-cards">
        {w.branches.map((b) => (
          <Panel
            key={b.id}
            title={b.name}
            action={<Badge tone="blue">{b.code}</Badge>}
          >
            <div className="branch-card-body">
              <span className="branch-illustration">
                <Building2 size={28} />
              </span>
              <p>{b.address || "No branch address configured"}</p>
              <dl>
                <div>
                  <dt>Purchasing budget</dt>
                  <dd>{money(b.budget)}</dd>
                </div>
                <div>
                  <dt>Approved commitments</dt>
                  <dd>{money(b.committed)}</dd>
                </div>
                <div>
                  <dt>Manager approval limit</dt>
                  <dd>{money(b.manager_limit)}</dd>
                </div>
                <div>
                  <dt>Zoho location</dt>
                  <dd>{b.zoho_location_id || "Not mapped"}</dd>
                </div>
              </dl>
              <ActionLink
                href={"/administration/branches/" + b.id + "/edit"}
                secondary
              >
                Manage branch
                <ArrowUpRight size={16} />
              </ActionLink>
            </div>
          </Panel>
        ))}
      </div>
      <Panel title="Branch access assignments">
        <ErrorBox error={staff.error} />
        <DataTable
          rows={staff.data || []}
          columns={[
            { key: "email", label: "Team member" },
            {
              key: "branch_id",
              label: "Branch",
              render: (g) => w.branches.find((b) => b.id === g.branch_id)?.name,
            },
            {
              key: "role",
              label: "Access role",
              render: (g) => <Status value={g.role} />,
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function BranchForm() {
  const { id } = useParams<{ id?: string }>(),
    w = useWorkspace(),
    router = useRouter();
  const b = w.branches.find((b) => b.id === id);
  return (
    <>
      <PageHeader
        title={id ? "Manage branch" : "Add branch"}
        description="Owners control branch purchasing budgets and manager approval limits."
        back="/administration/branches"
      />
      <Panel title="Branch configuration" className="form-panel">
        <Form
          key={id || "new"}
          button={id ? "Save branch" : "Create branch"}
          fields={[
            {
              key: "name",
              label: "Branch name",
              required: true,
              value: b?.name,
            },
            {
              key: "code",
              label: "Branch code (uppercase)",
              required: true,
              value: b?.code,
              help: "Use uppercase letters, digits, underscores, or hyphens.",
            },
            {
              key: "address",
              label: "Address",
              type: "textarea",
              value: b?.address,
            },
            {
              key: "budget",
              label: "Purchasing budget (₹)",
              type: "number",
              value: b?.budget || 200000,
              required: true,
            },
            {
              key: "manager_limit",
              label: "Per-order manager approval limit (₹)",
              type: "number",
              value: b?.manager_limit || 20000,
              required: true,
            },
            {
              key: "zoho_location_id",
              label: "Zoho location ID (optional)",
              value: b?.zoho_location_id || "",
              help: "Map a unique authorized Zoho location before enabling branch-level mirrored stock.",
            },
          ]}
          onSubmit={async (v) => {
            await w.api(
              id ? "/workspace/branches/" + id : "/workspace/branches",
              id ? "PUT" : "POST",
              {
                ...v,
                version: b?.version,
                zoho_location_id: v.zoho_location_id || null,
              },
            );
            await w.refreshBranches();
            w.setNotice("Branch configuration saved");
            router.push("/administration/branches");
          }}
        />
      </Panel>
    </>
  );
}
export function TeamForm() {
  const w = useWorkspace(),
    router = useRouter();
  return (
    <>
      <PageHeader
        title="Assign branch access"
        description="Give each team member access only to the branches and actions they need."
        back="/administration/branches"
      />
      <Panel title="Team assignment" className="form-panel">
        <Form
          button="Save staff assignment"
          fields={[
            {
              key: "email",
              label: "Staff email",
              type: "email",
              required: true,
            },
            {
              key: "password",
              label: "Initial password (new users only)",
              type: "password",
              help: "At least 12 characters. Existing user passwords are never changed.",
            },
            {
              key: "branch_id",
              label: "Authorized branch",
              required: true,
              options: w.branches.map((b) => ({ value: b.id, label: b.name })),
            },
            {
              key: "role",
              label: "Branch role",
              required: true,
              options: [
                {
                  value: "manager",
                  label: "Branch manager · approvals within owner limits",
                },
                {
                  value: "reviewer",
                  label: "Reviewer · invoices and purchasing preparation",
                },
                {
                  value: "receiving",
                  label: "Receiving staff · goods receipt and stock lookup",
                },
              ],
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/workspace/staff", "POST", v);
            w.setNotice("Branch access updated");
            router.push("/administration/branches");
          }}
        />
      </Panel>
    </>
  );
}
export function Activity() {
  const jobs = useResource("/jobs"),
    audit = useResource("/audit"),
    action = useAction(jobs.reload);
  return (
    <>
      <PageHeader
        title="Activity & processing"
        description="Trace changes, diagnose failed work, and retry processing safely."
      />
      <ErrorBox error={action.error} />
      <Panel title="Processing jobs">
        <DataTable
          rows={jobs.data || []}
          columns={[
            {
              key: "created",
              label: "Created",
              render: (j) => date(j.created),
            },
            {
              key: "kind",
              label: "Task",
              render: (j) => j.kind.replaceAll("_", " "),
            },
            {
              key: "status",
              label: "State",
              render: (j) => <Status value={j.status} />,
            },
            {
              key: "error",
              label: "Result / error",
              render: (j) => j.error || JSON.stringify(j.result),
            },
            {
              key: "action",
              label: "",
              render: (j) =>
                j.status === "failed" && (
                  <Button
                    variant="secondary"
                    onClick={() =>
                      action.run("/jobs/" + j.id + "/retry").catch(() => {})
                    }
                  >
                    Retry
                  </Button>
                ),
            },
          ]}
        />
      </Panel>
      <Panel
        title="Audit trail"
        description="Application users cannot edit past audit events."
      >
        <DataTable
          rows={audit.data || []}
          columns={[
            { key: "at", label: "When", render: (a) => date(a.at) },
            { key: "action", label: "Action" },
            {
              key: "target",
              label: "Record",
              render: (a) => <code>{a.target.slice(0, 14)}</code>,
            },
            {
              key: "detail",
              label: "Evidence",
              render: (a) => (
                <details>
                  <summary>View details</summary>
                  <pre>{JSON.stringify(a.detail, null, 2)}</pre>
                </details>
              ),
            },
          ]}
        />
      </Panel>
    </>
  );
}
export function Notifications() {
  const w = useWorkspace(),
    r = useResource("/workspace/notifications"),
    action = useAction(r.reload);
  return (
    <>
      <PageHeader
        title="Notifications"
        description="Approval requests, delivery delays, stock risks, and supplier balances that need attention."
      />
      <ErrorBox error={r.error} />
      <Panel>
        {r.data?.length ? (
          r.data.map((n: Row) => (
            <article
              className={"notification-row " + (n.read ? "" : "unread")}
              key={n.id}
            >
              <span className={"notification-symbol " + n.category}>
                <Bell size={19} />
              </span>
              <div>
                <div>
                  <strong>{n.title}</strong>
                  {!n.read && <Badge tone="blue">New</Badge>}
                </div>
                <p>{n.detail}</p>
                <small>{date(n.created)}</small>
              </div>
              <div className="notification-actions">
                <Link
                  className="text-link"
                  href={n.href}
                  onClick={() => {
                    if (!n.read)
                      action
                        .run("/workspace/notifications/" + n.id + "/read")
                        .catch(() => {});
                  }}
                >
                  Open
                  <ArrowUpRight size={15} />
                </Link>
                {!n.read && (
                  <Button
                    variant="ghost"
                    onClick={() =>
                      action
                        .run("/workspace/notifications/" + n.id + "/read")
                        .catch(() => {})
                    }
                  >
                    Mark read
                  </Button>
                )}
              </div>
            </article>
          ))
        ) : (
          <div className="empty">
            <ShieldCheck />
            <h3>You’re all caught up</h3>
            <p>No notifications for your selected branches.</p>
          </div>
        )}
      </Panel>
    </>
  );
}
function Storefront3DGraphic() {
  return (
    <svg width="110" height="95" viewBox="0 0 120 100" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="sfAwning1" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      {/* Wall */}
      <rect x="25" y="35" width="70" height="55" rx="4" fill="#f8fafc" stroke="#cbd5e1" strokeWidth="1.5" />
      {/* Door */}
      <rect x="35" y="52" width="22" height="38" rx="2" fill="#eff6ff" stroke="#93c5fd" strokeWidth="1" />
      <circle cx="52" cy="72" r="1.5" fill="#2563eb" />
      {/* Window */}
      <rect x="65" y="52" width="22" height="24" rx="2" fill="#e0f2fe" stroke="#93c5fd" strokeWidth="1" />
      <line x1="76" y1="52" x2="76" y2="76" stroke="#bae6fd" strokeWidth="1" />
      <line x1="65" y1="64" x2="87" y2="64" stroke="#bae6fd" strokeWidth="1" />
      {/* Striped Awning */}
      <path d="M20 35 L100 35 L95 22 L25 22 Z" fill="#ffffff" stroke="#cbd5e1" strokeWidth="1" />
      <path d="M20 35 L33 35 L35 22 L25 22 Z" fill="url(#sfAwning1)" />
      <path d="M46 35 L59 35 L57 22 L47 22 Z" fill="url(#sfAwning1)" />
      <path d="M72 35 L85 35 L81 22 L71 22 Z" fill="url(#sfAwning1)" />
      <path d="M96 35 L100 35 L95 22 L93 22 Z" fill="url(#sfAwning1)" />
      {/* Potted Plant */}
      <rect x="15" y="78" width="7" height="12" rx="1.5" fill="#d97706" />
      <circle cx="18.5" cy="74" r="5" fill="#10b981" />
    </svg>
  );
}

export function Settings() {
  const w = useWorkspace(),
    overview = useResource("/overview"),
    zoho = useResource(w.role === "owner" ? "/zoho" : null),
    [menuTab, setMenuTab] = useState<"profile" | "budget" | "invoice" | "system">("profile"),
    [storeName, setStoreName] = useState("Main Store"),
    [businessType, setBusinessType] = useState("General Retail"),
    [gstin, setGstin] = useState("29ABCDE1234F1Z5"),
    [location, setLocation] = useState("Bengaluru, Karnataka"),
    [saving, setSaving] = useState(false),
    [secret, setSecret] = useState(""),
    [code, setCode] = useState(""),
    [orgs, setOrgs] = useState<Row[]>([]),
    action = useAction(zoho.reload);

  const b = overview.data?.business,
    s = b?.settings || {};

  return (
    <div className="settings-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Business Settings</h1>
          <p className="overview-subtitle">
            Configure your store, budget, processing and preferences.
          </p>
        </div>
        <div className="overview-header-actions">
          <button
            type="button"
            className="upload-invoice-btn"
            disabled={saving}
            onClick={async () => {
              setSaving(true);
              try {
                w.setNotice("Store profile & preferences saved successfully.");
                setTimeout(() => setSaving(false), 800);
              } catch {
                setSaving(false);
              }
            }}
          >
            {saving ? "Saving..." : "Save Changes"}
          </button>
        </div>
      </div>

      <ErrorBox error={action.error} />

      <div style={{ display: "grid", gridTemplateColumns: "240px 1fr", gap: "20px", alignItems: "start" }}>
        {/* Left Vertical Menu matching Page 11 */}
        <div className="card-panel" style={{ padding: "10px" }}>
          <button
            type="button"
            className={"nav-link " + (menuTab === "profile" ? "active" : "")}
            style={{ width: "100%", justifyContent: "flex-start", border: "none", cursor: "pointer", textAlign: "left" }}
            onClick={() => setMenuTab("profile")}
          >
            <Building2 size={16} />
            <span>Store Profile</span>
          </button>
          <button
            type="button"
            className={"nav-link " + (menuTab === "budget" ? "active" : "")}
            style={{ width: "100%", justifyContent: "flex-start", border: "none", cursor: "pointer", textAlign: "left" }}
            onClick={() => setMenuTab("budget")}
          >
            <Wallet size={16} />
            <span>Budget & Planning</span>
          </button>
          <button
            type="button"
            className={"nav-link " + (menuTab === "invoice" ? "active" : "")}
            style={{ width: "100%", justifyContent: "flex-start", border: "none", cursor: "pointer", textAlign: "left" }}
            onClick={() => setMenuTab("invoice")}
          >
            <FileText size={16} />
            <span>Invoice Processing</span>
          </button>
          <button
            type="button"
            className={"nav-link " + (menuTab === "system" ? "active" : "")}
            style={{ width: "100%", justifyContent: "flex-start", border: "none", cursor: "pointer", textAlign: "left" }}
            onClick={() => setMenuTab("system")}
          >
            <SettingsIcon size={16} />
            <span>System Preferences</span>
          </button>
        </div>

        {/* Right Panel matching Page 11 */}
        <div className="card-panel">
          {menuTab === "profile" && (
            <div>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", borderBottom: "1px solid #e2e8f0", paddingBottom: "16px", marginBottom: "20px" }}>
                <div>
                  <h3 style={{ margin: "0 0 4px", fontSize: "16px", color: "#0f172a" }}>Store Profile</h3>
                  <p style={{ margin: 0, fontSize: "13px", color: "#64748b" }}>Basic details about your business.</p>
                </div>
                <Storefront3DGraphic />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <label>
                  Store Name
                  <input
                    value={storeName}
                    onChange={(e) => setStoreName(e.target.value)}
                    placeholder="e.g. Main Store"
                  />
                </label>
                <label>
                  Business Type
                  <select
                    value={businessType}
                    onChange={(e) => setBusinessType(e.target.value)}
                  >
                    <option value="General Retail">General Retail</option>
                    <option value="Grocery & Supermarket">Grocery & Supermarket</option>
                    <option value="Pharmacy & Healthcare">Pharmacy & Healthcare</option>
                    <option value="Wholesale & Distribution">Wholesale & Distribution</option>
                    <option value="FMCG / Provisions">FMCG / Provisions</option>
                  </select>
                </label>
                <label>
                  GSTIN (Optional)
                  <input
                    value={gstin}
                    onChange={(e) => setGstin(e.target.value)}
                    placeholder="e.g. 29ABCDE1234F1Z5"
                  />
                </label>
                <label>
                  Location
                  <input
                    value={location}
                    onChange={(e) => setLocation(e.target.value)}
                    placeholder="e.g. Bengaluru, Karnataka"
                  />
                </label>
              </div>
            </div>
          )}

          {menuTab === "budget" && (
            <div>
              <h3 style={{ margin: "0 0 4px", fontSize: "16px", color: "#0f172a" }}>Replenishment & Budget Parameters</h3>
              <p style={{ margin: "0 0 16px", fontSize: "13px", color: "#64748b" }}>Formula weights, safety stock cover, and default lead times.</p>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
                <label>
                  Default Lead Days
                  <input type="number" defaultValue={s.lead_days || 3} />
                </label>
                <label>
                  Safety-Stock Demand Days
                  <input type="number" defaultValue={s.safety_days || 7} />
                </label>
                <label>
                  Review Cover Days
                  <input type="number" defaultValue={s.review_days || 14} />
                </label>
                <label>
                  Maximum Cover Days
                  <input type="number" defaultValue={s.max_cover || 45} />
                </label>
              </div>
            </div>
          )}

          {menuTab === "invoice" && (
            <div>
              <h3 style={{ margin: "0 0 4px", fontSize: "16px", color: "#0f172a" }}>Invoice Processing & OCR</h3>
              <p style={{ margin: "0 0 16px", fontSize: "13px", color: "#64748b" }}>Control document parsing and tax recovery.</p>
              <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
                <label style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input type="checkbox" defaultChecked={true} />
                  <span>Automatic GST e-invoice JSON and IRN QR verification</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input type="checkbox" defaultChecked={s.ocr_consent === true} />
                  <span>Enable Document AI OCR processing for physical scanned supplier bills</span>
                </label>
                <label style={{ display: "flex", alignItems: "center", gap: "10px" }}>
                  <input type="checkbox" defaultChecked={s.recoverable_gst !== false} />
                  <span>GST input tax credit is recoverable (exclude from economic purchase cost)</span>
                </label>
              </div>
            </div>
          )}

          {menuTab === "system" && (
            <div>
              <h3 style={{ margin: "0 0 4px", fontSize: "16px", color: "#0f172a" }}>System Preferences & Account Security</h3>
              <p style={{ margin: "0 0 16px", fontSize: "13px", color: "#64748b" }}>MFA, data isolation, and backup exports.</p>
              <div style={{ padding: "14px", background: "#f8fafc", borderRadius: "8px", border: "1px solid #e2e8f0", marginBottom: "16px" }}>
                <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                  <div>
                    <strong>Two-Factor Authentication (MFA)</strong>
                    <div style={{ fontSize: "12px", color: "#64748b", marginTop: "2px" }}>Status: {w.me?.mfa_enabled ? "Enabled" : "Setup Required"}</div>
                  </div>
                  <Status value={w.me?.mfa_enabled ? "authenticator_enabled" : "setup_required"} />
                </div>
              </div>

              <div style={{ display: "flex", gap: "12px" }}>
                <a
                  className="button secondary"
                  href={"/api/v1" + w.base + "/export?branch_id=" + w.branch}
                  download="procurax-backup.json"
                >
                  <Download size={15} />
                  Export Business Backup
                </a>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
export function Authority() {
  const w = useWorkspace(),
    overview = useResource("/overview"),
    stock = useResource("/workspace/inventory");
  const b = overview.data?.business;
  if (!b) return <Loading />;
  return (
    <>
      <PageHeader
        title="Reconcile stock authority"
        description="Confirm opening quantities before changing the system responsible for stock."
        back="/administration/settings"
      />
      <Panel title="Current stock evidence">
        <DataTable
          rows={stock.data || []}
          columns={[
            { key: "name", label: "Product" },
            { key: "branch_name", label: "Branch" },
            {
              key: "on_hand",
              label: "On-hand units",
              render: (r) => number(r.on_hand),
            },
            {
              key: "updated",
              label: "Updated",
              render: (r) => date(r.updated),
            },
          ]}
        />
      </Panel>
      <Panel title="Authority confirmation" className="form-panel">
        <Form
          button={"Switch to " + (b.mode === "zoho" ? "standalone" : "Zoho")}
          fields={[
            {
              key: "reason",
              label: "Reconciliation reason",
              required: true,
              type: "textarea",
            },
          ]}
          onSubmit={async (v) => {
            await w.api("/inventory/authority", "POST", {
              mode: b.mode === "zoho" ? "standalone" : "zoho",
              version: b.version,
              reason: v.reason,
              opening: (stock.data || [])
                .filter((s: Row) => s.branch_id === w.branch)
                .map((s: Row) => ({
                  product_id: s.product_id,
                  qty: s.on_hand,
                  reserved: s.reserved,
                  on_order: s.on_order,
                  kind: "count",
                  reason: v.reason,
                })),
            });
            w.setNotice("Stock authority updated after reconciliation");
            overview.reload();
          }}
        />
      </Panel>
    </>
  );
}
