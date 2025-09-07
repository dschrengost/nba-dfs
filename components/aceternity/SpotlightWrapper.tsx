"use client";

// Optional lightweight spotlight hover effect wrapper.
export default function SpotlightWrapper({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative group">
      <div className="absolute inset-0 rounded-md opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none"
           style={{ background: "radial-gradient(600px circle at var(--x, 50%) var(--y, 50%), rgba(255,255,255,0.06), transparent 40%)" }}
      />
      {children}
    </div>
  );
}

