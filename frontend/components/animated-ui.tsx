"use client";

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
