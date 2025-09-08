import { defineConfig } from "vitest/config";
import path from "path";

export default defineConfig({
  test: {
    exclude: [
      "**/node_modules/**",
      "**/dist/**", 
      "**/e2e/**", // Exclude E2E tests (use Playwright instead)
    ],
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname),
    },
  },
});

