"use client";

import React, { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Plus,
  ShoppingBag,
  Upload,
  MessageSquare,
  Package,
  TrendingUp,
  X,
  CheckCircle2,
  Receipt,
  FileSpreadsheet,
} from "lucide-react";
import { useWorkspace } from "./workspace";
import { Button, Badge } from "./ui";

export function QuickActionsBar() {
  const w = useWorkspace();
  const pathname = usePathname();
  const [saleModalOpen, setSaleModalOpen] = useState(false);
  const [demandModalOpen, setDemandModalOpen] = useState(false);
  const [saleForm, setSaleForm] = useState({
    product_name: "",
    qty: 1,
    unit_price: "",
    payment_mode: "Cash",
    customer_notes: "",
  });
  const [demandForm, setDemandForm] = useState({
    product_name: "",
    category: "General",
    request_count: 1,
    estimated_sell_price: "",
    customer_notes: "",
  });
  const [submitting, setSubmitting] = useState(false);

  const handleRecordSale = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!saleForm.product_name || !saleForm.unit_price) {
      alert("Please enter product name and selling price.");
      return;
    }
    setSubmitting(true);
    try {
      await w.api(`/businesses/${w.business}/sales/quick-record`, "POST", {
        product_name: saleForm.product_name,
        qty: Number(saleForm.qty),
        unit_price: Number(saleForm.unit_price),
        payment_mode: saleForm.payment_mode,
        customer_notes: saleForm.customer_notes,
      });
      w.setNotice(`Recorded sale: ${saleForm.qty}x ${saleForm.product_name} in real-time.`);
      setSaleModalOpen(false);
      setSaleForm({
        product_name: "",
        qty: 1,
        unit_price: "",
        payment_mode: "Cash",
        customer_notes: "",
      });
    } catch (err: any) {
      alert(err.message || "Failed to record sale");
    } finally {
      setSubmitting(false);
    }
  };

  const handleRecordDemand = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!demandForm.product_name) {
      alert("Please enter product name.");
      return;
    }
    setSubmitting(true);
    try {
      await w.api(`/businesses/${w.business}/local-demand/requests`, "POST", {
        product_name: demandForm.product_name,
        category: demandForm.category,
        request_count: Number(demandForm.request_count),
        requested_qty: 1,
        estimated_sell_price: demandForm.estimated_sell_price ? Number(demandForm.estimated_sell_price) : null,
        customer_notes: demandForm.customer_notes,
        status: "logged",
      });
      w.setNotice(`Logged customer request for ${demandForm.product_name}`);
      setDemandModalOpen(false);
      setDemandForm({
        product_name: "",
        category: "General",
        request_count: 1,
        estimated_sell_price: "",
        customer_notes: "",
      });
    } catch (err: any) {
      alert(err.message || "Failed to log demand");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: "8px",
          flexWrap: "wrap",
          marginBottom: "16px",
          padding: "10px 14px",
          background: "#ffffff",
          borderRadius: "10px",
          border: "1px solid #e2e8f0",
          boxShadow: "0 1px 2px rgba(15, 23, 42, 0.04)",
        }}
      >
        <span style={{ fontSize: "12px", fontWeight: 700, color: "var(--muted)", textTransform: "uppercase", letterSpacing: "0.04em", marginRight: "4px" }}>
          Quick Actions:
        </span>

        {/* 1. Record Quick Sale */}
        <button
          type="button"
          onClick={() => setSaleModalOpen(true)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "7px 13px",
            borderRadius: "7px",
            background: "#059669",
            color: "#ffffff",
            fontSize: "12.5px",
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
            boxShadow: "0 1px 2px rgba(5, 150, 105, 0.2)",
            transition: "all 0.15s ease",
          }}
        >
          <Receipt size={14} />
          Record Quick Sale
        </button>

        {/* 2. Upload Supplier Invoice (hidden when already on purchasing/invoices or overview) */}
        {!pathname?.startsWith("/purchasing/invoices") && pathname !== "/overview" && (
          <Link href="/purchasing/invoices/upload" style={{ textDecoration: "none" }}>
            <button
              type="button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 13px",
                borderRadius: "7px",
                background: "#2563eb",
                color: "#ffffff",
                fontSize: "12.5px",
                fontWeight: 600,
                border: "none",
                cursor: "pointer",
                boxShadow: "0 1px 2px rgba(37, 99, 235, 0.2)",
                transition: "all 0.15s ease",
              }}
            >
              <Upload size={14} />
              Upload Supplier Invoice
            </button>
          </Link>
        )}

        {/* 3. Log Customer Request */}
        <button
          type="button"
          onClick={() => setDemandModalOpen(true)}
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: "6px",
            padding: "7px 13px",
            borderRadius: "7px",
            background: "#4f46e5",
            color: "#ffffff",
            fontSize: "12.5px",
            fontWeight: 600,
            border: "none",
            cursor: "pointer",
            boxShadow: "0 1px 2px rgba(79, 70, 229, 0.2)",
            transition: "all 0.15s ease",
          }}
        >
          <MessageSquare size={14} />
          Log Customer Request
        </button>

        {/* 4. Add New Product (hidden when on inventory stock page) */}
        {!pathname?.startsWith("/inventory/stock") && !pathname?.startsWith("/inventory/products") && (
          <Link href="/inventory/products/new" style={{ textDecoration: "none" }}>
            <button
              type="button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 13px",
                borderRadius: "7px",
                background: "#f8fafc",
                color: "#1e293b",
                fontSize: "12.5px",
                fontWeight: 600,
                border: "1px solid #cbd5e1",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <Package size={14} />
              Add New Product
            </button>
          </Link>
        )}

        {/* 5. Open Purchasing Planner (hidden when on planner page) */}
        {!pathname?.startsWith("/purchasing/planner") && (
          <Link href="/purchasing/planner" style={{ textDecoration: "none" }}>
            <button
              type="button"
              style={{
                display: "inline-flex",
                alignItems: "center",
                gap: "6px",
                padding: "7px 13px",
                borderRadius: "7px",
                background: "#f8fafc",
                color: "#1e293b",
                fontSize: "12.5px",
                fontWeight: 600,
                border: "1px solid #cbd5e1",
                cursor: "pointer",
                transition: "all 0.15s ease",
              }}
            >
              <TrendingUp size={14} />
              Open Purchasing Planner
            </button>
          </Link>
        )}
      </div>

      {/* Modal: Quick Sale POS Entry */}
      {saleModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#d1fae5", display: "flex", alignItems: "center", justifyContent: "center", color: "#059669" }}>
                  <Receipt size={18} />
                </span>
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>
                  Record Live Retail Sale
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSaleModalOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--muted)" }}>
              Immediately deducts inventory and triggers real-time profit and sales tracking across all screens.
            </p>

            <form onSubmit={handleRecordSale} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                  Product Name or SKU *
                </label>
                <input
                  required
                  placeholder="e.g. Tata Salt 1kg, Parle-G, Fortune Oil"
                  value={saleForm.product_name}
                  onChange={(e) => setSaleForm({ ...saleForm, product_name: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                    Quantity Sold *
                  </label>
                  <input
                    required
                    type="number"
                    min="1"
                    value={saleForm.qty}
                    onChange={(e) => setSaleForm({ ...saleForm, qty: Number(e.target.value) })}
                  />
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                    Price Per Unit (₹) *
                  </label>
                  <input
                    required
                    type="number"
                    step="0.01"
                    min="0.1"
                    placeholder="e.g. 28.00"
                    value={saleForm.unit_price}
                    onChange={(e) => setSaleForm({ ...saleForm, unit_price: e.target.value })}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                  Payment Method
                </label>
                <select
                  value={saleForm.payment_mode}
                  onChange={(e) => setSaleForm({ ...saleForm, payment_mode: e.target.value })}
                >
                  <option value="Cash">Cash Counter</option>
                  <option value="UPI">UPI / QR Code</option>
                  <option value="Card">Debit / Credit Card</option>
                  <option value="Credit / Khata">Credit / Customer Khata</option>
                </select>
              </div>

              {Number(saleForm.qty) > 0 && Number(saleForm.unit_price) > 0 && (
                <div style={{ padding: "8px 12px", background: "#f0fdf4", borderRadius: "6px", fontSize: "13px", color: "#166534", fontWeight: 600 }}>
                  Total Bill Amount: ₹{(Number(saleForm.qty) * Number(saleForm.unit_price)).toFixed(2)}
                </div>
              )}

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
                <Button variant="ghost" type="button" onClick={() => setSaleModalOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" type="submit" disabled={submitting}>
                  {submitting ? "Recording..." : "Record & Deduct Stock"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Modal: Fast Customer Demand Log */}
      {demandModalOpen && (
        <div className="modal-overlay">
          <div className="modal-box">
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "16px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                <span style={{ width: "32px", height: "32px", borderRadius: "8px", background: "#ede9fe", display: "flex", alignItems: "center", justifyContent: "center", color: "#7c3aed" }}>
                  <MessageSquare size={18} />
                </span>
                <h3 style={{ margin: 0, fontSize: "16px", fontWeight: 700, color: "#0f172a" }}>
                  Log Unmet Customer Demand
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setDemandModalOpen(false)}
                style={{ background: "none", border: "none", cursor: "pointer", color: "var(--muted)" }}
              >
                <X size={18} />
              </button>
            </div>

            <p style={{ margin: "0 0 16px", fontSize: "13px", color: "var(--muted)" }}>
              Captures items shoppers requested that you don't stock, updating opportunity scores in real time.
            </p>

            <form onSubmit={handleRecordDemand} style={{ display: "flex", flexDirection: "column", gap: "12px" }}>
              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                  Requested Item Name *
                </label>
                <input
                  required
                  placeholder="e.g. Oat Milk Barista, Gluten Free Atta, Greek Yogurt"
                  value={demandForm.product_name}
                  onChange={(e) => setDemandForm({ ...demandForm, product_name: e.target.value })}
                />
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px" }}>
                <div>
                  <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                    Category
                  </label>
                  <select
                    value={demandForm.category}
                    onChange={(e) => setDemandForm({ ...demandForm, category: e.target.value })}
                  >
                    <option value="Dairy & Beverages">Dairy & Beverages</option>
                    <option value="Snacks & Bakery">Snacks & Bakery</option>
                    <option value="Staples & Grains">Staples & Grains</option>
                    <option value="Personal Care">Personal Care</option>
                    <option value="General">General Retail</option>
                  </select>
                </div>
                <div>
                  <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                    Customer Inquiries (Count)
                  </label>
                  <input
                    type="number"
                    min="1"
                    value={demandForm.request_count}
                    onChange={(e) => setDemandForm({ ...demandForm, request_count: Number(e.target.value) })}
                  />
                </div>
              </div>

              <div>
                <label style={{ display: "block", fontSize: "12.5px", fontWeight: 600, marginBottom: "4px" }}>
                  Estimated Target Selling Price (₹)
                </label>
                <input
                  type="number"
                  step="0.01"
                  placeholder="Optional, e.g. 180"
                  value={demandForm.estimated_sell_price}
                  onChange={(e) => setDemandForm({ ...demandForm, estimated_sell_price: e.target.value })}
                />
              </div>

              <div style={{ display: "flex", justifyContent: "flex-end", gap: "8px", marginTop: "12px" }}>
                <Button variant="ghost" type="button" onClick={() => setDemandModalOpen(false)}>
                  Cancel
                </Button>
                <Button variant="primary" type="submit" disabled={submitting}>
                  {submitting ? "Saving..." : "Log Customer Demand"}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}
    </>
  );
}
