"use client";

import { usePathname, useRouter } from "next/navigation";
import { Tabs, TabsList, TabsTrigger } from "./tabs";

const tabs = [
  { label: "Optimizer", slug: "optimizer" },
  { label: "Variants", slug: "variants" },
  { label: "Field", slug: "field" },
  { label: "Simulator", slug: "simulator" },
];

export default function TopTabs() {
  const pathname = usePathname() || "/optimizer";
  const router = useRouter();
  const current = tabs.find((t) => pathname.startsWith(`/${t.slug}`))?.slug ?? "optimizer";
  return (
    <div className="h-[60px] w-full border-b border-border px-4 flex items-end bg-background">
      <Tabs
        value={current}
        onValueChange={(v) => router.push(`/${v}`)}
        aria-label="Primary navigation"
      >
        <TabsList>
          {tabs.map((t) => (
            <TabsTrigger key={t.slug} value={t.slug} aria-label={t.label}>
              {t.label}
            </TabsTrigger>
          ))}
        </TabsList>
      </Tabs>
    </div>
  );
}
