"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const tabs = [
  { label: "Optimizer", href: "/optimizer" },
  { label: "Variants", href: "/variants" },
  { label: "Field", href: "/field" },
  { label: "Simulator", href: "/simulator" },
];

export default function TopTabs() {
  const pathname = usePathname() || "/optimizer";
  return (
    <div className="h-[60px] w-full border-b border-border px-4 flex items-end bg-background">
      <nav className="flex gap-6" aria-label="Primary">
        {tabs.map((t) => {
          const active = pathname.startsWith(t.href);
          return (
            <Link
              key={t.href}
              href={t.href}
              aria-current={active ? "page" : undefined}
              className={`pb-3 text-sm font-medium focus:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                active ? "text-foreground border-b-2 border-primary" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.label}
            </Link>
          );
        })}
      </nav>
    </div>
  );
}

