import type { ReactNode } from "react";

export const metadata = {
  title: "NBA-DFS",
  description: "UI Shell for NBA-DFS tools",
};

import "../styles/globals.css";
import TopStatusBar from "../components/ui/TopStatusBar";
import TopTabs from "../components/ui/TopTabs";
import MetricsDrawer from "../components/ui/MetricsDrawer";
import { Separator } from "../components/ui/separator";

export default function RootLayout({
  children,
}: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground">
        <div className="flex flex-col min-h-screen">
          <TopStatusBar />
          <TopTabs />
          <Separator />
          <div className="relative flex-1">
            {children}
          </div>
          <MetricsDrawer />
        </div>
      </body>
    </html>
  );
}
