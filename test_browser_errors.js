const { chromium } = require('playwright');

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();

  const consoleMessages = [];
  const errors = [];

  page.on('console', msg => {
    consoleMessages.push({ type: msg.type(), text: msg.text() });
  });

  page.on('pageerror', error => {
    errors.push(error.message);
  });

  await page.goto('http://localhost:7860', { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  console.log('=== Console Messages ===');
  consoleMessages.forEach(m => console.log(`[${m.type}] ${m.text}`));

  console.log('\n=== Page Errors ===');
  errors.forEach(e => console.log(e));

  await browser.close();
})();
