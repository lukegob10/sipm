import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    environment: "jsdom",
    include: ["src/main/ui/test/unit/**/*.test.js"],
    restoreMocks: true,
    clearMocks: true,
  },
});
