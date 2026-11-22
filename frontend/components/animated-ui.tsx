"use client";
import { useEffect, useRef } from "react";

// ─────────────────────────────────────────────
// 3‑D rotating ProcuraX hex‑prism logo in pure SVG + CSS animation
// Colors: midnight navy + sky‑blue only (no purple)
// ─────────────────────────────────────────────
export function AnimatedLogo({ size = 34 }: { size?: number }) {
  return (
    <span
      style={{ display: "inline-block", width: size, height: size }}
      className="px-logo-3d"
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        style={{ display: "block" }}
      >
        <defs>
          {/* Sky‑blue gradient – top face */}
          <linearGradient id="lg-top" x1="4" y1="4" x2="36" y2="20" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#e0f2fe" />
            <stop offset="100%" stopColor="#38bdf8" />
          </linearGradient>
          {/* Deep navy gradient – right face */}
          <linearGradient id="lg-right" x1="20" y1="12" x2="36" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#0369a1" />
            <stop offset="100%" stopColor="#0c1a2e" />
          </linearGradient>
          {/* Mid‑blue gradient – left face */}
          <linearGradient id="lg-left" x1="4" y1="12" x2="20" y2="36" gradientUnits="userSpaceOnUse">
            <stop offset="0%" stopColor="#1d4ed8" />
            <stop offset="100%" stopColor="#0f172a" />
          </linearGradient>
          {/* Glow filter */}
          <filter id="lg-glow" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="2.5" result="blur" />
            <feComposite in="SourceGraphic" in2="blur" operator="over" />
          </filter>
        </defs>

        {/* Hex prism – 3 visible faces */}
        {/* left face */}
        <path d="M4 12 L20 21 L20 37 L4 28 Z" fill="url(#lg-left)" />
        {/* right face */}
        <path d="M36 12 L20 21 L20 37 L36 28 Z" fill="url(#lg-right)" />
        {/* top face */}
        <path d="M20 3 L36 12 L20 21 L4 12 Z" fill="url(#lg-top)" />

        {/* Inner facet highlight on top */}
        <path d="M20 8 L31 14 L20 20 L9 14 Z" fill="#bae6fd" opacity="0.65" />

        {/* "P" letter mark – white with glow */}
        <path
          d="M15 16 L22 16 C24.5 16 26 17.2 26 19.4 C26 21.6 24.5 23 22 23 L18 23 L18 27 L15 27 Z
             M18 18.5 L18 20.5 L21.5 20.5 C22.4 20.5 23 20.1 23 19.4 C23 18.8 22.4 18.5 21.5 18.5 Z"
          fill="#ffffff"
          filter="url(#lg-glow)"
        />

        {/* edge highlight */}
        <path d="M20 3 L36 12" stroke="#bae6fd" strokeWidth="0.8" opacity="0.8" />
        <path d="M20 3 L4 12" stroke="#93c5fd" strokeWidth="0.8" opacity="0.6" />
      </svg>
    </span>
  );
}

// ─────────────────────────────────────────────
// Dynamic Project-Based Procurement & Supply-Chain Canvas Background
// (Supply Hubs, Live Transit Packets, Floating 3D Cargo Boxes,
// Interactive Telemetry Grid, Strictly Navy/Blue/Sky - No Purple)
// ─────────────────────────────────────────────
export function ProjectBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let animId: number;
    let W = 0;
    let H = 0;
    let time = 0;

    // Track mouse for interactive proximity field
    const mouse = { x: -1000, y: -1000, currX: -1000, currY: -1000, active: false };

    const onMouseMove = (e: MouseEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      mouse.active = true;
    };
    const onMouseLeave = () => {
      mouse.active = false;
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseleave", onMouseLeave);

    // Types of Procurement Nodes
    type NodeType = "supplier" | "warehouse" | "store";
    type Node = {
      x: number;
      y: number;
      baseX: number;
      baseY: number;
      vx: number;
      vy: number;
      type: NodeType;
      label: string;
      radius: number;
      pulsePhase: number;
    };

    const SUPPLIER_NAMES = [
      "SUP-MUMBAI",
      "SUP-DELHI",
      "SUP-BLR",
      "SUP-CHENNAI",
      "SUP-KOLKATA",
      "SUP-HYD",
      "SUP-PUNE",
      "SUP-AHMEDABAD",
    ];
    const WH_NAMES = [
      "WH-CENTRAL",
      "DC-NORTH",
      "DC-SOUTH",
      "LOGISTICS-01",
      "DEPOT-WEST",
      "DISPATCH-EAST",
    ];
    const STORE_NAMES = [
      "STORE-MAIN",
      "RETAIL-01",
      "BRANCH-BENGALURU",
      "OUTLET-03",
    ];

    const nodes: Node[] = [];
    const NODE_COUNT = 28;

    // Active Cargo Delivery Packets flowing between nodes
    type Packet = {
      fromIndex: number;
      toIndex: number;
      progress: number;
      speed: number;
      size: number;
      color: string;
    };
    const packets: Packet[] = [];

    // Floating 3D Isometric Cargo Crates
    type FloatingCrate = {
      x: number;
      y: number;
      z: number;
      size: number;
      vx: number;
      vy: number;
      rotSpeed: number;
      rot: number;
      opacity: number;
    };
    const crates: FloatingCrate[] = [];

    function resize() {
      if (!canvas) return;
      W = window.innerWidth;
      H = window.innerHeight;
      canvas.width = W;
      canvas.height = H;

      // Initialize Nodes
      nodes.length = 0;
      for (let i = 0; i < NODE_COUNT; i++) {
        let type: NodeType = "supplier";
        let label = SUPPLIER_NAMES[i % SUPPLIER_NAMES.length];
        if (i % 3 === 1) {
          type = "warehouse";
          label = WH_NAMES[i % WH_NAMES.length];
        } else if (i % 3 === 2) {
          type = "store";
          label = STORE_NAMES[i % STORE_NAMES.length];
        }

        const x = Math.random() * W;
        const y = Math.random() * H;
        nodes.push({
          x,
          y,
          baseX: x,
          baseY: y,
          vx: (Math.random() - 0.5) * 0.45,
          vy: (Math.random() - 0.5) * 0.45,
          type,
          label,
          radius: type === "warehouse" ? 6 : type === "supplier" ? 5 : 4,
          pulsePhase: Math.random() * Math.PI * 2,
        });
      }

      // Initialize Cargo Packets
      packets.length = 0;
      for (let k = 0; k < 18; k++) {
        const fromIndex = Math.floor(Math.random() * NODE_COUNT);
        let toIndex = Math.floor(Math.random() * NODE_COUNT);
        while (toIndex === fromIndex) {
          toIndex = Math.floor(Math.random() * NODE_COUNT);
        }
        packets.push({
          fromIndex,
          toIndex,
          progress: Math.random(),
          speed: 0.003 + Math.random() * 0.006,
          size: 2.5 + Math.random() * 2,
          color: k % 2 === 0 ? "#38bdf8" : "#0284c7",
        });
      }

      // Initialize 3D Floating Crates
      crates.length = 0;
      const CRATE_COUNT = 7;
      for (let c = 0; c < CRATE_COUNT; c++) {
        crates.push({
          x: Math.random() * W,
          y: Math.random() * H,
          z: 0.4 + Math.random() * 0.6,
          size: 16 + Math.random() * 24,
          vx: (Math.random() - 0.5) * 0.25,
          vy: (Math.random() - 0.5) * 0.2,
          rotSpeed: (Math.random() - 0.5) * 0.008,
          rot: Math.random() * Math.PI * 2,
          opacity: 0.12 + Math.random() * 0.14,
        });
      }
    }

    // Helper: Draw 3D Isometric Crate
    function drawIsometricCrate(
      cx: number,
      cy: number,
      size: number,
      angle: number,
      opacity: number
    ) {
      if (!ctx) return;
      ctx.save();
      ctx.translate(cx, cy);
      ctx.rotate(angle);
      ctx.globalAlpha = opacity;

      const s = size;
      const h = size * 0.58;

      // Top Face
      ctx.beginPath();
      ctx.moveTo(0, -h);
      ctx.lineTo(s, -h * 0.5);
      ctx.lineTo(0, 0);
      ctx.lineTo(-s, -h * 0.5);
      ctx.closePath();
      ctx.fillStyle = "#38bdf8";
      ctx.fill();
      ctx.strokeStyle = "#bae6fd";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Left Face
      ctx.beginPath();
      ctx.moveTo(-s, -h * 0.5);
      ctx.lineTo(0, 0);
      ctx.lineTo(0, h);
      ctx.lineTo(-s, h * 0.5);
      ctx.closePath();
      ctx.fillStyle = "#1d4ed8";
      ctx.fill();
      ctx.strokeStyle = "#60a5fa";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Right Face
      ctx.beginPath();
      ctx.moveTo(0, 0);
      ctx.lineTo(s, -h * 0.5);
      ctx.lineTo(s, h * 0.5);
      ctx.lineTo(0, h);
      ctx.closePath();
      ctx.fillStyle = "#0c1a2e";
      ctx.fill();
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 1;
      ctx.stroke();

      // Strapping Tape lines
      ctx.strokeStyle = "rgba(255, 255, 255, 0.75)";
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(0, -h * 0.5);
      ctx.lineTo(s * 0.5, -h * 0.25);
      ctx.lineTo(s * 0.5, h * 0.75);
      ctx.stroke();

      ctx.beginPath();
      ctx.moveTo(-s * 0.5, -h * 0.25);
      ctx.lineTo(0, 0);
      ctx.lineTo(0, h);
      ctx.stroke();

      ctx.restore();
    }

    // Helper: Draw Procurement Node
    function drawNode(n: Node, t: number) {
      if (!ctx) return;
      ctx.save();
      ctx.translate(n.x, n.y);

      // Pulse ring
      const pulse = ((t + n.pulsePhase) % 3) / 3;
      const pulseR = n.radius + pulse * 18;
      const pulseAlpha = (1 - pulse) * 0.35;
      ctx.beginPath();
      ctx.arc(0, 0, pulseR, 0, Math.PI * 2);
      ctx.strokeStyle = n.type === "warehouse" ? "#38bdf8" : "#2563eb";
      ctx.lineWidth = 1;
      ctx.globalAlpha = pulseAlpha;
      ctx.stroke();

      ctx.globalAlpha = 0.85;

      if (n.type === "supplier") {
        // Diamond Node
        ctx.beginPath();
        ctx.moveTo(0, -n.radius * 1.5);
        ctx.lineTo(n.radius * 1.5, 0);
        ctx.lineTo(0, n.radius * 1.5);
        ctx.lineTo(-n.radius * 1.5, 0);
        ctx.closePath();
        ctx.fillStyle = "#0284c7";
        ctx.fill();
        ctx.strokeStyle = "#38bdf8";
        ctx.lineWidth = 1.4;
        ctx.stroke();
      } else if (n.type === "warehouse") {
        // Hexagonal / Square Hub
        ctx.beginPath();
        for (let a = 0; a < 6; a++) {
          const angle = (a * Math.PI) / 3;
          const px = Math.cos(angle) * (n.radius * 1.4);
          const py = Math.sin(angle) * (n.radius * 1.4);
          if (a === 0) ctx.moveTo(px, py);
          else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.fillStyle = "#1d4ed8";
        ctx.fill();
        ctx.strokeStyle = "#93c5fd";
        ctx.lineWidth = 1.5;
        ctx.stroke();
      } else {
        // Store Beacon
        ctx.beginPath();
        ctx.arc(0, 0, n.radius, 0, Math.PI * 2);
        ctx.fillStyle = "#38bdf8";
        ctx.fill();
        ctx.strokeStyle = "#ffffff";
        ctx.lineWidth = 1.2;
        ctx.stroke();
      }

      // Center glowing pip
      ctx.beginPath();
      ctx.arc(0, 0, 1.8, 0, Math.PI * 2);
      ctx.fillStyle = "#ffffff";
      ctx.fill();

      // Telemetry Label
      ctx.font = "8.5px ui-monospace, SFMono-Regular, monospace";
      ctx.fillStyle = "#64748b";
      ctx.globalAlpha = 0.55;
      ctx.fillText(n.label, n.radius + 4, 3);

      ctx.restore();
    }

    function tick() {
      if (!ctx) return;
      time += 0.016;

      ctx.clearRect(0, 0, W, H);

      // 1. Dynamic Ambient Light Blooms (Fluid Blue/Cyan Mesh - strictly NO purple)
      const grad = ctx.createLinearGradient(0, 0, W, H);
      grad.addColorStop(0, "#f8fafc");
      grad.addColorStop(0.4, "#f0f6ff");
      grad.addColorStop(0.7, "#edf4fe");
      grad.addColorStop(1, "#f1f5f9");
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, W, H);

      // Subtle luminous radial light pool that moves softly
      const lightX = W * 0.45 + Math.sin(time * 0.4) * (W * 0.15);
      const lightY = H * 0.4 + Math.cos(time * 0.35) * (H * 0.12);
      const radGrad = ctx.createRadialGradient(
        lightX,
        lightY,
        50,
        lightX,
        lightY,
        W * 0.6
      );
      radGrad.addColorStop(0, "rgba(56, 189, 248, 0.12)");
      radGrad.addColorStop(0.6, "rgba(37, 99, 235, 0.05)");
      radGrad.addColorStop(1, "rgba(240, 246, 255, 0)");
      ctx.fillStyle = radGrad;
      ctx.fillRect(0, 0, W, H);

      // 2. High-Tech Grid Mesh with Coordinate Crosshairs
      ctx.save();
      ctx.strokeStyle = "rgba(203, 213, 225, 0.45)";
      ctx.lineWidth = 0.5;
      const GRID = 80;
      for (let x = 0; x < W; x += GRID) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, H);
        ctx.stroke();
      }
      for (let y = 0; y < H; y += GRID) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(W, y);
        ctx.stroke();
      }

      // Crosshairs at grid intersections
      ctx.strokeStyle = "rgba(56, 189, 248, 0.5)";
      ctx.lineWidth = 1;
      for (let x = GRID; x < W; x += GRID * 2) {
        for (let y = GRID; y < H; y += GRID * 2) {
          ctx.beginPath();
          ctx.moveTo(x - 3, y);
          ctx.lineTo(x + 3, y);
          ctx.moveTo(x, y - 3);
          ctx.lineTo(x, y + 3);
          ctx.stroke();
        }
      }
      ctx.restore();

      // 3. Floating 3D Isometric Cargo Boxes
      crates.forEach((c) => {
        c.x += c.vx;
        c.y += c.vy;
        c.rot += c.rotSpeed;

        if (c.x < -60) c.x = W + 60;
        if (c.x > W + 60) c.x = -60;
        if (c.y < -60) c.y = H + 60;
        if (c.y > H + 60) c.y = -60;

        drawIsometricCrate(c.x, c.y, c.size, c.rot, c.opacity);
      });

      // 4. Update Nodes & Mouse Interaction
      if (mouse.active) {
        mouse.currX += (mouse.x - mouse.currX) * 0.1;
        mouse.currY += (mouse.y - mouse.currY) * 0.1;

        // Interactive mouse radar pulse
        ctx.save();
        ctx.beginPath();
        ctx.arc(mouse.currX, mouse.currY, 32 + Math.sin(time * 4) * 8, 0, Math.PI * 2);
        ctx.strokeStyle = "rgba(56, 189, 248, 0.28)";
        ctx.lineWidth = 1.2;
        ctx.stroke();
        ctx.restore();
      }

      nodes.forEach((n) => {
        n.x += n.vx;
        n.y += n.vy;

        // Mouse proximity gentle repulsion
        if (mouse.active) {
          const mdx = n.x - mouse.currX;
          const mdy = n.y - mouse.currY;
          const mdist = Math.sqrt(mdx * mdx + mdy * mdy);
          if (mdist < 140 && mdist > 0) {
            const force = (1 - mdist / 140) * 0.8;
            n.x += (mdx / mdist) * force * 2;
            n.y += (mdy / mdist) * force * 2;
          }
        }

        // Screen wrap
        if (n.x < -30) n.x = W + 30;
        if (n.x > W + 30) n.x = -30;
        if (n.y < -30) n.y = H + 30;
        if (n.y > H + 30) n.y = -30;
      });

      // 5. Draw Supply Route Network Lines
      const MAX_DIST = 220;
      for (let i = 0; i < nodes.length; i++) {
        for (let j = i + 1; j < nodes.length; j++) {
          const dx = nodes[i].x - nodes[j].x;
          const dy = nodes[i].y - nodes[j].y;
          const dist = Math.sqrt(dx * dx + dy * dy);
          if (dist < MAX_DIST) {
            ctx.save();
            const alpha = (1 - dist / MAX_DIST) * 0.32;
            ctx.globalAlpha = alpha;
            ctx.strokeStyle = "#38bdf8";
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(nodes[i].x, nodes[i].y);
            ctx.lineTo(nodes[j].x, nodes[j].y);
            ctx.stroke();
            ctx.restore();
          }
        }
      }

      // 6. Draw Active Cargo Transit Packets (Live Flowing Deliveries)
      packets.forEach((p) => {
        p.progress += p.speed;
        if (p.progress >= 1) {
          p.progress = 0;
          p.fromIndex = p.toIndex;
          let nextTo = Math.floor(Math.random() * nodes.length);
          while (nextTo === p.fromIndex) {
            nextTo = Math.floor(Math.random() * nodes.length);
          }
          p.toIndex = nextTo;
        }

        const n1 = nodes[p.fromIndex];
        const n2 = nodes[p.toIndex];
        if (!n1 || !n2) return;

        const px = n1.x + (n2.x - n1.x) * p.progress;
        const py = n1.y + (n2.y - n1.y) * p.progress;

        ctx.save();
        ctx.beginPath();
        ctx.arc(px, py, p.size, 0, Math.PI * 2);
        ctx.fillStyle = p.color;
        ctx.shadowColor = "#38bdf8";
        ctx.shadowBlur = 6;
        ctx.fill();

        // Inner glowing core
        ctx.beginPath();
        ctx.arc(px, py, p.size * 0.45, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.restore();
      });

      // 7. Draw Nodes
      nodes.forEach((n) => drawNode(n, time));

      // 8. Faint Telemetry Corner Readout
      ctx.save();
      ctx.font = "9px ui-monospace, SFMono-Regular, monospace";
      ctx.fillStyle = "#94a3b8";
      ctx.globalAlpha = 0.5;
      ctx.fillText("PROCURAX NETWORK FLOW: ACTIVE", 280, H - 24);
      ctx.fillText("TRANSIT HUBS: 28 | CADENCE: 60 FPS", 280, H - 12);
      ctx.restore();

      animId = requestAnimationFrame(tick);
    }

    resize();
    window.addEventListener("resize", resize);
    tick();

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener("resize", resize);
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseleave", onMouseLeave);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        zIndex: 0,
        pointerEvents: "none",
      }}
    />
  );
}
