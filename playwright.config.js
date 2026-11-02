import {defineConfig} from '@playwright/test';

const browserName = process.env.PLAYWRIGHT_BROWSER || 'chromium';
const endpoint = process.env.PW_TEST_CONNECT_WS_ENDPOINT;

export default defineConfig({
  testDir: './tests/browser',
  fullyParallel: true,
  workers: 2,
  retries: process.env.CI ? 1 : 0,
  reporter: [['list'], ['html', {open: 'never'}]],
  snapshotPathTemplate: '{testDir}/../../docs/gallery/{arg}{ext}',
  expect: {toHaveScreenshot: {maxDiffPixelRatio: .002, animations: 'disabled'}},
  use: {
    baseURL: 'http://127.0.0.1:8765', locale: 'en-US', timezoneId: 'UTC',
    browserName, deviceScaleFactor: 1, trace: 'retain-on-failure',
    launchOptions: {timeout: 30000},
    connectOptions: browserName === 'chromium' && endpoint ? {wsEndpoint: endpoint, timeout: 10000} : undefined,
  },
  webServer: {
    command: `${process.env.PYTHON || '.venv/bin/python'} scripts/browser_server.py`,
    url: 'http://127.0.0.1:8765/admin/login/', reuseExistingServer: !process.env.CI,
    timeout: 60000,
  },
});
