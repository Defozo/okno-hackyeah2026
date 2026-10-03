/* Keyboard-only browser acceptance check. No pointer, focus(), fill(), or API setup. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '../.venv/Lib/site-packages/playwright/driver/package');
const fs = require('node:fs');
const path = require('node:path');
const evidence = path.resolve(__dirname, '..', 'docs', 'evidence');
fs.mkdirSync(evidence, { recursive: true });

(async () => {
  const report = {
    tested_at: new Date().toISOString(),
    base_url: process.env.OKNO_URL || 'http://localhost:18430',
    status: 'running',
    input_method: 'Playwright keyboard Tab, Shift+Tab, Enter, Space, Escape, Control+A and insertText on the already focused input',
    pointer_or_programmatic_focus_used: false,
    screen_reader_tested: false,
    limitations: ['Automated keyboard and browser accessibility semantics check; not a human usability study or an NVDA/JAWS/VoiceOver test.', 'Single Chromium desktop viewport, fresh browser session, synthetic at-home offer.'],
    navigation: [], flows: [], focus_trap: [], page_errors: [], console_errors: []
  };
  const browser = await chromium.launch({ headless: true, args: process.env.CHROMIUM_HOST_IP ? ['--host-resolver-rules=MAP localhost ' + process.env.CHROMIUM_HOST_IP] : [] });
  const context = await browser.newContext({ viewport: { width: 1440, height: 1000 }, locale: 'pl-PL', ignoreHTTPSErrors: !!process.env.OKNO_TEST_LOCAL_CA });
  const page = await context.newPage();
  page.on('pageerror', error => report.page_errors.push(error.message));
  page.on('console', message => { if (message.type() === 'error') report.console_errors.push(message.text()); });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const active = () => page.evaluate(() => {
    const el = document.activeElement;
    return { tag: el?.tagName, role: el?.getAttribute('role'), name: el?.getAttribute('aria-label') || el?.textContent?.trim().slice(0, 100) || el?.getAttribute('name') || el?.id || '', in_dialog: !!el?.closest('[role="dialog"]') };
  });
  const focused = async locator => (await locator.count()) === 1 && await locator.evaluate(el => el === document.activeElement);
  const tabTo = async (locator, name, maxTabs = 180) => {
    await locator.waitFor({ state: 'visible', timeout: 45000 });
    for (let tabs = 0; tabs <= maxTabs; tabs++) {
      if (await focused(locator)) {
        report.navigation.push({ target: name, tabs, active: await active() });
        return;
      }
      await page.keyboard.press('Tab');
    }
    throw new Error('Keyboard could not reach ' + name + ': ' + JSON.stringify(await active()));
  };
  const activate = async (locator, name) => { await tabTo(locator, name); await page.keyboard.press('Enter'); };
  const type = async (locator, name, value) => {
    await tabTo(locator, name);
    await page.keyboard.press('Control+A');
    await page.keyboard.insertText(value);
    assert(await locator.inputValue() === value, 'Typed value mismatch: ' + name);
  };
  const flow = name => { report.flows.push(name); console.log(name); };
  const dialog = () => page.getByRole('dialog');
  const title = 'Próba klawiatury ' + new Date().toISOString();
  try {
    await page.goto(report.base_url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.getByRole('combobox', { name: 'Wybierz przykład' }).waitFor({ timeout: 30000 });
    await page.keyboard.press('Tab');
    assert(await focused(page.getByRole('link', { name: 'Przejdź do treści' })), 'Skip link is not the first keyboard target');
    await page.keyboard.press('Enter');
    flow('First Tab reaches the skip link; Enter activates it');
    await type(page.getByLabel('Nazwa Twojego planu', { exact: true }), 'plan title', title);
    await activate(page.getByRole('button', { name: 'Dodaj ofertę lub zajęcia', exact: true }), 'add own offer');
    await type(page.getByLabel('Nazwa oferty lub zajęć', { exact: true }), 'offer title', 'Praca w domu, próba klawiatury');
    await type(page.getByLabel('Miejsce (krótka etykieta)'), 'offer location', 'dom');
    await type(page.getByLabel('Początek zajęć', { exact: true }), 'offer start', '09:00');
    await activate(page.getByRole('button', { name: 'Sprawdź mój plan', exact: true }), 'analyse own offer');
    await page.getByRole('heading', { name: 'Przyjrzyjmy się Twoim możliwościom' }).waitFor({ timeout: 45000 });
    await page.locator('.alternative').first().waitFor({ timeout: 45000 });
    assert((await page.locator('.alternative').count()) > 0, 'At-home offer produced no feasible result');
    flow('Own at-home offer entered and analysed using keyboard only');

    const saveInvoker = page.getByRole('button', { name: 'Zapisz plan', exact: true });
    await activate(saveInvoker, 'open save dialog');
    await page.getByRole('heading', { name: 'Chcesz wrócić do swojego planu?' }).waitFor();
    report.save_dialog_accessibility_snapshot = await dialog().ariaSnapshot();
    const consent = page.getByRole('checkbox', { name: 'Chcę zapisać te dane i rozumiem sposób dostępu.' });
    assert(!(await consent.isChecked()), 'Save consent is unexpectedly preselected');
    assert(await page.getByRole('button', { name: 'Zapisz mój plan', exact: true }).isDisabled(), 'Save action enabled before consent');
    for (const key of [...Array(7).fill('Tab'), ...Array(7).fill('Shift+Tab')]) {
      await page.keyboard.press(key);
      const state = await active();
      report.focus_trap.push({ key, ...state });
      assert(state.in_dialog, 'Keyboard focus escaped modal: ' + JSON.stringify(state));
    }
    assert(new Set(report.focus_trap.map(s => s.tag + ':' + s.name)).size >= 2, 'Focus trap test did not traverse distinct controls');
    await page.keyboard.press('Escape');
    await dialog().waitFor({ state: 'hidden' });
    await page.waitForFunction(() => document.activeElement?.tagName === 'BUTTON' && document.activeElement.textContent?.trim() === 'Zapisz plan', null, { timeout: 3000 });
    report.save_dialog_focus_restored = await focused(saveInvoker);
    assert(report.save_dialog_focus_restored, 'Escape did not return focus to the save dialog invoker');
    flow('Save dialog requires explicit consent; Tab and Shift+Tab stay inside; Escape restores the opening button');

    await page.keyboard.press('Enter');
    await dialog().waitFor({ state: 'visible' });
    await tabTo(consent, 'save consent');
    await page.keyboard.press('Space');
    assert(await consent.isChecked(), 'Space did not select consent');
    await activate(page.getByRole('button', { name: 'Zapisz mój plan', exact: true }), 'confirm save');
    await dialog().waitFor({ state: 'hidden', timeout: 45000 });
    await page.locator('.session-status').filter({ hasText: 'Zapisany · wersja 1' }).waitFor({ timeout: 45000 });
    flow('Explicit consent selected with Space and synthetic plan saved');

    await activate(page.getByRole('button', { name: /Zapisane plany/ }), 'open saved plans');
    await page.getByRole('heading', { name: 'Twoje zapisane plany' }).waitFor();
    assert(await dialog().getByText(title, { exact: true }).count() === 1, 'Saved plan is not in the session list');
    await activate(page.getByRole('button', { name: 'Bieżący plan', exact: true }), 'manage current plan');
    await page.getByRole('heading', { name: 'Kopia, historia i usunięcie' }).waitFor();
    await activate(page.getByRole('button', { name: 'Usuń bieżący plan', exact: true }), 'open delete confirmation');
    await page.getByRole('heading', { name: 'Usunąć plan i jego historię?' }).waitFor();
    await activate(page.getByRole('button', { name: 'Usuń plan i powiązane dane', exact: true }), 'confirm test plan deletion');
    await dialog().waitFor({ state: 'hidden', timeout: 45000 });
    await page.locator('.session-status').filter({ hasText: 'Bez zapisu' }).waitFor();
    await activate(page.getByRole('button', { name: /Zapisane plany/ }), 'verify saved list after deletion');
    await page.getByRole('heading', { name: 'Twoje zapisane plany' }).waitFor();
    assert(await dialog().getByText(title, { exact: true }).count() === 0, 'Deleted test plan remains in list');
    assert((await dialog().innerText()).includes('Nie masz jeszcze zapisanych planów'), 'Session list is not empty after deletion');
    await page.keyboard.press('Escape');
    await dialog().waitFor({ state: 'hidden' });
    report.test_plan_deleted = true;
    flow('Saved plan managed, explicitly deleted, and absence verified using keyboard only');
    assert(report.page_errors.length === 0, 'JavaScript errors occurred');
    assert(report.console_errors.length === 0, 'Browser console errors occurred');
    report.status = 'passed';
  } catch (error) {
    report.status = 'failed';
    report.error = error.stack || String(error);
    report.focus_at_failure = await active().catch(() => null);
    await page.screenshot({ path: path.join(evidence, 'keyboard-failure.png'), fullPage: true }).catch(() => {});
    process.exitCode = 1;
  } finally {
    report.finished_at = new Date().toISOString();
    fs.writeFileSync(path.join(evidence, 'keyboard-report.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ status: report.status, flows: report.flows, error: report.error, test_plan_deleted: report.test_plan_deleted }));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
