"use client";

import React, { createContext, useContext, useEffect, useState, useRef } from "react";
import { RealtimeClient, RealtimeEvent, ConnectionStatus } from "../lib/realtime";
import { Activity, Bell, CheckCircle2, AlertTriangle, FileText, Users, RefreshCw, X, Radio } from "lucide-react";
import { Badge, Button } from "./ui";

interface RealtimeContextValue {
  status: ConnectionStatus;
  events: RealtimeEvent[];
  unreadCount: number;
  isDrawerOpen: boolean;
  openDrawer: () => void;
  closeDrawer: () => void;
  toggleDrawer: () => void;
  clearEvents: () => void;
  client: RealtimeClient | null;
}

const RealtimeContext = createContext<RealtimeContextValue>({
  status: "disconnected",
  events: [],
  unreadCount: 0,
  isDrawerOpen: false,
  openDrawer: () => {},
  closeDrawer: () => {},
  toggleDrawer: () => {},
  clearEvents: () => {},
  client: null,
});

export function useRealtime() {
  return useContext(RealtimeContext);
}

// Dynamic relative time formatter (ticks dynamically)
function formatRelativeTime(isoString: string, now: number): string {
  try {
    const eventTime = new Date(isoString).getTime();
    const diffSec = Math.max(0, Math.floor((now - eventTime) / 1000));
    if (diffSec < 5) return "just now";
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHr = Math.floor(diffMin / 60);
    return `${diffHr}h ago`;
  } catch (e) {
    return "recently";
  }
}

export function RealtimeProvider({
  businessId,
  children,
}: {
  businessId?: string;
  children: React.ReactNode;
}) {
  const [status, setStatus] = useState<ConnectionStatus>("connecting");
  const [events, setEvents] = useState<RealtimeEvent[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [currentTime, setCurrentTime] = useState(Date.now());
  const clientRef = useRef<RealtimeClient | null>(null);

  // Tick relative time every second
  useEffect(() => {
    const timer = setInterval(() => setCurrentTime(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!businessId) return;

    const client = new RealtimeClient(businessId);
    clientRef.current = client;

    const unsubStatus = client.onStatusChange((newStatus) => {
      setStatus(newStatus);
    });

    const unsubEvents = client.subscribe((event) => {
      setEvents((prev) => [event, ...prev.slice(0, 49)]); // keep latest 50
      setUnreadCount((c) => c + 1);
    });

    return () => {
      unsubStatus();
      unsubEvents();
      client.disconnect();
      clientRef.current = null;
    };
  }, [businessId]);

  const openDrawer = () => {
    setIsDrawerOpen(true);
    setUnreadCount(0);
  };
  const closeDrawer = () => setIsDrawerOpen(false);
  const toggleDrawer = () => {
    if (isDrawerOpen) {
      closeDrawer();
    } else {
      openDrawer();
    }
  };
  const clearEvents = () => {
    setEvents([]);
    setUnreadCount(0);
  };

  return (
    <RealtimeContext.Provider
      value={{
        status,
        events,
        unreadCount,
        isDrawerOpen,
        openDrawer,
        closeDrawer,
        toggleDrawer,
        clearEvents,
        client: clientRef.current,
      }}
    >
      {children}
      <LiveActivityDrawer
        isOpen={isDrawerOpen}
        onClose={closeDrawer}
        events={events}
        onClear={clearEvents}
        currentTime={currentTime}
        status={status}
      />
    </RealtimeContext.Provider>
  );
}

// Live Status Pulse Badge in Header
export function LivePulseBadge() {
  const { status, unreadCount, toggleDrawer } = useRealtime();

  const isConnected = status === "connected";
  const isConnecting = status === "connecting";

  return (
    <button
      className="live-pulse-badge"
      onClick={toggleDrawer}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: "6px",
        padding: "5px 10px",
        borderRadius: "9999px",
        background: isConnected ? "rgba(16, 185, 129, 0.08)" : isConnecting ? "rgba(245, 158, 11, 0.08)" : "rgba(100, 116, 139, 0.08)",
        border: `1px solid ${isConnected ? "rgba(16, 185, 129, 0.25)" : isConnecting ? "rgba(245, 158, 11, 0.25)" : "rgba(100, 116, 139, 0.2)"}`,
        color: isConnected ? "#059669" : isConnecting ? "#d97706" : "#64748b",
        fontSize: "12px",
        fontWeight: 600,
        cursor: "pointer",
        transition: "all 0.15s ease",
      }}
      title={`Real-Time Sync: ${status}. Click to view live activity feed.`}
    >
      <span
        style={{
          width: "7px",
          height: "7px",
          borderRadius: "50%",
          background: isConnected ? "#10b981" : isConnecting ? "#f59e0b" : "#94a3b8",
          boxShadow: isConnected ? "0 0 0 2px rgba(16, 185, 129, 0.2)" : "none",
          display: "inline-block",
        }}
      />
      <span className="live-pulse-text">{isConnected ? "Live Sync" : isConnecting ? "Connecting..." : "Offline"}</span>

      {unreadCount > 0 && (
        <span
          style={{
            background: "#ef4444",
            color: "#ffffff",
            fontSize: "10px",
            fontWeight: 700,
            padding: "1px 5px",
            borderRadius: "9999px",
            lineHeight: 1.2,
          }}
        >
          {unreadCount}
        </span>
      )}
    </button>
  );
}

// Slide-out Drawer for Time-to-Time Real-Time Events
function LiveActivityDrawer({
  isOpen,
  onClose,
  events,
  onClear,
  currentTime,
  status,
}: {
  isOpen: boolean;
  onClose: () => void;
  events: RealtimeEvent[];
  onClear: () => void;
  currentTime: number;
  status: ConnectionStatus;
}) {
  if (!isOpen) return null;

  const getEventIcon = (type: string) => {
    switch (type) {
      case "INVOICE_PROCESSED":
      case "INVOICE_UPLOADED":
        return <FileText size={16} color="#0284c7" />;
      case "PRICE_ALERT":
      case "PROFIT_LEAK":
        return <AlertTriangle size={16} color="#ea580c" />;
      case "DEMAND_LOGGED":
      case "DEMAND_UPDATED":
        return <Users size={16} color="#7c3aed" />;
      case "DATA_RESET":
        return <RefreshCw size={16} color="#d97706" />;
      default:
        return <Activity size={16} color="#10b981" />;
    }
  };

  return (
    <>
      <div
        onClick={onClose}
        style={{
          position: "fixed",
          inset: 0,
          background: "rgba(15, 23, 42, 0.4)",
          backdropFilter: "blur(4px)",
          zIndex: 100,
        }}
      />
      <div
        style={{
          position: "fixed",
          top: 0,
          right: 0,
          bottom: 0,
          width: "380px",
          maxWidth: "100vw",
          background: "#ffffff",
          boxShadow: "-8px 0 24px rgba(15, 23, 42, 0.12)",
          zIndex: 101,
          display: "flex",
          flexDirection: "column",
          animation: "slideInRight 0.2s cubic-bezier(0.16, 1, 0.3, 1)",
        }}
      >
        {/* Header */}
        <div
          style={{
            padding: "16px 20px",
            borderBottom: "1px solid #e2e8f0",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            <Radio size={18} color="#0284c7" />
            <h3 style={{ margin: 0, fontSize: "15px", fontWeight: 700, color: "var(--foreground)" }}>
              Live Real-Time Activity
            </h3>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
            {events.length > 0 && (
              <button
                onClick={onClear}
                style={{
                  background: "transparent",
                  border: "none",
                  color: "var(--muted)",
                  fontSize: "12px",
                  cursor: "pointer",
                }}
              >
                Clear
              </button>
            )}
            <button
              onClick={onClose}
              style={{
                background: "transparent",
                border: "none",
                color: "var(--muted)",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                padding: "4px",
              }}
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Status indicator bar */}
        <div
          style={{
            padding: "8px 20px",
            background: "#f8fafc",
            borderBottom: "1px solid #f1f5f9",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            fontSize: "12px",
          }}
        >
          <span style={{ color: "var(--muted)" }}>WebSocket Channel</span>
          <span style={{ color: status === "connected" ? "#059669" : "#d97706", fontWeight: 600 }}>
            {status === "connected" ? "● Connected (Live)" : "○ " + status}
          </span>
        </div>

        {/* Event List */}
        <div style={{ flex: 1, overflowY: "auto", padding: "16px 20px" }}>
          {events.length === 0 ? (
            <div style={{ textAlign: "center", padding: "48px 12px", color: "var(--muted)" }}>
              <Radio size={32} style={{ opacity: 0.3, margin: "0 auto 12px" }} />
              <p style={{ margin: "0 0 4px", fontSize: "14px", fontWeight: 600 }}>No live events yet</p>
              <p style={{ margin: 0, fontSize: "12px" }}>
                Events like invoice processing, price changes, and customer demand will stream here in real time.
              </p>
            </div>
          ) : (
            <div style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              {events.map((evt) => (
                <div
                  key={evt.event_id}
                  style={{
                    padding: "12px 14px",
                    borderRadius: "10px",
                    background: "#f8fafc",
                    border: "1px solid #e2e8f0",
                    display: "flex",
                    flexDirection: "column",
                    gap: "4px",
                    transition: "all 0.15s ease",
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
                    <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
                      {getEventIcon(evt.type)}
                      <span style={{ fontSize: "13px", fontWeight: 700, color: "var(--foreground)" }}>
                        {evt.title}
                      </span>
                    </div>
                    <span style={{ fontSize: "11px", color: "var(--muted)", fontWeight: 500 }}>
                      {formatRelativeTime(evt.timestamp, currentTime)}
                    </span>
                  </div>
                  <p style={{ margin: 0, fontSize: "12.5px", color: "var(--foreground)", lineHeight: 1.4 }}>
                    {evt.message}
                  </p>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
