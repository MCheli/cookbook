import { defineConfig, devices } from '@playwright/test'

// Browser checks of the order flow on a phone (iPhone Safari's engine, Android Chrome) and a
// computer, against a local stack started by run.sh (or E2E_BASE_URL). Not run in CI: they need
// browsers and a database. Screenshots land in screenshots/ for a person (or Claude) to look at.
export default defineConfig({
  testDir: './tests',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL || 'http://localhost:5173',
    trace: 'retain-on-failure',
  },
  projects: [
    { name: 'iphone', use: { ...devices['iPhone 15'] } },
    { name: 'android', use: { ...devices['Pixel 7'] } },
    { name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1280, height: 900 } } },
  ],
})
