/**
 * Debug blank page - check what browser actually renders
 */
import { chromium } from 'playwright';

const BASE = 'http://localhost:7860';

async function debug() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage();

  const errors = [];
  const warnings = [];

  page.on('console', msg => {
    if (msg.type() === 'error') errors.push(msg.text());
    if (msg.type() === 'warning') warnings.push(msg.text());
  });

  page.on('pageerror', err => errors.push(`PAGE ERROR: ${err.message}`));
  page.on('requestfailed', req => errors.push(`FAILED: ${req.url()}`));

  console.log('=== Loading homepage ===');
  await page.goto(BASE, { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  let bodyText = await page.textContent('body');
  let bodyHTML = await page.content();

  console.log(`Body text length: ${bodyText.length}`);
  console.log(`Body text preview: "${bodyText.slice(0, 200)}"`);

  // Check for blank states
  if (bodyText.length < 50 || bodyHTML.includes('blank') || bodyHTML.includes('Loading')) {
    console.log('\n⚠️  Page appears to be blank or loading');
  }

  console.log('\n=== Loading /episode ===');
  await page.goto(`${BASE}/episode`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(5000);

  bodyText = await page.textContent('body');
  bodyHTML = await page.content();

  console.log(`Body text length: ${bodyText.length}`);
  console.log(`Body text preview: "${bodyText.slice(0, 300)}"`);

  // Check if there are any visible elements
  const allElements = await page.$$('*');
  console.log(`Total DOM elements: ${allElements.length}`);

  // Check for React root
  const hasRoot = bodyHTML.includes('root') || bodyHTML.includes('id="root"');
  console.log(`Has root element: ${hasRoot}`);

  // Check if there are JS errors
  if (errors.length > 0) {
    console.log(`\nJS Errors (${errors.length}):`);
    errors.forEach(e => console.log(`  - ${e}`));
  }

  // Check what resources loaded
  const scripts = await page.$$eval('script[src]', scripts =>
    scripts.map(s => s.src).filter(s => !s.includes('vite') && !s.includes('hot'))
  );
  console.log(`\nLoaded scripts: ${scripts.length}`);
  scripts.forEach(s => console.log(`  - ${s}`));

  // Check for 404s in network
  const responses = [];
  page.on('response', resp => {
    if (resp.status() >= 400) responses.push(`${resp.status()} ${resp.url()}`);
  });

  await page.reload({ waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  if (responses.length > 0) {
    console.log('\nFailed responses:');
    responses.forEach(r => console.log(`  - ${r}`));
  }

  await browser.close();
}

debug().catch(e => { console.error(e); process.exit(1); });
