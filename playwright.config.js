import { defineConfig } from "@playwright/test";

const pythonCommand = process.platform === "win32" ? "python" : "python3";
const smokePort = Number(process.env.SIPM_UI_SMOKE_PORT || 8000);
const smokeBaseUrl = `http://127.0.0.1:${smokePort}`;

export default defineConfig({
  testDir: "src/main/ui/test/e2e",
  timeout: 60_000,
  expect: {
    timeout: 10_000,
  },
  use: {
    baseURL: `${smokeBaseUrl}/project-manager`,
    trace: "on-first-retry",
  },
  webServer: {
    command: `${pythonCommand} scripts/run_ui_smoke_app.py`,
    url: `${smokeBaseUrl}/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
