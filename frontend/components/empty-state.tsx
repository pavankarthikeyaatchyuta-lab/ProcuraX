"use client";

import React from "react";
import Link from "next/link";
import { Button, Badge } from "./ui";

interface EmptyStateProps {
  icon: React.ReactNode;
  badge?: string;
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
  onAction?: () => void;
  secondaryLabel?: string;
  secondaryHref?: string;
}

export function EmptyState({
  icon,
  badge,
  title,
  description,
  actionLabel,
  actionHref,
  onAction,
  secondaryLabel,
  secondaryHref,
}: EmptyStateProps) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        textAlign: "center",
        padding: "48px 24px",
        borderRadius: "16px",
        background: "radial-gradient(ellipse at top, rgba(248, 250, 252, 0.95), #ffffff)",
        border: "1px dashed #cbd5e1",
        margin: "16px 0",
      }}
    >
      <div
        style={{
          width: "56px",
          height: "56px",
          borderRadius: "16px",
          background: "#f1f5f9",
          border: "1px solid #e2e8f0",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: "var(--brand)",
          marginBottom: "16px",
          boxShadow: "0 4px 12px rgba(15, 23, 42, 0.04)",
        }}
      >
        {icon}
      </div>

      {badge && (
        <div style={{ marginBottom: "8px" }}>
          <Badge tone="blue">{badge}</Badge>
        </div>
      )}

      <h3
        style={{
          fontSize: "17px",
          fontWeight: 700,
          color: "var(--foreground)",
          margin: "0 0 8px 0",
          letterSpacing: "-0.01em",
        }}
      >
        {title}
      </h3>

      <p
        style={{
          fontSize: "13.5px",
          color: "var(--muted)",
          maxWidth: "460px",
          lineHeight: 1.55,
          margin: "0 0 24px 0",
        }}
      >
        {description}
      </p>

      <div style={{ display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap", justifyContent: "center" }}>
        {actionLabel && (
          actionHref ? (
            <Link href={actionHref}>
              <Button variant="primary">{actionLabel}</Button>
            </Link>
          ) : (
            <Button variant="primary" onClick={onAction}>
              {actionLabel}
            </Button>
          )
        )}

        {secondaryLabel && secondaryHref && (
          <Link href={secondaryHref}>
            <Button variant="ghost">{secondaryLabel}</Button>
          </Link>
        )}
      </div>
    </div>
  );
}
