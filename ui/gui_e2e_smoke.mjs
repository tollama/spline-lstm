import { chromium } from 'playwright';

const base = 'http://127.0.0.1:4173';
const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();
const out = [];

function ok(step, detail='') { out.push({step, status:'PASS', detail}); }
function fail(step, err) { out.push({step, status:'FAIL', detail:String(err)}); }

try {
  await page.goto(base, { waitUntil: 'networkidle', timeout: 20000 });
  ok('load-home', await page.title());
  const text = await page.textContent('body');
  if (text && text.length > 20) ok('body-rendered', `len=${text.length}`);
  else throw new Error('Body text too short');

  const targets = ['Run', 'Results', 'Dashboard'];
  for (const t of targets) {
    const link = page.getByRole('link', { name: new RegExp(t, 'i') }).first();
    if (await link.count()) {
      await link.click();
      await page.waitForLoadState('networkidle');
      ok(`nav-${t.toLowerCase()}`, page.url());
    } else {
      ok(`nav-${t.toLowerCase()}-missing`, 'link not present (non-blocking)');
    }
  }

  const runBtn = page.getByRole('button', { name: /run|start|submit/i }).first();
  if (await runBtn.count()) ok('run-button-visible', 'found');
  else ok('run-button-missing', 'not found (non-blocking)');

  await page.screenshot({ path: '/tmp/spline_gui_e2e_smoke.png', fullPage: true });
  ok('screenshot', '/tmp/spline_gui_e2e_smoke.png');
} catch (e) {
  fail('e2e-smoke', e);
} finally {
  await browser.close();
}

const failed = out.filter(x => x.status === 'FAIL');
console.log(JSON.stringify({ base, results: out, failed: failed.length }, null, 2));
process.exit(failed.length ? 1 : 0);
