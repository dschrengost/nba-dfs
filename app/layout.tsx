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
import { Toaster } from "../components/ui/sonner";

export default function RootLayout({
  children,
}: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-background text-foreground">
        <a href="#content" className="skip-link">Skip to main content</a>
        <div className="flex flex-col min-h-screen">
          <TopStatusBar />
          <TopTabs />
          <Separator />
          <main id="content" role="main" className="relative flex-1 focus:outline-none">
            {children}
          </main>
          <MetricsDrawer />
        </div>
        <Toaster position="top-right" richColors />
      </body>
    </html>
  );
}
