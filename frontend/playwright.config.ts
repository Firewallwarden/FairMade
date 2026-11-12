import { defineConfig, devices } from '@playwright/test'
import { randomUUID } from 'node:crypto'
import { resolve } from 'node:path'
import { execFileSync } from 'node:child_process'

// Workers and child servers inherit one run identity. No retained demo database is used.
process.env.E2E_RUN_DIR ??= resolve('.e2e', randomUUID())
process.env.E2E_PASSWORD ??= `Browser-${randomUUID()}!`
process.env.E2E_EXPECTED_REVISION ??= execFileSync('git', ['rev-parse', 'HEAD'], { encoding: 'utf8' }).trim()
const apiPort = process.env.E2E_API_PORT ?? '8002'
const webPort = process.env.E2E_WEB_PORT ?? '5174'
process.env.E2E_API_PORT = apiPort

export default defineConfig({
  testDir: './e2e', timeout: 60_000, expect: { timeout: 10_000 },
  fullyParallel: false, workers: 1, retries: 0,
  outputDir: resolve(process.env.E2E_RUN_DIR, 'results'),
  reporter: [
    ['list'],
    ['html', { outputFolder: resolve(process.env.E2E_RUN_DIR, 'report'), open: 'never' }],
    ['json', { outputFile: resolve(process.env.E2E_RUN_DIR, 'results.json') }],
  ],
  use: { baseURL: `http://127.0.0.1:${webPort}`, actionTimeout: 15_000, trace: 'off', video: 'off', screenshot: 'only-on-failure' },
  webServer: [
    { command: 'node e2e/start-backend.mjs', url: `http://127.0.0.1:${apiPort}/health`, reuseExistingServer: false, timeout: 60_000 },
    { command: `npm run dev -- --host 127.0.0.1 --port ${webPort} --strictPort`, url: `http://127.0.0.1:${webPort}`, reuseExistingServer: false,
      env: { FAIRMADE_API_PROXY_TARGET: `http://127.0.0.1:${apiPort}` } },
  ],
  projects: [
    { name: 'setup', testMatch: /auth\.setup\.ts/ },
    { name: 'desktop', use: { ...devices['Desktop Chrome'] }, dependencies: ['setup'], testIgnore: /auth\.setup\.ts/ },
    { name: 'mobile', use: { ...devices['iPhone 13'], defaultBrowserType: 'chromium' }, dependencies: ['setup'], testIgnore: /auth\.setup\.ts/ },
  ],
})
