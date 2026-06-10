import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/main/ui/test/unit/**/*.test.js"],
    restoreMocks: true,
    clearMocks: true,
    coverage: {
      provider: "v8",
      include: ["src/main/ui/js/**/*.js"],
      exclude: ["src/main/ui/js/app.js"],
      reporter: ["text", "json-summary"],
      thresholds: {
        statements: 18,
        branches: 15,
        functions: 20,
        lines: 19,
      },
    },
  },
});
