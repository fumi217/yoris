import { defineConfig, devices } from '@playwright/test'

// E2E（spec 001 の T091）。手元で `docker compose --profile e2e run --rm e2e` で動かす（CI には入れない）。
// アプリは起動済み（docker compose up -d）の前提。開発の DB と、開発用のユーザー切り替えを使う。
export default defineConfig({
  testDir: './tests/e2e',
  // 同じ DB・Redis を共有するので、1 本ずつ動かす
  workers: 1,
  fullyParallel: false,
  reporter: [['list'], ['html', { open: 'never' }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
