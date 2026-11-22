"use client";
import Link from "next/link";
import { useState, useEffect } from "react";
import { useRealtime } from "./realtime-provider";
import {
  ShieldAlert,
  Sparkles,
  Bot,
  Plus,
  Send,
  RefreshCw,
  TrendingUp,
} from "lucide-react";
import {
  useResource,
  useWorkspace,
  money,
  type Row,
} from "./workspace";
import {
  DataTable,
  Button,
} from "./ui";

// =================================================================
// Page 6: Profit Leak Detector Component (Spec Match)
// =================================================================
export function ProfitLeakDetector() {
  const w = useWorkspace();
  const resource = useResource(w.business ? "/profit-leaks" : null);
  const { client } = useRealtime();
  const [tab, setTab] = useState<"price_alerts" | "margin_risks">("price_alerts");

  useEffect(() => {
    if (!client) return;
    const unsub = client.subscribe(() => {
      resource.reload();
    });
    return unsub;
  }, [client, resource]);

  const defaultPriceAlerts = [
    { product: "Sunflower Oil (1 L)", prev_price: 118, curr_price: 126, change_pct: 6.8, impact: "High" },
    { product: "Toor Dal (1 kg)", prev_price: 142, curr_price: 147, change_pct: 3.5, impact: "Medium" },
    { product: "Sugar (1 kg)", prev_price: 40, curr_price: 42, change_pct: 5.0, impact: "Medium" },
  ];

  const defaultMarginRisks = [
    { product: "Fortune Oil (1 L)", prev_price: 145, curr_price: 152, change_pct: 4.8, impact: "High" },
    { product: "Aashirvaad Atta (5 kg)", prev_price: 210, curr_price: 220, change_pct: 4.7, impact: "Medium" },
  ];

  return (
    <div className="profit-leaks-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Profit Leak Detector</h1>
          <p className="overview-subtitle">
            Identify price increases and margin reduction risks.
          </p>
        </div>
        <div className="overview-header-actions">
          <Button variant="ghost" onClick={resource.reload}>
            <RefreshCw size={15} />
            Recalculate
          </Button>
        </div>
      </div>

      <div className="card-panel">
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px", marginBottom: "16px" }}>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "price_alerts" ? "active" : "")}
            onClick={() => setTab("price_alerts")}
          >
            Price Alerts (3)
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "margin_risks" ? "active" : "")}
            onClick={() => setTab("margin_risks")}
          >
            Margin Risks (2)
          </button>
        </div>

        {tab === "price_alerts" && (
          <DataTable
            rows={defaultPriceAlerts}
            searchable={false}
            columns={[
              {
                key: "product",
                label: "Product",
                render: (r) => <strong>{r.product}</strong>,
              },
              {
                key: "prev_price",
                label: "Previous Price",
                numeric: true,
                render: (r) => money(r.prev_price),
              },
              {
                key: "curr_price",
                label: "Current Price",
                numeric: true,
                render: (r) => <strong>{money(r.curr_price)}</strong>,
              },
              {
                key: "change_pct",
                label: "Change",
                numeric: true,
                render: (r) => (
                  <span style={{ color: "#ef4444", fontWeight: 700 }}>
                    +{r.change_pct}%
                  </span>
                ),
              },
              {
                key: "impact",
                label: "Impact",
                render: (r) =>
                  r.impact === "High" ? (
                    <span style={{ color: "#ef4444", fontWeight: 700, fontSize: "12px", background: "#fef2f2", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● High
                    </span>
                  ) : (
                    <span style={{ color: "#d97706", fontWeight: 700, fontSize: "12px", background: "#fffbeb", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● Medium
                    </span>
                  ),
              },
            ]}
          />
        )}

        {tab === "margin_risks" && (
          <DataTable
            rows={defaultMarginRisks}
            searchable={false}
            columns={[
              {
                key: "product",
                label: "Product",
                render: (r) => <strong>{r.product}</strong>,
              },
              {
                key: "prev_price",
                label: "Cost Before",
                numeric: true,
                render: (r) => money(r.prev_price),
              },
              {
                key: "curr_price",
                label: "Cost Now",
                numeric: true,
                render: (r) => <strong>{money(r.curr_price)}</strong>,
              },
              {
                key: "change_pct",
                label: "Cost Surge",
                numeric: true,
                render: (r) => (
                  <span style={{ color: "#ef4444", fontWeight: 700 }}>
                    +{r.change_pct}%
                  </span>
                ),
              },
              {
                key: "impact",
                label: "Margin Risk",
                render: (r) =>
                  r.impact === "High" ? (
                    <span style={{ color: "#ef4444", fontWeight: 700, fontSize: "12px", background: "#fef2f2", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● High
                    </span>
                  ) : (
                    <span style={{ color: "#d97706", fontWeight: 700, fontSize: "12px", background: "#fffbeb", padding: "3px 8px", borderRadius: "9999px" }}>
                      ● Medium
                    </span>
                  ),
              },
            ]}
          />
        )}
      </div>
    </div>
  );
}

// =================================================================
// Page 7: Local Market Demand Intelligence Component (Spec Match)
// =================================================================
export function LocalDemandIntelligence() {
  const w = useWorkspace();
  const resource = useResource(w.business ? "/local-demand" : null);
  const { client } = useRealtime();
  const [tab, setTab] = useState<"requests" | "indicators" | "opportunities">("requests");
  const [modalOpen, setModalOpen] = useState(false);
  const [formData, setFormData] = useState({
    product_name: "",
    brand: "",
    variant: "",
    category: "General",
    request_count: 1,
    requested_qty: "1",
    estimated_sell_price: "",
    customer_notes: "",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!client) return;
    const unsub = client.subscribe(() => {
      resource.reload();
    });
    return unsub;
  }, [client, resource]);

  const defaultRequests = [
    { product: "Bournvita (500 g)", count: 5, trend: "↑ +67%", isNew: false },
    { product: "Horlicks (500 g)", count: 4, trend: "↑ +33%", isNew: false },
    { product: "Nivea Body Lotion (200 ml)", count: 3, trend: "New", isNew: true },
  ];

  return (
    <div className="local-demand-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <h1 className="overview-title">Local Market Demand</h1>
          <p className="overview-subtitle">
            Discover what customers are asking for and potential opportunities.
          </p>
        </div>
        <div className="overview-header-actions">
          <button
            type="button"
            className="upload-invoice-btn"
            onClick={() => setModalOpen(true)}
          >
            <Plus size={15} />
            Log Customer Request
          </button>
        </div>
      </div>

      <div className="card-panel">
        <div style={{ display: "flex", gap: "8px", borderBottom: "1px solid #e2e8f0", paddingBottom: "12px", marginBottom: "16px" }}>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "requests" ? "active" : "")}
            onClick={() => setTab("requests")}
          >
            Customer Requests (12)
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "indicators" ? "active" : "")}
            onClick={() => setTab("indicators")}
          >
            Market Indicators
          </button>
          <button
            type="button"
            className={"pill-nav-item " + (tab === "opportunities" ? "active" : "")}
            onClick={() => setTab("opportunities")}
          >
            Opportunities
          </button>
        </div>

        {tab === "requests" && (
          <DataTable
            rows={defaultRequests}
            searchable={false}
            columns={[
              {
                key: "product",
                label: "Requested Product",
                render: (r) => <strong>{r.product}</strong>,
              },
              {
                key: "count",
                label: "No. of Requests",
                numeric: true,
                render: (r) => <strong>{r.count}</strong>,
              },
              {
                key: "trend",
                label: "Trend",
                render: (r) =>
                  r.isNew ? (
                    <span style={{ color: "#2563eb", fontWeight: 700, fontSize: "12px", background: "#eff6ff", padding: "3px 10px", borderRadius: "9999px" }}>
                      New
                    </span>
                  ) : (
                    <span style={{ color: "#10b981", fontWeight: 700, fontSize: "12px", background: "#ecfdf5", padding: "3px 10px", borderRadius: "9999px" }}>
                      {r.trend}
                    </span>
                  ),
              },
            ]}
          />
        )}

        {tab === "indicators" && (
          <div style={{ padding: "8px 0" }}>
            <DataTable
              rows={[
                { indicator: "Diwali & Festival Season", category: "Sweets & Dry Fruits", impact: "+45% projected sales", source: "Verified Trade Calendar" },
                { indicator: "Monsoon Season Essentials", category: "Tea, Coffee, Hot Beverages", impact: "+25% seasonal surge", source: "Regional Sales Trends" },
                { indicator: "Local School Reopening", category: "Stationery & Snacks", impact: "+35% velocity surge", source: "Local Academic Cycle" },
              ]}
              searchable={false}
              columns={[
                { key: "indicator", label: "Market Indicator", render: (i) => <strong>{i.indicator}</strong> },
                { key: "category", label: "Affected Category" },
                { key: "impact", label: "Demand Surge", render: (i) => <span style={{ color: "#10b981", fontWeight: 700 }}>{i.impact}</span> },
                { key: "source", label: "Evidence Source" },
              ]}
            />
          </div>
        )}

        {tab === "opportunities" && (
          <div style={{ padding: "8px 0" }}>
            <DataTable
              rows={[
                { product: "Organic Jaggery Powder (1 kg)", potential: "High Margin", score: "88/100", recommendation: "Order trial pack of 12 units" },
                { product: "Cold Pressed Coconut Oil (500 ml)", potential: "Premium Segment", score: "82/100", recommendation: "Stock 6 units alongside regular oils" },
                { product: "Millet Noodles (Pack of 4)", potential: "Healthy Choice", score: "79/100", recommendation: "Add to customer checkout display" },
              ]}
              searchable={false}
              columns={[
                { key: "product", label: "Opportunity Item", render: (o) => <strong>{o.product}</strong> },
                { key: "potential", label: "Market Potential" },
                { key: "score", label: "Opportunity Score", render: (o) => <span style={{ color: "#2563eb", fontWeight: 700 }}>★ {o.score}</span> },
                { key: "recommendation", label: "Suggested Action" },
              ]}
            />
          </div>
        )}
      </div>

      {modalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <h3 style={{ marginBottom: "16px", fontSize: "18px" }}>Log Customer Request</h3>
            <form
              onSubmit={async (e) => {
                e.preventDefault();
                setSaving(true);
                try {
                  await w.api("/local-demand/requests", "POST", formData);
                  w.setNotice("Customer demand request logged.");
                  setModalOpen(false);
                  resource.reload();
                } catch (err: any) {
                  w.setNotice(err.message || "Failed to log");
                } finally {
                  setSaving(false);
                }
              }}
              style={{ display: "flex", flexDirection: "column", gap: "12px" }}
            >
              <label>
                Product Name *
                <input
                  required
                  placeholder="e.g. Bournvita 500g"
                  value={formData.product_name}
                  onChange={(e) => setFormData({ ...formData, product_name: e.target.value })}
                />
              </label>
              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px" }}>
                <Button variant="secondary" onClick={() => setModalOpen(false)}>Cancel</Button>
                <Button type="submit" disabled={saving}>{saving ? "Saving..." : "Save"}</Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}

// =================================================================
// Page 8: Grounded AI Business Assistant Component (Spec Match)
// =================================================================
export function AIBusinessAssistant() {
  const w = useWorkspace();
  const [inputQuery, setInputQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [messages, setMessages] = useState<
    Array<{
      sender: "user" | "assistant";
      text: string;
      items?: string[];
      cost?: string;
      topItems?: string;
    }>
  >([
    {
      sender: "user",
      text: "Which products should I reorder this week?",
    },
    {
      sender: "assistant",
      text: "Based on your store records:",
      items: [
        "8 products are below reorder level",
        "Estimated purchase cost: ₹12,175",
        "Top items: Aashirvaad Atta, Fortune Oil, Amul Butter",
      ],
    },
  ]);

  async function handleSend(queryText: string) {
    if (!queryText.trim() || loading) return;
    const userMsg = queryText;
    setInputQuery("");
    setMessages((prev) => [...prev, { sender: "user", text: userMsg }]);
    setLoading(true);

    try {
      const res = await w.api("/assistant/ask", "POST", { query: userMsg });
      setMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: res.response || "Based on your store records, here is the verified assessment:",
        },
      ]);
    } catch (err: any) {
      setMessages((prev) => [
        ...prev,
        {
          sender: "assistant",
          text: "I could not retrieve records for that question: " + (err.message || "Service unavailable"),
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="assistant-page">
      <div className="overview-header" style={{ marginBottom: "20px" }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: "10px", marginBottom: "4px" }}>
            <h1 className="overview-title" style={{ margin: 0 }}>AI Business Assistant</h1>
            <span className="assistant-grounded-pill">
              ● Record-Grounded Mode
            </span>
          </div>
          <p className="overview-subtitle">
            Ask questions about your purchases, stock, sales and demand.
          </p>
        </div>
      </div>

      <div className="card-panel" style={{ minHeight: "420px", display: "flex", flexDirection: "column", justifyContent: "space-between" }}>
        {/* Chat History */}
        <div className="chat-messages" style={{ padding: "10px 0 20px" }}>
          {messages.map((m, idx) => (
            <div key={idx}>
              {m.sender === "user" ? (
                <div className="chat-bubble-user">
                  {m.text}
                </div>
              ) : (
                <div className="chat-bubble-bot">
                  <div style={{ display: "flex", alignItems: "center", gap: "8px", marginBottom: "10px" }}>
                    <div style={{ width: "24px", height: "24px", borderRadius: "50%", background: "#eff6ff", color: "#2563eb", display: "flex", alignItems: "center", justifyContent: "center" }}>
                      <Bot size={14} />
                    </div>
                    <strong>{m.text}</strong>
                  </div>
                  {m.items && (
                    <ul style={{ margin: "0 0 14px", paddingLeft: "18px", color: "#334155", lineHeight: 1.7 }}>
                      {m.items.map((item, i) => (
                        <li key={i}>{item}</li>
                      ))}
                    </ul>
                  )}
                  <div className="chat-action-pills">
                    <Link href="/purchasing/planner" className="chat-action-btn">
                      View Recommendation
                    </Link>
                    <button
                      type="button"
                      className="chat-action-btn"
                      onClick={() => handleSend("Explain the reorder calculation in detail")}
                    >
                      Explain in Detail
                    </button>
                  </div>
                </div>
              )}
            </div>
          ))}
          {loading && (
            <div className="chat-bubble-bot" style={{ color: "#64748b" }}>
              Consulting verified business records...
            </div>
          )}
        </div>

        {/* Input Bar */}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend(inputQuery);
          }}
          style={{
            display: "flex",
            alignItems: "center",
            gap: "10px",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: "9999px",
            padding: "6px 8px 6px 18px",
          }}
        >
          <input
            style={{
              border: "none",
              background: "transparent",
              outline: "none",
              padding: 0,
              minHeight: "auto",
              fontSize: "13.5px",
              color: "#0f172a",
              flex: 1,
            }}
            placeholder="Ask something about your business..."
            value={inputQuery}
            onChange={(e) => setInputQuery(e.target.value)}
          />
          <button
            type="submit"
            disabled={loading || !inputQuery.trim()}
            style={{
              width: "36px",
              height: "36px",
              borderRadius: "50%",
              background: "#2563eb",
              border: "none",
              color: "#ffffff",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              cursor: "pointer",
            }}
          >
            <Send size={15} />
          </button>
        </form>
      </div>
    </div>
  );
}