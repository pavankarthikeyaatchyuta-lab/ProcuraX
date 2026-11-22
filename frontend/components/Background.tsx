"use client";
import { ProjectBackground } from "./animated-ui";

export default function Background({ children }: { children: React.ReactNode }) {
  return (
    <>
      {/* Animated procurement-graph canvas behind everything */}
      <ProjectBackground />
      {/* Page content sits above the canvas */}
      <div style={{ position: "relative", zIndex: 1, minHeight: "100vh" }}>
        {children}
      </div>
    </>
  );
}
