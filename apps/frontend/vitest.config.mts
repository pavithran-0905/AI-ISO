import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./tests/setup.ts"],
    include: ["**/*.test.{ts,tsx}"],
    exclude: ["node_modules/**", ".next/**", "tests/e2e/**"],
    coverage: {
      provider: "v8",
      reporter: ["text", "text-summary"],
      include: [
        "app/**",
        "api/**",
        "auth/**",
        "permissions/**",
        "components/**",
        "layouts/**",
        "lib/**",
        "modules/**",
        "state/**",
        "providers/**",
        "utils/**",
        "config/**",
      ],
      exclude: ["**/*.d.ts", "**/*.config.*", "**/*.md"],
    },
  },
});
