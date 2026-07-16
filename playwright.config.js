import { defineConfig } from "@playwright/test";

const pythonCommand = process.platform === "win32" ? "python" : "python3";
const smokePort = Number(process.env.SIPM_UI_SMOKE_PORT || 8765);
const smokeBaseUrl = `http://127.0.0.1:${smokePort}`;
const reuseExistingServer = process.env.SIPM_UI_SMOKE_REUSE_SERVER === "true";

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
    env: {
      ...process.env,
      SIPM_UI_SMOKE_PORT: String(smokePort),
    },
    url: `${smokeBaseUrl}/health`,
    reuseExistingServer,
    timeout: 60_000,
  },
});
