/**
 * IncidentOps - E2E Tests: Critical User Flows
 */
import { test, expect } from '@playwright/test';

const BASE = process.env.BASE_URL || 'http://localhost:7860';

test.describe('IncidentOps Dashboard', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(BASE);
  });

  test('homepage loads', async ({ page }) => {
    const consoleLogs: string[] = [];
    const consoleErrors: string[] = [];

    page.on('console', msg => {
      if (msg.type() === 'error') {
        consoleErrors.push(msg.text());
      } else {
        consoleLogs.push(`[${msg.type()}] ${msg.text()}`);
      }
    });

    await page.goto(BASE, { waitUntil: 'networkidle' });
    await expect(page).toHaveTitle(/IncidentOps/);

    // Check for console errors
    if (consoleErrors.length > 0) {
      console.log('Console errors:', consoleErrors);
    }
    console.log('Console logs:', consoleLogs.slice(0, 10));

    // Verify the page has loaded (even if React hasn't rendered)
    const html = await page.content();
    expect(html).toContain('IncidentOps');
  });

  test('API health check works', async ({ page }) => {
    const response = await page.request.get(`${BASE}/health`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.status).toBe('healthy');
  });

  test('reset starts an episode', async ({ page }) => {
    const response = await page.request.post(`${BASE}/reset`, {
      data: { seed: 42, fault_type: 'oom' },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('observation');
  });

  test('step executes an action', async ({ page }) => {
    // Reset first
    await page.request.post(`${BASE}/reset`, {
      data: { seed: 42 },
    });

    const response = await page.request.post(`${BASE}/step`, {
      data: {
        action_type: 'query_service',
        target_service: 'api-gateway',
      },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('observation');
    expect(data).toHaveProperty('reward');
  });

  test('services list returns 15 services', async ({ page }) => {
    const response = await page.request.get(`${BASE}/services`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.services.length).toBe(15);
  });

  test('actions list returns 11 actions', async ({ page }) => {
    const response = await page.request.get(`${BASE}/actions`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.actions.length).toBe(11);
  });

  test('tasks returns at least 3 tasks', async ({ page }) => {
    const response = await page.request.get(`${BASE}/tasks`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data.tasks.length).toBeGreaterThanOrEqual(3);
  });

  test('validation runs successfully', async ({ page }) => {
    const response = await page.request.get(`${BASE}/validation`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('total_tests');
    expect(data).toHaveProperty('passed');
  });

  test('grader grades trajectory', async ({ page }) => {
    const response = await page.request.post(`${BASE}/grader`, {
      data: {
        actions: [
          { action_type: 'query_service', target_service: 'api-gateway' },
          { action_type: 'restart_service', target_service: 'payment-service' },
        ],
        final_state: { terminated: true },
        scenario: { fault_type: 'oom', difficulty: 2 },
        use_enhanced: true,
      },
    });
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('final_score');
    expect(data.final_score).toBeGreaterThanOrEqual(0);
    expect(data.final_score).toBeLessThanOrEqual(1);
  });

  test('determinism check passes', async ({ page }) => {
    const response = await page.request.get(`${BASE}/determinism/check`);
    expect(response.ok()).toBeTruthy();
  });

  test('frontier scenario returns data', async ({ page }) => {
    const response = await page.request.get(`${BASE}/frontier`);
    expect(response.ok()).toBeTruthy();
    const data = await response.json();
    expect(data).toHaveProperty('scenario_id');
    expect(data).toHaveProperty('difficulty');
  });
});
