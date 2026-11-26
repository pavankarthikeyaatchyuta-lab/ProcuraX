"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Layers3,
  LayoutDashboard,
  ShoppingBag,
  FileText,
  Package,
  Truck,
  TrendingUp,
  Users,
  Settings,
  Bell,
  Search,
  Menu,
  X,
  LogOut,
  Building2,
  Activity,
  ChevronDown,
  ChevronRight,
  Sparkles,
  ShieldAlert,
  Bot,
  RefreshCw,
  Home,
  Store,
  CheckCheck,
  Camera,
  LayoutGrid,
  Boxes,
  SlidersHorizontal,
} from "lucide-react";
import { useWorkspace, useResource } from "./workspace";
import { Loading } from "./ui";
import { RealtimeProvider, LivePulseBadge } from "./realtime-provider";
import { QuickActionsBar } from "./quick-actions";

export function ProcuraXLogo({ size = 30 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <linearGradient id="px-c1" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#2563eb" />
        </linearGradient>
        <linearGradient id="px-c2" x1="0" y1="20" x2="20" y2="40" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#1d4ed8" />
          <stop offset="100%" stopColor="#0f172a" />
        </linearGradient>
        <filter id="px-glow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      <path d="M20 3 L36 12 L36 28 L20 37 L4 28 L4 12 Z" fill="url(#px-c2)" />
      <path d="M20 3 L36 12 L20 21 L4 12 Z" fill="#60a5fa" opacity="0.85" />
      <path d="M20 21 L36 12 L36 28 L20 37 Z" fill="url(#px-c1)" />
      <path d="M20 21 L4 12 L4 28 L20 37 Z" fill="#1e40af" />
      <path d="M20 9 L31 15 L20 21 L9 15 Z" fill="#93c5fd" opacity="0.9" />
      <path d="M16 16 L23 16 C25 16 26 17 26 19 C26 21 25 22 23 22 L19 22 L19 27 L16 27 Z M19 18.5 L19 20 L22.5 20 C23 20 23.5 19.7 23.5 19.2 C23.5 18.8 23 18.5 22.5 18.5 Z" fill="#ffffff" filter="url(#px-glow)" />
    </svg>
  );
}

const navigation = [
  {
    group: "WORKSPACE",
    items: [["Overview", "/overview", LayoutDashboard]],
  },
  {
    group: "PURCHASING",
    items: [
      ["Purchase Planner", "/purchasing/planner", TrendingUp],
      ["Invoices & Receipts", "/purchasing/invoices", FileText],
      ["Purchase Orders", "/purchasing/orders", ShoppingBag],
      ["Suppliers", "/intelligence/suppliers", Users],
    ],
  },
  {
    group: "INVENTORY",
    items: [
      ["Stock & Ledger", "/inventory/stock", Layers3],
      ["Product Catalog", "/inventory/products", Package],
      ["Goods Receiving", "/inventory/receiving", Truck],
    ],
  },
  {
    group: "INTELLIGENCE",
    items: [
      ["Profit Leak Detector", "/intelligence/profit-leaks", ShieldAlert],
      ["Local Market Demand", "/intelligence/local-demand", Sparkles],
      ["AI Business Assistant", "/intelligence/assistant", Bot],
    ],
  },
  {
    group: "SETTINGS",
    items: [
      ["Business Settings", "/administration/settings", Settings],
      ["Activity & Audit", "/administration/activity", Activity],
    ],
  },
] as const;

function MobileBottomNav({
  path,
  onOpenMenu,
}: {
  path: string;
  onOpenMenu: () => void;
}) {
  const isOverview = path === "/overview" || path === "/";
  const isPlanner = path.startsWith("/purchasing/planner");
  const isInvoices = path.startsWith("/purchasing/invoices");
  const isStock = path.startsWith("/inventory");

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile Navigation">
      <Link
        href="/overview"
        className={`mobile-nav-btn ${isOverview ? "active" : ""}`}
      >
        <LayoutGrid size={18} />
        <span>Home</span>
      </Link>

      <Link
        href="/purchasing/planner"
        className={`mobile-nav-btn ${isPlanner ? "active" : ""}`}
      >
        <TrendingUp size={18} />
        <span>Planner</span>
      </Link>

      {/* Center elevated scan button for mobile quick invoice/bill scanning */}
      <Link
        href="/purchasing/invoices"
        className={`mobile-nav-fab ${isInvoices ? "active" : ""}`}
        aria-label="Scan or upload invoice"
      >
        <div className="mobile-fab-icon-wrap">
          <Camera size={19} />
        </div>
        <span className="mobile-fab-title">Scan</span>
      </Link>

      <Link
        href="/inventory/stock"
        className={`mobile-nav-btn ${isStock ? "active" : ""}`}
      >
        <Boxes size={18} />
        <span>Stock</span>
      </Link>

      <button
        type="button"
        className="mobile-nav-btn"
        onClick={onOpenMenu}
        aria-label="Open full menu"
      >
        <SlidersHorizontal size={18} />
        <span>Menu</span>
      </button>
    </nav>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  const w = useWorkspace(),
    path = usePathname(),
    router = useRouter(),
    [open, setOpen] = useState(false),
    [search, setSearch] = useState(""),
    [showResetModal, setShowResetModal] = useState(false),
    [resetting, setResetting] = useState(false);

  const notifications = useResource(
    w.business && w.branch ? "/workspace/notifications" : null,
  );

  useEffect(() => {
    if (!w.loading && !w.me) router.replace("/login");
  }, [w.me, w.loading, router]);

  useEffect(() => {
    setOpen(false);
  }, [path]);

  useEffect(() => {
    const timer = setInterval(notifications.reload, 60000);
    return () => clearInterval(timer);
  }, [w.business, w.branch]);

  if (w.loading || !w.me) return <Loading />;
  const business = w.me.businesses.find((b: any) => b.id === w.business);
  const unread = (notifications.data || []).filter((n: any) => !n.read).length;

  const handleResetCleanSlate = async (wipeCatalog: boolean = false) => {
    setResetting(true);
    try {
      await w.api(
        `/businesses/${w.business}/reset-data?wipe_catalog=${wipeCatalog}`,
        "POST",
      );
      w.setNotice(
        "All sample data purged. Store is now operating on zero default data in real-time.",
      );
      setShowResetModal(false);
      window.location.reload();
    } catch (err: any) {
      alert(err.message || "Failed to reset business data");
    } finally {
      setResetting(false);
    }
  };

  const getBreadcrumbs = () => {
    const parts = path.split("/").filter(Boolean);
    if (parts.length === 0 || parts[0] === "overview") {
      return (
        <div className="breadcrumbs">
          <Home size={15} className="breadcrumb-home" />
          <span className="breadcrumb-sep">/</span>
          <strong className="breadcrumb-current">Overview</strong>
        </div>
      );
    }
    const sectionName =
      parts[0] === "purchasing"
        ? "Purchasing"
        : parts[0] === "inventory"
          ? "Inventory"
          : parts[0] === "intelligence"
            ? "Intelligence"
            : parts[0] === "administration"
              ? "Administration"
              : parts[0];

    let pageTitle = parts[1] || "";
    for (const group of navigation) {
      for (const item of group.items) {
        if (item[1] === path) {
          pageTitle = item[0];
          break;
        }
      }
    }
    if (!pageTitle && parts[1]) {
      pageTitle = parts[1].replace(/-/g, " ");
      pageTitle = pageTitle.charAt(0).toUpperCase() + pageTitle.slice(1);
    }

    return (
      <div className="breadcrumbs">
        <Home size={15} className="breadcrumb-home" />
        <span className="breadcrumb-sep">/</span>
        <span className="breadcrumb-section">{sectionName}</span>
        <ChevronRight size={13} className="breadcrumb-chevron" />
        <strong className="breadcrumb-current">{pageTitle}</strong>
      </div>
    );
  };

  return (
    <RealtimeProvider businessId={w.business}>
      <div className="app">
        <aside className={"sidebar " + (open ? "is-open" : "")}>
          <div className="sidebar-header-row">
            <Link href="/overview" className="procurax-brand">
              <ProcuraXLogo size={32} />
              <div className="brand-text">
                <span className="brand-title">ProcuraX</span>
                <span className="brand-subtitle">AI Procurement Intelligence for MSMEs</span>
              </div>
            </Link>
            <button
              type="button"
              className="sidebar-close-btn"
              aria-label="Close navigation"
              onClick={() => setOpen(false)}
            >
              <X size={18} />
            </button>
          </div>

          <div className="store-selector-card">
            <div className="store-selector-left">
              <Store size={16} className="store-icon" />
              <select
                aria-label="Active store"
                value={w.business}
                onChange={(e) => w.setBusiness(e.target.value)}
                className="store-select"
              >
                {w.me.businesses.map((b: any) => (
                  <option value={b.id} key={b.id}>
                    {b.name === "My Retail Store" ? "Main Store" : b.name}
                  </option>
                ))}
              </select>
            </div>
            <ChevronDown size={14} className="store-chevron" />
          </div>

          <nav className="sidebar-nav">
            {navigation.map((group) => (
              <div className="nav-group" key={group.group}>
                <p className="nav-group-title">{group.group}</p>
                {group.items
                  .filter(
                    ([label, href]) =>
                      w.role !== "receiving" ||
                      [
                        "/overview",
                        "/inventory/stock",
                        "/inventory/receiving",
                      ].includes(href),
                  )
                  .map(([label, href, Icon]) => {
                    const isActive =
                      path === href ||
                      (href !== "/overview" && path.startsWith(href + "/"));
                    return (
                      <Link
                        key={href}
                        href={href}
                        className={
                          isActive ? "nav-link active" : "nav-link"
                        }
                      >
                        <Icon size={17} className="nav-icon" />
                        <span className="nav-label">{label}</span>
                      </Link>
                    );
                  })}
              </div>
            ))}
          </nav>

          <div className="sidebar-profile">
            <span className="avatar">
              {w.me.email?.slice(0, 2).toUpperCase()}
            </span>
            <div className="profile-info">
              <strong>
                {w.role === "manager"
                  ? "Branch manager"
                  : w.role === "owner"
                    ? "Business owner"
                    : w.role === "receiving"
                      ? "Receiving staff"
                      : "Reviewer"}
              </strong>
              <small>{w.me.email}</small>
            </div>
            <button
              aria-label="Sign out"
              className="signout-button"
              onClick={async () => {
                await w.api("/auth/logout", "POST");
                await w.profile();
                router.replace("/login");
              }}
            >
              <LogOut size={16} />
            </button>
          </div>
        </aside>

        {open && (
          <button
            className="nav-scrim"
            aria-label="Close navigation"
            onClick={() => setOpen(false)}
          />
        )}

        <div className="main">
          <header className="topbar">
            <button
              className="icon-button mobile-toggle"
              aria-label="Open navigation"
              onClick={() => setOpen(true)}
            >
              <SlidersHorizontal size={16} />
            </button>

            <Link href="/overview" className="mobile-topbar-brand">
              <ProcuraXLogo size={20} />
              <span className="mobile-brand-title">ProcuraX</span>
            </Link>

            {getBreadcrumbs()}

            <div className="topbar-actions">
              <form
                className="global-search-pill"
                onSubmit={(e) => {
                  e.preventDefault();
                  router.push(
                    "/inventory/products?q=" + encodeURIComponent(search),
                  );
                }}
              >
                <Search size={15} className="search-icon" />
                <input
                  aria-label="Search products, suppliers, invoices"
                  placeholder="Search products, suppliers, invoices..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
                <kbd className="search-kbd">⌘ K</kbd>
              </form>

              <div className="branch-selector-pill">
                <Building2 size={14} />
                <select
                  aria-label="Selected branch"
                  value={w.branch}
                  onChange={(e) => w.setBranch(e.target.value)}
                >
                  {w.branches.length > 1 && (
                    <option value="all">All authorized branches</option>
                  )}
                  {w.branches.map((b) => (
                    <option key={b.id} value={b.id}>
                      {b.name}
                    </option>
                  ))}
                </select>
                <ChevronDown size={12} />
              </div>

              <LivePulseBadge />

              <Link
                className="notification-pill-btn"
                href="/notifications"
                aria-label={`Notifications, ${unread} unread`}
              >
                <Bell size={18} />
                {unread > 0 ? (
                  <span className="notif-badge">{unread > 9 ? "9+" : unread}</span>
                ) : (
                  <span className="notif-dot" />
                )}
              </Link>

              <div className="topbar-store-avatar" title={business?.name || "Store"}>
                <Store size={17} color="#ffffff" />
              </div>
            </div>
          </header>

          <main className="workspace-content">
            {business?.demo && (
              <div className="demo-strip">
                <div className="demo-strip-left">
                  <span className="demo-pulse-dot" />
                  <span>
                    Demo workspace <span className="demo-sep">·</span> Sample data for exploring the procurement workflow
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() => setShowResetModal(true)}
                  className="reset-clean-btn"
                >
                  <RefreshCw size={12} />
                  Reset to Clean Slate (Zero Default Data)
                </button>
              </div>
            )}

            {w.notice && (
              <div className="success" role="status">
                <CheckCheck size={18} />
                {w.notice}
                <button
                  aria-label="Dismiss message"
                  onClick={() => w.setNotice("")}
                >
                  <X size={16} />
                </button>
              </div>
            )}

            {w.business && w.branch ? (
              <>
                <QuickActionsBar />
                {children}
              </>
            ) : (
              <div className="onboarding-empty">
                <h1>Welcome to ProcuraX</h1>
                <p>
                  Create a business and its first branch in Settings to get
                  started.
                </p>
                <Link href="/administration/settings" className="button primary">
                  Set up your business
                </Link>
                {path.includes("settings") && children}
              </div>
            )}

            <footer className="procurax-footer">
              <span className="footer-brand">ProcuraX · AI Procurement Intelligence for MSMEs</span>
              <span className="footer-meta">INR · Asia/Kolkata</span>
            </footer>
          </main>
        </div>

        {/* Mobile Fixed Bottom Navigation Bar */}
        <MobileBottomNav path={path} onOpenMenu={() => setOpen(true)} />

        {showResetModal && (
          <div className="modal-overlay">
            <div className="modal-box">
              <div className="modal-header">
                <span className="modal-icon-wrap">
                  <RefreshCw size={18} />
                </span>
                <div>
                  <h3>Reset to Clean Slate</h3>
                  <span className="modal-subtitle">Operate on zero default data in real-time</span>
                </div>
              </div>
              <p className="modal-body-text">
                This will purge all mock purchase orders, supplier invoices, sales transactions, unmet customer requests, and price anomalies.
                Your business and staff accounts will remain intact. Choose how you would like to reset:
              </p>
              <div className="modal-options">
                <button
                  type="button"
                  disabled={resetting}
                  onClick={() => handleResetCleanSlate(false)}
                  className="reset-option-card"
                >
                  <strong>Clean Transactions Only (Recommended)</strong>
                  <span>Keeps product names and suppliers registered, but resets all stock to 0 and clears all history.</span>
                </button>
                <button
                  type="button"
                  disabled={resetting}
                  onClick={() => handleResetCleanSlate(true)}
                  className="reset-option-card danger"
                >
                  <strong>Complete Wipe (100% Empty Canvas)</strong>
                  <span>Deletes products, quotes, suppliers, and all transactions. Start completely fresh.</span>
                </button>
              </div>
              <div className="modal-actions">
                <button
                  type="button"
                  disabled={resetting}
                  onClick={() => setShowResetModal(false)}
                  className="button secondary"
                >
                  Cancel
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </RealtimeProvider>
  );
}