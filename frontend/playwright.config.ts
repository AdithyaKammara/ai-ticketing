import { defineConfig, devices } from '@playwright/test'

// Runs against the docker compose stack (web on :8080), freshly seeded:
//   docker compose up -d --build postgres redis migrate api web
//   docker compose run --rm api python -m app.seed --reset
//   pnpm e2e
export default defineConfig({
  testDir: './e2e',
  // The specs change shared seeded data (statuses, a deactivated agent), so run one at a time.
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8080',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
