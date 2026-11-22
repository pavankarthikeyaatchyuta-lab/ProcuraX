"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { useRealtime } from "./realtime-provider";
import {
  Truck,
  ShoppingCart,
  Package,
  ShieldAlert,
  Sparkles,
  BarChart3,
  Zap,
  ChevronRight,
  Upload,
  Calendar,
  ChevronDown,
  TrendingDown,
  TrendingUp,
} from "lucide-react";
import {
  useResource,
  useWorkspace,
  money,
  number,
  type Row,
} from "./workspace";
import { Loading, ErrorBox } from "./ui";

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning!";
  if (hour < 17) return "Good afternoon!";
  return "Good evening!";
}

function GlassCube3D() {
  return (
    <svg width="220" height="130" viewBox="0 0 240 140" fill="none" xmlns="http://www.w3.org/2000/svg">
      <defs>
        <radialGradient id="bannerGlow" cx="50%" cy="50%" r="50%">
          <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.4" />
          <stop offset="100%" stopColor="#1e3a8a" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="cubeTop" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#60a5fa" stopOpacity="0.95" />
          <stop offset="100%" stopColor="#38bdf8" stopOpacity="0.9" />
        </linearGradient>
        <linearGradient id="cubeLeft" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#1d4ed8" stopOpacity="0.85" />
        </linearGradient>
        <linearGradient id="cubeRight" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1e40af" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#0f172a" stopOpacity="0.85" />
        </linearGradient>
        <filter id="badgeGlow" x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation="3" result="blur" />
          <feComposite in="SourceGraphic" in2="blur" operator="over" />
        </filter>
      </defs>
      
      {/* Background radial halo */}
      <ellipse cx="120" cy="75" rx="90" ry="45" fill="url(#bannerGlow)" />
      
      {/* Floating Base Rings */}
      <ellipse cx="120" cy="85" rx="70" ry="24" stroke="#60a5fa" strokeWidth="1.5" strokeOpacity="0.4" strokeDasharray="4 3" />
      <ellipse cx="120" cy="85" rx="52" ry="18" fill="#1e3a8a" fillOpacity="0.3" stroke="#93c5fd" strokeWidth="1" strokeOpacity="0.5" />

      {/* 3D Isometric Crystal Cube in Center */}
      <g transform="translate(98, 40)">
        {/* Top Face */}
        <polygon points="22,0 44,11 22,22 0,11" fill="url(#cubeTop)" stroke="#93c5fd" strokeWidth="1" />
        {/* Left Face */}
        <polygon points="0,11 22,22 22,44 0,33" fill="url(#cubeLeft)" stroke="#3b82f6" strokeWidth="1" />
        {/* Right Face */}
        <polygon points="22,22 44,11 44,33 22,44" fill="url(#cubeRight)" stroke="#1d4ed8" strokeWidth="1" />
        {/* Inner Glowing Monogram */}
        <path d="M19 14 L25 14 C26.5 14 27.5 14.8 27.5 16 C27.5 17.2 26.5 18 25 18 L21.5 18 L21.5 22 L19 22 Z" fill="#ffffff" filter="url(#badgeGlow)" />
      </g>

      {/* Orbiting Glass Feature Badges */}
      {/* Top Left: Cart */}
      <g transform="translate(42, 28)">
        <rect width="28" height="28" rx="7" fill="#1e293b" fillOpacity="0.8" stroke="#38bdf8" strokeWidth="1.2" />
        <path d="M7 9 L10 9 L12 18 L21 18 L23 11 L10.5 11" stroke="#38bdf8" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" fill="none" />
        <circle cx="13" cy="20" r="1.2" fill="#38bdf8" />
        <circle cx="19" cy="20" r="1.2" fill="#38bdf8" />
      </g>

      {/* Top Right: Inventory / Package */}
      <g transform="translate(172, 30)">
        <rect width="28" height="28" rx="7" fill="#1e293b" fillOpacity="0.8" stroke="#38bdf8" strokeWidth="1.2" />
        <path d="M8 12 L14 8 L20 12 L14 16 Z" stroke="#38bdf8" strokeWidth="1.2" fill="none" />
        <path d="M8 12 L8 18 L14 22 L14 16" stroke="#38bdf8" strokeWidth="1.2" fill="none" />
        <path d="M20 12 L20 18 L14 22" stroke="#38bdf8" strokeWidth="1.2" fill="none" />
      </g>

      {/* Bottom Left: Bar Chart */}
      <g transform="translate(48, 76)">
        <rect width="28" height="28" rx="7" fill="#1e293b" fillOpacity="0.8" stroke="#60a5fa" strokeWidth="1.2" />
        <line x1="10" y1="21" x2="10" y2="15" stroke="#60a5fa" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="14" y1="21" x2="14" y2="11" stroke="#60a5fa" strokeWidth="1.8" strokeLinecap="round" />
        <line x1="18" y1="21" x2="18" y2="8" stroke="#60a5fa" strokeWidth="1.8" strokeLinecap="round" />
      </g>

      {/* Bottom Right: Target / Sparkle */}
      <g transform="translate(166, 76)">
        <rect width="28" height="28" rx="7" fill="#1e293b" fillOpacity="0.8" stroke="#c084fc" strokeWidth="1.2" />
        <circle cx="14" cy="14" r="7" stroke="#c084fc" strokeWidth="1.2" fill="none" />
        <circle cx="14" cy="14" r="3" stroke="#c084fc" strokeWidth="1.2" fill="none" />
        <circle cx="14" cy="14" r="1" fill="#c084fc" />
      </g>
    </svg>
  );
}

export function Overview() {
  const { branch } = useWorkspace(),
    [period, setPeriod] = useState("30"),
    [trendPeriod, setTrendPeriod] = useState("6m");

  const start = new Date(Date.now() - Number(period) * 86400000)
    .toISOString()
    .slice(0, 10);
  const report = useResource("/workspace/reports?start=" + start),
    orders = useResource("/workspace/orders?page_size=10"),
    products = useResource("/products"),
    leaks = useResource("/profit-leaks"),
    demand = useResource("/local-demand");

  const { client } = useRealtime();

  useEffect(() => {
    if (!client) return;
    const unsub = client.subscribe(() => {
      report.reload();
      orders.reload();
      products.reload();
      leaks.reload();
      demand.reload();
    });
    return unsub;
  }, [client, report, orders, products, leaks, demand]);

  const r = report.data;

  if (!r) {
    return (
      <div className="overview-page">
        <div className="overview-header">
          <div>
            <h1 className="overview-title">{getGreeting()}</h1>
            <p className="overview-subtitle">Here's your procurement and business performance at a glance.</p>
          </div>
        </div>
        <ErrorBox error={report.error} />
        <Loading />
      </div>
    );
  }

  // Calculate actual dynamic values
  const pendingOrders = (orders.data?.items || []).filter((o: Row) =>
    ["ordered", "partially_received"].includes(o.status),
  );
  const inboundCount = pendingOrders.length;
  const inTransitAmount = pendingOrders.reduce(
    (sum: number, o: Row) => sum + (Number(o.total) || 0),
    0,
  );
  const inTransitDisplay = money(inTransitAmount);

  const totalSKUs = Array.isArray(products.data)
    ? products.data.length
    : Array.isArray(products.data?.items)
      ? products.data.items.length
      : Array.isArray(r.stock)
        ? r.stock.length
        : 0;
  const riskProducts = (r.stock || []).filter((s: Row) => s.risk !== "healthy");
  const lowStockCount = riskProducts.length;

  const leakAlertsCount = leaks.data?.anomalies?.length ?? 0;
  const leakEstImpact = leaks.data?.summary?.estimated_total_leakage
    ? money(leaks.data.summary.estimated_total_leakage)
    : money(0);

  const demandRequestsCount = demand.data?.requests?.length ?? 0;

  // Monthly purchase trends mock or dynamic
  const trendMonths = [
    { month: "Jul", value: "₹1.8L", heightPercent: 45 },
    { month: "Aug", value: "₹2.2L", heightPercent: 55 },
    { month: "Sep", value: "₹2.5L", heightPercent: 63 },
    { month: "Oct", value: "₹2.1L", heightPercent: 52 },
    { month: "Nov", value: "₹2.9L", heightPercent: 72 },
    { month: "Dec", value: "₹3.4L", heightPercent: 88 },
  ];

  return (
    <div className="overview-page">
      {/* 1. Header Section */}
      <div className="overview-header">
        <div>
          <h1 className="overview-title">{getGreeting()}</h1>
          <p className="overview-subtitle">
            Here's your procurement and business performance at a glance.
          </p>
        </div>
        <div className="overview-header-actions">
          <div className="period-dropdown-btn">
            <Calendar size={15} style={{ color: "#64748b" }} />
            <select
              aria-label="Period selector"
              value={period}
              onChange={(e) => setPeriod(e.target.value)}
            >
              <option value="30">Last 30 days</option>
              <option value="90">Last 90 days</option>
              <option value="180">Last 180 days</option>
            </select>
            <ChevronDown size={13} style={{ color: "#64748b" }} />
          </div>

          <Link href="/purchasing/invoices" className="upload-invoice-btn">
            <Upload size={15} />
            + Upload Invoice
          </Link>
        </div>
      </div>

      {/* 2. Top 5 Pastel KPI Cards */}
      <div className="kpi-row">
        {/* Card 1: Inbound Deliveries */}
        <Link href="/inventory/receiving" className="kpi-card kpi-card-blue">
          <div className="kpi-card-top">
            <div className="kpi-card-title-group">
              <div className="kpi-icon-wrap" style={{ color: "#2563eb" }}>
                <Truck size={17} />
              </div>
              <span className="kpi-title">Inbound Deliveries</span>
            </div>
            <div className="kpi-chevron">
              <ChevronRight size={14} />
            </div>
          </div>
          <div>
            <div className="kpi-value">{inboundCount}</div>
            <div className="kpi-subtext">
              <span>{inTransitDisplay} in transit</span>
            </div>
          </div>
        </Link>

        {/* Card 2: Purchasing */}
        <Link href="/purchasing/orders" className="kpi-card kpi-card-green">
          <div className="kpi-card-top">
            <div className="kpi-card-title-group">
              <div className="kpi-icon-wrap" style={{ color: "#10b981" }}>
                <ShoppingCart size={17} />
              </div>
              <span className="kpi-title">Purchasing</span>
            </div>
            <div className="kpi-chevron">
              <ChevronRight size={14} />
            </div>
          </div>
          <div>
            <div className="kpi-value">
              {r.purchase_total > 0 ? money(r.purchase_total) : money(0)}
            </div>
            <div className="kpi-subtext" style={{ color: r.purchase_total > 0 ? "#10b981" : "#64748b" }}>
              <span>{r.purchase_total > 0 ? "↑ Active purchasing" : "No purchases in period"}</span>
            </div>
          </div>
        </Link>

        {/* Card 3: Inventory */}
        <Link href="/inventory/stock" className="kpi-card kpi-card-amber">
          <div className="kpi-card-top">
            <div className="kpi-card-title-group">
              <div className="kpi-icon-wrap" style={{ color: "#f59e0b" }}>
                <Package size={17} />
              </div>
              <span className="kpi-title">Inventory</span>
            </div>
            <div className="kpi-chevron">
              <ChevronRight size={14} />
            </div>
          </div>
          <div>
            <div className="kpi-value">{number(totalSKUs)} SKUs</div>
            <div className="kpi-subtext" style={{ color: "#b45309" }}>
              <span>● {lowStockCount} items need attention</span>
            </div>
          </div>
        </Link>

        {/* Card 4: Profit Leaks */}
        <Link href="/intelligence/profit-leaks" className="kpi-card kpi-card-red">
          <div className="kpi-card-top">
            <div className="kpi-card-title-group">
              <div className="kpi-icon-wrap" style={{ color: "#ef4444" }}>
                <ShieldAlert size={17} />
              </div>
              <span className="kpi-title">Profit Leaks</span>
            </div>
            <div className="kpi-chevron">
              <ChevronRight size={14} />
            </div>
          </div>
          <div>
            <div className="kpi-value">{leakAlertsCount} alerts</div>
            <div className="kpi-subtext" style={{ color: "#e11d48" }}>
              <span>↗ Est. {leakEstImpact} impact</span>
            </div>
          </div>
        </Link>

        {/* Card 5: Local Demand */}
        <Link href="/intelligence/local-demand" className="kpi-card kpi-card-sky">
          <div className="kpi-card-top">
            <div className="kpi-card-title-group">
              <div className="kpi-icon-wrap" style={{ color: "#0284c7" }}>
                <Sparkles size={17} />
              </div>
              <span className="kpi-title">Local Demand</span>
            </div>
            <div className="kpi-chevron">
              <ChevronRight size={14} />
            </div>
          </div>
          <div>
            <div className="kpi-value">{demandRequestsCount} requests</div>
            <div className="kpi-subtext" style={{ color: "#0284c7" }}>
              <span>↑ +33% vs. last period</span>
            </div>
          </div>
        </Link>
      </div>

      {/* 3. AI Procurement Intelligence Hero Banner */}
      <div className="ai-procurement-banner">
        <div className="ai-banner-content">
          <div className="ai-banner-pill">
            <Sparkles size={12} />
            AI Procurement Intelligence
          </div>
          <h2 className="ai-banner-heading">Make smarter purchase decisions.</h2>
          <p className="ai-banner-sub">
            Connect invoices, stock, supplier prices and local demand — all in one place.
          </p>
          <div className="ai-banner-benefits">
            <span className="ai-benefit-chip">
              <TrendingDown size={14} color="#38bdf8" />
              Lower purchase cost
            </span>
            <span className="ai-benefit-chip">
              <Package size={14} color="#60a5fa" />
              Avoid stockouts
            </span>
            <span className="ai-benefit-chip">
              <TrendingUp size={14} color="#4ade80" />
              Improve margins
            </span>
          </div>
        </div>

        <div className="glass-cube-illustration">
          <GlassCube3D />
        </div>
      </div>

      {/* 4. Bottom 2-Column Section */}
      <div className="overview-bottom-grid">
        {/* Left Column: Purchase Trend Bar Chart */}
        <div className="card-panel">
          <div className="panel-header-row">
            <div className="panel-title-group">
              <div className="panel-icon-wrap" style={{ background: "#eff6ff", color: "#2563eb" }}>
                <BarChart3 size={18} />
              </div>
              <div className="panel-title-text">
                <h3>Purchase Trend</h3>
                <p>Total purchase value over time</p>
              </div>
            </div>
            <div className="panel-dropdown-pill">
              <select
                aria-label="Trend duration"
                value={trendPeriod}
                onChange={(e) => setTrendPeriod(e.target.value)}
              >
                <option value="6m">Last 6 months</option>
                <option value="12m">Last 12 months</option>
              </select>
              <ChevronDown size={12} />
            </div>
          </div>

          <div className="trend-chart-container">
            <div className="trend-y-axis">
              <span>₹4.0L</span>
              <span>₹3.0L</span>
              <span>₹2.0L</span>
              <span>₹1.0L</span>
              <span>₹0</span>
            </div>
            <div className="trend-bars-wrapper">
              {trendMonths.map((bar) => (
                <div key={bar.month} className="trend-bar-col" title={`${bar.month}: ${bar.value}`}>
                  <div
                    className="trend-bar-fill"
                    style={{ height: `${bar.heightPercent}%` }}
                  />
                  <span>{bar.month}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Today's Priorities */}
        <div className="card-panel">
          <div className="panel-header-row">
            <div className="panel-title-group">
              <div className="panel-icon-wrap" style={{ background: "#fef3c7", color: "#d97706" }}>
                <Zap size={18} />
              </div>
              <div className="panel-title-text">
                <h3>Today's Priorities</h3>
                <p>Recommended actions to keep your business in control.</p>
              </div>
            </div>
          </div>

          <div className="priorities-list">
            <Link href="/purchasing/planner" className="priority-card-item priority-item-blue">
              <div className="priority-item-left">
                <div className="priority-icon-circle">
                  <Package size={17} />
                </div>
                <div className="priority-text-block">
                  <strong>Reorder 8 low-stock products</strong>
                  <span>Avoid potential stockouts</span>
                </div>
              </div>
              <div className="priority-arrow">→</div>
            </Link>

            <Link href="/intelligence/profit-leaks" className="priority-card-item priority-item-red">
              <div className="priority-item-left">
                <div className="priority-icon-circle">
                  <ShieldAlert size={17} />
                </div>
                <div className="priority-text-block">
                  <strong>Review 3 price increase alerts</strong>
                  <span>Check supplier price changes and margin impact</span>
                </div>
              </div>
              <div className="priority-arrow">→</div>
            </Link>

            <Link href="/intelligence/local-demand" className="priority-card-item priority-item-sky">
              <div className="priority-item-left">
                <div className="priority-icon-circle">
                  <Sparkles size={17} />
                </div>
                <div className="priority-text-block">
                  <strong>Address 5 pending customer requests</strong>
                  <span>Capture demand and avoid lost sales</span>
                </div>
              </div>
              <div className="priority-arrow">→</div>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}


export function SpendChart({ data }: { data?: Array<{ label?: string; month?: string; amount?: number; total?: number }> }) {
  const chartData = (data && data.length > 0)
    ? data.map((d: any) => ({
        label: d.label || d.month || "Period",
        amount: Number(d.amount ?? d.total ?? 0),
      }))
    : [
        { label: "Jul", amount: 180000 },
        { label: "Aug", amount: 220000 },
        { label: "Sep", amount: 250000 },
        { label: "Oct", amount: 210000 },
        { label: "Nov", amount: 290000 },
        { label: "Dec", amount: 340000 },
      ];

  const max = Math.max(...chartData.map((d) => d.amount), 1);

  return (
    <div className="trend-chart-container" style={{ height: "160px" }}>
      <div className="trend-y-axis">
        <span>₹{(max / 100000).toFixed(1)}L</span>
        <span>₹{(max * 0.75 / 100000).toFixed(1)}L</span>
        <span>₹{(max * 0.5 / 100000).toFixed(1)}L</span>
        <span>₹{(max * 0.25 / 100000).toFixed(1)}L</span>
        <span>₹0</span>
      </div>
      <div className="trend-bars-wrapper">
        {chartData.map((bar, i) => {
          const heightPercent = Math.max(8, Math.round((bar.amount / max) * 100));
          return (
            <div key={i} className="trend-bar-col" title={`${bar.label}: ₹${bar.amount.toLocaleString("en-IN")}`}>
              <div className="trend-bar-fill" style={{ height: `${heightPercent}%` }} />
              <span>{bar.label}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}
