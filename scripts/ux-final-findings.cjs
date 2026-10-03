/* Read-only verification of final audit claims. Does not modify product code. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '../.venv/Lib/site-packages/playwright/driver/package');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const evidence = path.join(root, 'docs/evidence');
fs.mkdirSync(evidence, { recursive: true });

(async () => {
  const report = { tested_at: new Date().toISOString(), base_url: process.env.OKNO_URL || 'http://localhost:18430',
    purpose: 'Independent reproduction of final audit date-range and empty-catalog claims. No UI changes or disabled-control bypass.',
    methods: [], catalogue: null, page_errors: [], status: 'running',
    limitations: ['Chromium automation with fresh sessions; not a human screen-reader test.', 'A failure to reproduce a claim applies only to the documented methods and tested build.'] };
  const browser = await chromium.launch({ headless: true, args: process.env.CHROMIUM_HOST_IP ? ['--host-resolver-rules=MAP localhost ' + process.env.CHROMIUM_HOST_IP] : [] });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const redact = error => (error.stack || String(error)).replace(/^(\s*-?\s*(?:cookie|authorization|x-csrf-token):).*$/gim, '$1 [redacted]');
  for (const method of ['normal-fill', 'keyboard-day-segment']) {
    const item = { method, inputs: [], observed_solve_requests: [], observed_solve_responses: [], snapshots: [], status: 'running' };
    report.methods.push(item);
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'pl-PL', ignoreHTTPSErrors: !!process.env.OKNO_TEST_LOCAL_CA });
    const page = await context.newPage();
    page.setDefaultTimeout(15000);
    page.on('pageerror', error => report.page_errors.push({ method, error: error.message }));
    page.on('request', request => {
      if (new URL(request.url()).pathname === '/api/solve' && request.method() === 'POST') {
        const input = request.postDataJSON();
        item.observed_solve_requests.push({ start_date: input.start_date, end_date: input.end_date, version: input.version });
      }
    });
    const responses = [];
    page.on('response', response => {
      if (new URL(response.url()).pathname === '/api/solve' && response.request().method() === 'POST') responses.push((async () => {
        const body = await response.json();
        item.observed_solve_responses.push({ http_status: response.status(), status: body.status, data_status: body.data_status, checked_period: body.checked_period, alternatives: body.alternatives?.length, detail: body.detail });
      })());
    });
    const end = page.locator('#editor-end_date');
    const solve = page.getByRole('button', { name: 'Sprawdź mój plan', exact: true });
    const settle = () => page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    const leaveDateField = async () => {
      for (let count = 0; count < 6; count++) {
        if (!await end.evaluate(el => el === document.activeElement)) return;
        await page.keyboard.press('Tab');
      }
      assert(!await end.evaluate(el => el === document.activeElement), 'Tab did not leave the native date field');
    };
    const snapshot = async stage => {
      const result = { stage, start: await page.locator('#editor-start_date').inputValue(), end: await end.inputValue(),
        solve_enabled: await solve.isEnabled(), aria_invalid: await end.getAttribute('aria-invalid'), aria_describedby: await end.getAttribute('aria-describedby'),
        field_errors: await end.locator('..').locator('.error-text').allTextContents(),
        field_accessibility_snapshot: await end.ariaSnapshot(), label_accessibility_snapshot: await end.locator('..').ariaSnapshot(),
        summary: await page.locator('#editor-validation-summary').allTextContents(),
        focused_id: await page.evaluate(() => document.activeElement?.id || '') };
      item.snapshots.push(result);
      return result;
    };
    try {
      await page.goto(report.base_url, { waitUntil: 'networkidle', timeout: 60000 });
      await page.getByRole('combobox', { name: 'Wybierz przykład' }).selectOption('single-parent');
      await page.getByLabel('Miejsce (krótka etykieta)').waitFor();
      report.frontend_assets = await page.evaluate(() => [...document.scripts].map(script => script.src).filter(Boolean));
      assert(await end.inputValue() === '2026-10-09', 'Unexpected starting end date');
      await snapshot('initial-example');
      await page.evaluate(() => {
        window.__endDateEvents = [];
        const input = document.querySelector('#editor-end_date');
        for (const name of ['input', 'change', 'blur']) input.addEventListener(name, event => window.__endDateEvents.push({ type: event.type, trusted: event.isTrusted, value: input.value }));
      });
      if (method === 'normal-fill') {
        await end.fill('2026-10-01');
        item.inputs.push({ action: 'locator.fill', value: '2026-10-01' });
      } else {
        let reached = false;
        for (let count = 0; count < 150; count++) {
          if (await end.evaluate(el => el === document.activeElement)) { reached = true; break; }
          await page.keyboard.press('Tab');
        }
        assert(reached, 'Could not reach end-date field by keyboard');
        let daySegment = false;
        // Probe the selected native date segment using only real key events.
        // Undo a month/year probe before moving to the next segment.
        for (let attempt = 0; attempt < 3; attempt++) {
          await page.keyboard.press('ArrowDown');
          const value = await end.inputValue();
          item.inputs.push({ key: 'ArrowDown', resulting_value: value });
          if (value === '2026-10-08') { daySegment = true; break; }
          await page.keyboard.press('ArrowUp');
          item.inputs.push({ key: 'ArrowUp', resulting_value: await end.inputValue() });
          assert(await end.inputValue() === '2026-10-09', 'Could not restore the starting date after identifying the native segment');
          await page.keyboard.press('ArrowRight');
          item.inputs.push({ key: 'ArrowRight' });
        }
        assert(daySegment, 'Could not identify the native day segment with keyboard events');
        for (let count = 0; count < 7; count++) {
          await page.keyboard.press('ArrowDown');
          item.inputs.push({ key: 'ArrowDown', resulting_value: await end.inputValue() });
        }
      }
      await snapshot('after-edit-before-blur');
      assert(await end.inputValue() === '2026-10-01', 'The method did not enter the requested target date');
      await leaveDateField();
      await settle();
      await snapshot('after-blur');
      await page.waitForTimeout(350);
      const stable = await snapshot('after-validation-settled');
      await page.locator('.goal-grid').scrollIntoViewIfNeeded();
      await page.screenshot({ path: path.join(evidence, 'ux-final-date-' + method + '.png'), animations: 'disabled' });
      if (stable.solve_enabled) {
        item.solve_action = 'Normal enabled-button click; no forced DOM/API action';
        await solve.click();
        await page.waitForTimeout(2500);
        await Promise.all(responses);
      } else item.solve_action = 'Button disabled; no click or direct API request attempted';
      item.input_events = await page.evaluate(() => window.__endDateEvents);
      assert(item.input_events.some(event => event.type === 'blur' && event.trusted), 'The invalid-date method did not trigger a real blur event');
      if (await page.getByRole('button', { name: 'Zmień dane', exact: true }).count()) {
        await page.getByRole('button', { name: 'Zmień dane', exact: true }).click();
      } else {
        await page.getByRole('button', { name: /Twoje możliwości Konflikt/ }).click();
        await page.getByRole('button', { name: /Twój plan Godziny/ }).click();
      }
      await end.waitFor();
      await settle();
      const returned = await snapshot('after-leaving-and-returning-to-form');
      item.original_claim_reproduced = item.observed_solve_requests.some(request => request.end_date === '2026-10-09')
        && item.observed_solve_responses.some(response => ['OPTIMAL', 'FEASIBLE'].includes(response.status) && response.checked_period?.end === '2026-10-09');
      item.entered_date_reverted_after_navigation = returned.end !== '2026-10-01';
      item.range_error_has_aria_invalid_and_describedby = stable.aria_invalid === 'true' && Boolean(stable.aria_describedby);
      item.range_error_appears_in_wrapping_label = stable.field_errors.some(message => stable.label_accessibility_snapshot.includes(message));
      item.visible_range_error = stable.field_errors.length > 0;
      const invalidRequests = [...item.observed_solve_requests];
      item.invalid_date_requests = invalidRequests;
      item.invalid_date_responses = [...item.observed_solve_responses];
      await end.fill('2026-10-08');
      await leaveDateField();
      await settle();
      const positiveState = await snapshot('positive-control-valid-end');
      assert(positiveState.solve_enabled, 'Positive control: valid changed end date did not enable analysis');
      const positiveResponse = page.waitForResponse(response => new URL(response.url()).pathname === '/api/solve' && response.request().method() === 'POST', { timeout: 45000 });
      await solve.click();
      const accepted = await positiveResponse;
      const actualInput = accepted.request().postDataJSON();
      const actualResult = await accepted.json();
      item.positive_control = { action: 'Normal fill of valid changed end followed by normal enabled-button click', entered_end: positiveState.end,
        request: { start_date: actualInput.start_date, end_date: actualInput.end_date }, http_status: accepted.status(), status: actualResult.status,
        checked_period: actualResult.checked_period, invalid_date_request_count: invalidRequests.length };
      assert(accepted.ok() && actualInput.end_date === '2026-10-08' && actualResult.checked_period?.end === '2026-10-08', 'Positive control did not analyse the actual changed date');
      item.status = 'observed';
      fs.rmSync(path.join(evidence, 'ux-final-error-' + method + '.png'), { force: true });
      console.log(JSON.stringify({ method, solve_enabled: stable.solve_enabled, invalid_date_requests: invalidRequests, returned_end: returned.end,
        original_claim_reproduced: item.original_claim_reproduced, visible_error: stable.field_errors, aria_invalid: stable.aria_invalid, aria_describedby: stable.aria_describedby,
        label_accessibility_snapshot: stable.label_accessibility_snapshot, positive_control: item.positive_control }));
      if (method === 'normal-fill') {
        await page.getByRole('button', { name: /Katalog źródeł/ }).click();
        await page.getByRole('textbox', { name: 'Szukaj w katalogu', exact: true }).waitFor();
        const before = await page.locator('.catalog-card').count();
        await page.getByRole('textbox', { name: 'Szukaj w katalogu', exact: true }).fill('zzzz-brak-rekordu-ux-final-2026');
        const empty = page.getByRole('heading', { name: 'Nie ma pasujących źródeł', exact: true });
        await empty.waitFor();
        report.catalogue = { query: 'zzzz-brak-rekordu-ux-final-2026', cards_before: before, cards_after: await page.locator('.catalog-card').count(),
          visible_heading: await empty.innerText(),
          empty_container_semantics: await empty.locator('..').evaluate(el => ({ role: el.getAttribute('role'), aria_live: el.getAttribute('aria-live'),
            enclosing_live_region: !!el.closest('[role="status"], [role="alert"], [aria-live="polite"], [aria-live="assertive"]') })),
          live_regions: await page.locator('[role="status"], [role="alert"], [aria-live]').evaluateAll(elements => elements.map(el => ({ role: el.getAttribute('role'), aria_live: el.getAttribute('aria-live'), text: el.textContent?.trim() }))) };
        report.catalogue.result_change_live_announcement_found = report.catalogue.live_regions.some(region => /Nie ma pasujących źródeł|liczba wyników:\s*0\b|0.*wynik|brak.*wynik/i.test(region.text || ''));
        await page.screenshot({ path: path.join(evidence, 'ux-final-catalogue-no-results.png'), fullPage: true, animations: 'disabled' });
      }
    } catch (error) {
      item.status = 'inconclusive'; item.error = redact(error);
      await page.screenshot({ path: path.join(evidence, 'ux-final-error-' + method + '.png'), fullPage: true, animations: 'disabled' }).catch(() => {});
      console.log(JSON.stringify({ method, error: item.error }));
    } finally { await context.close(); }
  }
  report.status = report.methods.every(item => item.status === 'observed') ? 'verification-complete' : 'verification-partial';
  report.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(evidence, 'ux-final-findings.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log(JSON.stringify({ status: report.status, original_claim_reproduced: report.methods.some(item => item.original_claim_reproduced), catalogue: report.catalogue }));
})().catch(error => { console.error(String(error)); process.exitCode = 1; });
