import { defineConfig, devices } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  timeout: 120000,
  expect: {timeout:20000},
  use: {
    baseURL: process.env.BASE_URL || "http://localhost:3001",
    trace: "retain-on-failure",
    channel: "chrome",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    {
      name: "mobile",
      use: { ...devices["iPhone 13"], defaultBrowserType: "chromium" },
    },
  ],
  reporter: "list",
});
