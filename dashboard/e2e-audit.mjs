/**
 * IncidentOps E2E Audit Script
 * Tests the complete user flow: auth, start episode, execute actions, save
 */
import { chromium } from 'playwright';

const BASE = 'http://localhost:7860';

async function audit() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const results = [];
  const errors = [];

  // Capture console errors
  page.on('console', msg => {
    if (msg.type() === 'error') {
      errors.push(`CONSOLE ERROR: ${msg.text()}`);
    }
  });

  page.on('requestfailed', req => {
    errors.push(`FAILED REQUEST: ${req.url()} - ${req.failure()?.errorText}`);
  });

  async function test(name, fn) {
    try {
      await fn();
      results.push({ name, status: 'PASS' });
      console.log(`  ✓ ${name}`);
    } catch (e) {
      results.push({ name, status: 'FAIL', error: e.message });
      console.log(`  ✗ ${name}: ${e.message}`);
    }
  }

  console.log('\n=== IncidentOps E2E Audit ===\n');

  // 1. Homepage loads
  await test('Homepage loads', async () => {
    await page.goto(BASE, { waitUntil: 'networkidle' });
    const title = await page.title();
    const body = await page.textContent('body');
    if (!body.includes('IncidentOps') && !body.includes('incident')) {
      throw new Error('Homepage does not contain expected text');
    }
  });

  // 2. Navigation to episode page
  await test('Navigate to episode page', async () => {
    await page.goto(`${BASE}/episode`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000); // Wait for React to render
    const body = await page.textContent('body');
    if (!body.includes('Episode') && !body.includes('Fault')) {
      throw new Error('Episode page did not render properly');
    }
  });

  // 3. Check API endpoints are reachable
  await test('API /health reachable', async () => {
    const resp = await page.request.get(`${BASE}/health`);
    const json = await resp.json();
    if (json.status !== 'healthy') throw new Error(`Health check failed: ${JSON.stringify(json)}`);
  });

  await test('API /tasks reachable', async () => {
    const resp = await page.request.get(`${BASE}/tasks`);
    const json = await resp.json();
    if (!json.tasks || !Array.isArray(json.tasks)) throw new Error(`Tasks endpoint failed: ${JSON.stringify(json).slice(0, 200)}`);
    console.log(`    -> ${json.tasks.length} tasks available`);
  });

  await test('API /services reachable', async () => {
    const resp = await page.request.get(`${BASE}/services`);
    const json = await resp.json();
    if (!json.services || !Array.isArray(json.services)) throw new Error(`Services endpoint failed`);
    console.log(`    -> ${json.services.length} services available`);
  });

  await test('API /actions reachable', async () => {
    const resp = await page.request.get(`${BASE}/actions`);
    const json = await resp.json();
    if (!json.actions || !Array.isArray(json.actions)) throw new Error(`Actions endpoint failed`);
    console.log(`    -> ${json.actions.length} actions available`);
  });

  // 4. Start episode (no auth required)
  await test('Start episode via /reset', async () => {
    const resp = await page.request.post(`${BASE}/reset`, { data: {} });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`Reset failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (!json.observation) throw new Error(`Reset response missing observation`);
    const numServices = Object.keys(json.observation.services || {}).length;
    console.log(`    -> Episode started, ${numServices} services visible, fault: ${json.info?.fault_type}`);
  });

  // 5. Execute a step
  await test('Execute action via /step', async () => {
    const resp = await page.request.post(`${BASE}/step`, {
      data: { action_type: 'restart_service', target_service: 'payment-service' }
    });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`Step failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (typeof json.reward !== 'number') throw new Error(`Step response missing reward`);
    console.log(`    -> Reward: ${json.reward.toFixed(3)}`);
  });

  // 6. Auth flow
  const testUser = `e2e_${Date.now()}`;
  const testPass = 'TestPass123!';

  await test('Register new user', async () => {
    const resp = await page.request.post(`${BASE}/auth/register`, {
      data: { username: testUser, email: `${testUser}@test.com`, password: testPass }
    });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`Register failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (!json.access_token) throw new Error(`No access_token in register response`);
    console.log(`    -> User "${testUser}" registered`);
    // Store token for subsequent tests
    page.context()._testToken = json.access_token;
  });

  await test('Login with registered user', async () => {
    const resp = await page.request.post(`${BASE}/auth/login`, {
      data: { username: testUser, password: testPass }
    });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`Login failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (!json.access_token) throw new Error(`No access_token in login response`);
  });

  await test('GET /me with auth token', async () => {
    const token = page.context()._testToken;
    const resp = await page.request.get(`${BASE}/me`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`/me failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (!json.username) throw new Error(`No username in /me response`);
    console.log(`    -> Authenticated as: ${json.username}`);
  });

  // 7. Frontend UI elements
  await test('Episode page has Start Episode button', async () => {
    await page.goto(`${BASE}/episode`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2000);
    const startBtn = page.getByText('Start Episode').or(page.getByText('Start New Episode'));
    const count = await startBtn.count();
    if (count === 0) {
      // Check if page loaded at all
      const bodyText = await page.textContent('body');
      if (bodyText.length < 50) throw new Error('Episode page appears blank or empty');
      throw new Error('Start Episode button not found on page');
    }
  });

  await test('Episode page shows task selector', async () => {
    await page.goto(`${BASE}/episode`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(3000);
    const bodyText = await page.textContent('body');
    const hasTasks = bodyText.includes('OOM') || bodyText.includes('Cascade') || bodyText.includes('Fault') || bodyText.includes('Scenario');
    if (!hasTasks) {
      // Log the actual body content for debugging
      const snippet = bodyText.slice(0, 500);
      throw new Error(`Task selector not found. Page content: "${snippet}"`);
    }
  });

  // 8. Grader endpoint
  await test('Grader endpoint works', async () => {
    const resp = await page.request.post(`${BASE}/grader`, {
      data: {
        actions: [
          { action_type: 'restart_service', target_service: 'payment-service', reward: 1.0 }
        ],
        rewards: [1.0],
        final_state: { total_reward: 1.0, step_count: 1 },
        scenario: { fault_type: 'oom', difficulty: 2 },
        use_enhanced: true,
        seed: 42,
      }
    });
    if (!resp.ok()) {
      const text = await resp.text();
      throw new Error(`Grader failed: ${resp.status} - ${text}`);
    }
    const json = await resp.json();
    if (typeof json.final_score !== 'number') throw new Error(`Grader response missing final_score`);
    console.log(`    -> Score: ${(json.final_score * 100).toFixed(1)}%`);
  });

  // Summary
  console.log('\n=== Results ===');
  const passed = results.filter(r => r.status === 'PASS').length;
  const failed = results.filter(r => r.status === 'FAIL').length;
  console.log(`\nPassed: ${passed}/${results.length}`);
  console.log(`Failed: ${failed}/${results.length}`);

  if (errors.length > 0) {
    console.log(`\nConsole Errors (${errors.length}):`);
    errors.forEach(e => console.log(`  - ${e}`));
  }

  if (failed > 0) {
    console.log('\nFailed tests:');
    results.filter(r => r.status === 'FAIL').forEach(r => {
      console.log(`  - ${r.name}: ${r.error}`);
    });
  }

  await browser.close();
  process.exit(failed > 0 ? 1 : 0);
}

audit().catch(e => {
  console.error('Audit script crashed:', e);
  process.exit(1);
});
