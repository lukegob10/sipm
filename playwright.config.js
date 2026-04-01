import { defineConfig } from "@playwright/test";

const pythonCommand = process.platform === "win32" ? "python" : "python3";

export default defineConfig({
  testDir: "src/main/ui/test/e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: "http://127.0.0.1:8000/project-manager",
    trace: "on-first-retry",
  },
  webServer: {
    command: `${pythonCommand} scripts/run_ui_smoke_app.py`,
    url: "http://127.0.0.1:8000/health",
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
