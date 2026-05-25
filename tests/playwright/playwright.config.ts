import { defineConfig, devices } from '@playwright/test';
import * as dotenv from 'dotenv';
import path from 'path';
import { fileURLToPath } from 'url';

// ES module equivalent of __dirname
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Read from default ".env" file.
dotenv.config({ path: path.resolve(__dirname, '.env') });

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: 1,

  // Configure HTML reporter with attachments visible and auto-open
  reporter: [
    ['html', {
      open: 'never',  // Auto-open report after test completion
    }],
    ['json', { outputFile: 'test-results/results.json' }],  // JSON output with full details
    ['list']  // Also show list output in terminal
  ],

  use: {
    baseURL: process.env.BASE_URL || 'http://localhost:8000',
    trace: 'on-first-retry',
    extraHTTPHeaders: {
      'Accept': 'application/json',
    },
  },

  projects: [
    {
      name: 'api',
      // We don't need UI browsers for pure API testing, but we can leave this generic
    },
  ],

  // Auto-start and auto-stop the Django development server
  webServer: {
    command: 'cd ../.. && source .venv/bin/activate && python manage.py runserver --settings=settings.development',
    url: `${process.env.BASE_URL || 'http://localhost:8000'}/health/simple`,  // Use simple health check endpoint
    reuseExistingServer: !process.env.CI,  // Reuse server in local dev, fresh in CI
    timeout: 30 * 1000,  // Wait up to 30 seconds for the server to start
    stdout: 'pipe',  // Capture server output
    stderr: 'pipe',  // Capture server errors
  },
});
