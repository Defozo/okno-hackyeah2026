/* UX regressions: real API first, explicitly labelled response mocks afterwards. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || '../.venv/Lib/site-packages/playwright/driver/package');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const evidence = path.join(root, 'docs', 'evidence');
fs.mkdirSync(evidence, { recursive: true });

(async () => {
  const report = {
    tested_at: new Date().toISOString(), base_url: process.env.OKNO_URL || 'http://localhost:18430',
    script_sha256: require('node:crypto').createHash('sha256').update(fs.readFileSync(__filename)).digest('hex'),
    status: 'running', real_api: [], mocked_responses: [], mobile_navigation: {}, axe: [], screenshots: [],
    page_errors: [], console_errors: [], expected_console_errors: [],
    limitations: ['Automated Chromium keyboard, accessibility tree and rendering regression; not a human usability study or a screen-reader session.',
      'Blank and corrected own-offer analyses, the Polish example and its original-reference comparison use the real API. Subsequent status cases intercept only /api/solve and are reported separately.',
      'The first save is an explicitly simulated HTTP 429; retry and deletion use the real API. Only this script\'s synthetic plan is saved and deleted. No external messages.']
  };
  const offlineEvidence = path.join(evidence, 'example-label-contract.json');
  if (fs.existsSync(offlineEvidence)) {
    report.offline_example_contract = JSON.parse(fs.readFileSync(offlineEvidence, 'utf8'));
    report.offline_example_contract.source_matches_current_code = report.offline_example_contract.source_sha256 === require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(root, 'web/src/types.ts'))).digest('hex');
  }
  const browser = await chromium.launch({ headless: true, args: process.env.CHROMIUM_HOST_IP ? ['--host-resolver-rules=MAP localhost ' + process.env.CHROMIUM_HOST_IP] : [] });
  const context = await browser.newContext({ viewport: { width: 390, height: 844 }, locale: 'pl-PL', ignoreHTTPSErrors: !!process.env.OKNO_TEST_LOCAL_CA });
  const page = await context.newPage();
  page.setDefaultTimeout(15000);
  let expectedSave429 = false;
  page.on('pageerror', error => report.page_errors.push(error.message));
  page.on('console', message => {
    if (message.type() !== 'error') return;
    if (expectedSave429 && /429/.test(message.text()) && message.location().url.includes('/api/plans')) report.expected_console_errors.push({ case: 'simulated-save-429', text: message.text() });
    else report.console_errors.push(message.text());
  });
  let phase = 'real-api';
  let realSolveRequests = 0;
  page.on('request', request => {
    if (phase === 'real-api' && new URL(request.url()).pathname === '/api/solve' && request.method() === 'POST') realSolveRequests++;
  });
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const focused = async locator => await locator.count() === 1 && await locator.evaluate(el => el === document.activeElement);
  const active = () => page.evaluate(() => {
    const el = document.activeElement;
    return { tag: el?.tagName, id: el?.id, name: el?.getAttribute('aria-label') || el?.textContent?.trim().slice(0, 120) || '', inside_sidebar: !!el?.closest('#app-navigation') };
  });
  const tabTo = async (locator, name, maximum = 180) => {
    await locator.waitFor({ state: 'visible' });
    for (let index = 0; index <= maximum; index++) {
      if (await focused(locator)) return;
      await page.keyboard.press('Tab');
    }
    throw new Error('Keyboard could not reach ' + name + ': ' + JSON.stringify(await active()));
  };
  const screenshot = async (name, fullPage = true) => {
    const file = 'ux-' + name + '.png';
    await page.screenshot({ path: path.join(evidence, file), fullPage, animations: 'disabled' });
    report.screenshots.push(file);
  };
  const scan = async name => {
    await page.evaluate(fs.readFileSync(path.join(root, '.runtime', 'axe.min.js'), 'utf8'));
    const result = await page.evaluate(async () => window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa', 'wcag22aa'] } }));
    const violations = result.violations.map(item => ({ id: item.id, impact: item.impact, nodes: item.nodes.map(node => ({ target: node.target, summary: node.failureSummary })) }));
    report.axe.push({ screen: name, violations });
  };
  const solveResponse = async () => {
    const pending = page.waitForResponse(response => new URL(response.url()).pathname === '/api/solve' && response.request().method() === 'POST', { timeout: 45000 });
    await page.getByRole('button', { name: 'Sprawdź mój plan', exact: true }).click();
    const response = await pending;
    assert(response.ok(), 'Analysis returned HTTP ' + response.status());
    const result = await response.json();
    await page.getByRole('heading', { name: 'Przyjrzyjmy się Twoim możliwościom', exact: true }).waitFor({ timeout: 45000 });
    return { result, input: response.request().postDataJSON(), http_status: response.status() };
  };
  const edit = () => page.getByRole('button', { name: 'Zmień dane', exact: true }).click();
  try {
    await page.goto(report.base_url, { waitUntil: 'networkidle', timeout: 60000 });
    await page.getByRole('combobox', { name: 'Wybierz przykład' }).waitFor({ timeout: 30000 });
    report.frontend_assets = await page.evaluate(() => [...document.scripts].map(script => script.src).filter(Boolean));
    const menu = page.getByRole('button', { name: 'Otwórz menu', exact: true });
    const sidebar = page.locator('#app-navigation');
    assert(await sidebar.count() === 1, 'Mobile navigation has no stable controlled container');
    assert(await menu.getAttribute('aria-controls') === 'app-navigation', 'Menu button does not identify the controlled navigation');
    assert(await menu.getAttribute('aria-expanded') === 'false', 'Mobile menu starts expanded');
    assert(await sidebar.getAttribute('aria-hidden') === 'true', 'Closed mobile navigation is not hidden from accessibility APIs');
    assert(await sidebar.evaluate(el => el.inert), 'Closed mobile navigation is not inert');
    assert(await page.getByRole('navigation', { name: 'Główna nawigacja' }).count() === 0, 'Closed navigation remains in the accessible role tree');
    const cdp = await context.newCDPSession(page);
    const closedAX = await cdp.send('Accessibility.getFullAXTree');
    const activeAX = closedAX.nodes.filter(node => !node.ignored).map(node => ({ role: node.role?.value, name: node.name?.value || '' }));
    assert(!activeAX.some(node => node.role === 'navigation' && node.name === 'Główna nawigacja'), 'Closed sidebar remains an exposed Chromium AX navigation node');
    report.mobile_navigation.closed_ax_navigation_absent = true;
    report.mobile_navigation.closed_accessibility_snapshot = await page.locator('body').ariaSnapshot();
    report.mobile_navigation.closed_tab_order = [];
    for (let index = 0; index < 30; index++) {
      await page.keyboard.press('Tab');
      const state = await active();
      report.mobile_navigation.closed_tab_order.push(state);
      assert(!state.inside_sidebar, 'Tab entered the closed mobile sidebar');
    }
    report.mobile_navigation.closed_reverse_tab_order = [];
    for (let index = 0; index < 15; index++) {
      await page.keyboard.press('Shift+Tab');
      const state = await active();
      report.mobile_navigation.closed_reverse_tab_order.push(state);
      assert(!state.inside_sidebar, 'Shift+Tab entered the closed mobile sidebar');
    }
    await tabTo(menu, 'open mobile menu');
    await page.keyboard.press('Enter');
    await page.waitForFunction(() => document.querySelector('[aria-controls="app-navigation"]')?.getAttribute('aria-expanded') === 'true');
    assert(await page.getByRole('navigation', { name: 'Główna nawigacja' }).count() === 1, 'Opening the menu did not expose navigation');
    assert(!await sidebar.evaluate(el => el.inert), 'Open menu remains inert');
    await tabTo(page.getByRole('button', { name: 'Zamknij menu nawigacji', exact: true }), 'menu close control');
    report.mobile_navigation.open_focus = await active();
    await page.waitForFunction(() => Math.abs(document.querySelector('#app-navigation').getBoundingClientRect().left) < 0.5);
    await screenshot('mobile-menu-open', false);
    await page.keyboard.press('Escape');
    await page.waitForFunction(() => document.querySelector('[aria-controls="app-navigation"]')?.getAttribute('aria-expanded') === 'false');
    await page.waitForFunction(() => document.activeElement === document.querySelector('[aria-controls="app-navigation"]'));
    assert(await focused(menu), 'Escape did not restore focus to the mobile menu opener');
    assert(await sidebar.evaluate(el => el.inert), 'Escape did not restore inert navigation');
    report.mobile_navigation.escape_focus_restored = true;
    await page.keyboard.press('Tab');
    assert(!(await active()).inside_sidebar, 'First Tab after Escape entered the closed menu');
    // A desktop navigation item must not retain focus when it becomes inert
    // after crossing back into the mobile breakpoint.
    await tabTo(menu, 'open menu before breakpoint change');
    await page.keyboard.press('Enter');
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.waitForFunction(() => !document.querySelector('#app-navigation')?.inert);
    assert(await page.getByRole('navigation', { name: 'Główna nawigacja' }).count() === 1, 'Desktop breakpoint did not expose navigation');
    await tabTo(page.getByRole('button', { name: /Twój plan Godziny/ }), 'desktop plan navigation');
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForFunction(() => document.querySelector('#app-navigation')?.inert === true);
    await page.waitForFunction(() => document.activeElement === document.querySelector('[aria-controls="app-navigation"]'));
    assert(await menu.getAttribute('aria-expanded') === 'false', 'Menu open state leaked across the desktop/mobile breakpoint');
    assert(await focused(menu), 'Breakpoint change left focus inside the newly hidden navigation');
    report.mobile_navigation.breakpoint_reset = { widths: [390, 1440, 390], desktop_navigation_exposed: true, mobile_closed: true, focus_restored: true };

    await page.keyboard.press('Enter');
    await tabTo(page.getByRole('button', { name: /Zapisane plany/ }), 'saved-plans modal from mobile navigation');
    await page.keyboard.press('Enter');
    const savedDialog = page.getByRole('dialog');
    await savedDialog.getByRole('heading', { name: 'Twoje zapisane plany', exact: true }).waitFor();
    await page.keyboard.press('Escape');
    await savedDialog.waitFor({ state: 'hidden' });
    await page.waitForFunction(() => {
      const el = document.activeElement;
      return el && el !== document.body && !el.closest('[inert], [aria-hidden="true"]') && el.getClientRects().length > 0;
    });
    await page.waitForFunction(() => document.activeElement === document.querySelector('[aria-controls="app-navigation"]'));
    assert(await focused(menu), 'Closing a modal opened from the mobile sidebar did not restore its visible menu opener');
    assert(await sidebar.evaluate(el => el.inert), 'Closing the sidebar modal unexpectedly exposed the navigation');
    report.mobile_navigation.sidebar_modal_escape_focus = await active();
    await page.keyboard.press('Control+Home');
    await screenshot('mobile-menu-closed');
    await scan('mobile-menu-closed');
    await cdp.detach();
    console.log('Mobile 390: closed AX and Tab exclusion, keyboard opening and Escape focus verified');

    const empty = await solveResponse();
    assert(empty.result.status === 'UNKNOWN' && empty.result.data_status === 'needs_input', 'Empty real plan did not return UNKNOWN/needs_input');
    assert(empty.result.data_gaps.some(gap => gap.code === 'empty_period'), 'Empty real plan lacks the empty_period explanation');
    assert(await page.getByRole('heading', { name: 'Dodaj zajęcia w sprawdzanym okresie', exact: true }).count() === 1, 'Empty plan does not explain the missing activity');
    assert(await page.getByRole('button', { name: 'Spróbuj ponownie', exact: true }).count() === 0, 'Empty plan incorrectly offers retry');
    const emptyText = await page.locator('.results').innerText();
    assert(!/limit analizy|upłynął limit|przekroczono.*limit/i.test(emptyText), 'Empty plan is incorrectly explained as an analysis limit');
    assert(!emptyText.includes('Obliczenia bez rozstrzygnięcia'), 'Empty plan shows redundant undecided-calculation badge');
    report.real_api.push({ case: 'empty-plan', http_status: empty.http_status, status: empty.result.status, data_status: empty.result.data_status, gaps: empty.result.data_gaps, retry_present: false, limit_claim_present: false });
    await screenshot('empty-needs-input');
    await scan('empty-needs-input');

    await edit();
    await page.setViewportSize({ width: 1440, height: 1000 });
    const examplesResponse = await page.evaluate(async () => {
      const response = await fetch('/api/examples', { credentials: 'same-origin' });
      return { ok: response.ok, status: response.status, data: await response.json() };
    });
    assert(examplesResponse.ok, 'Could not read the served original examples for comparison');
    const originalExample = examplesResponse.data.items.find(item => item.id === 'single-parent');
    assert(originalExample?.scenario, 'The served single-parent example is missing');
    await page.getByRole('combobox', { name: 'Wybierz przykład' }).selectOption('single-parent');
    const replaceExample = page.getByRole('button', { name: 'Otwórz przykład', exact: true });
    if (await replaceExample.isVisible()) await replaceExample.click();
    const workPlace = page.getByLabel('Miejsce (krótka etykieta)');
    await workPlace.waitFor();
    assert(await workPlace.inputValue() === 'praca', 'Opening the example left the technical work location in the form');
    await page.getByRole('tab', { name: /^Opieka/ }).click();
    assert(await page.getByLabel('Etykieta podopiecznego', { exact: true }).inputValue() === 'dziecko 1', 'Dependent reference was not localized');
    assert(await page.getByLabel('Miejsce (etykieta do tras)', { exact: true }).inputValue() === 'miejsce opieki', 'Care resource location was not localized');
    await page.getByText('Zajętość opiekuna i zgodność opieki', { exact: true }).click();
    assert(await page.getByLabel('Dopuszczeni podopieczni').inputValue() === 'dziecko 1', 'Resource compatibility still points to the old dependent label');
    await screenshot('polish-example-care');
    await page.getByRole('tab', { name: /^Dojazdy/ }).click();
    assert(await page.getByLabel('Etykieta miejsca domowego', { exact: true }).inputValue() === 'dom', 'Home location was not localized');
    const origins = await page.getByLabel('Z miejsca', { exact: true }).evaluateAll(inputs => inputs.map(input => input.value));
    const destinations = await page.getByLabel('Do miejsca', { exact: true }).evaluateAll(inputs => inputs.map(input => input.value));
    assert(JSON.stringify(origins) === JSON.stringify(['dom', 'miejsce opieki', 'praca', 'miejsce opieki']), 'Route origins do not follow the Polish place references');
    assert(JSON.stringify(destinations) === JSON.stringify(['miejsce opieki', 'praca', 'miejsce opieki', 'dom']), 'Route destinations do not follow the Polish place references');
    await screenshot('polish-example-travel');
    const translatedExample = await solveResponse();
    assert(translatedExample.result.status === 'OPTIMAL', 'The translated example failed to solve');
    assert(translatedExample.result.alternatives.every(item => item.validation.valid), 'The translated example failed independent validation');
    const originalInput = originalExample.scenario;
    const translatedInput = translatedExample.input;
    assert(translatedInput.home_location === 'dom' && originalInput.home_location === 'home', 'Example translation did not stay separate from the original served data');
    assert(translatedInput.activities[0].id === originalInput.activities[0].id && translatedInput.activities[0].kind === originalInput.activities[0].kind, 'Example localization changed activity IDs or enums');
    assert(JSON.stringify(translatedInput.care_resources.map(item => item.id)) === JSON.stringify(originalInput.care_resources.map(item => item.id)), 'Example localization changed resource IDs');
    assert(JSON.stringify(translatedInput.travel_legs.map(item => item.id)) === JSON.stringify(originalInput.travel_legs.map(item => item.id)), 'Example localization changed route IDs');
    const originalResponse = await page.evaluate(async scenario => {
      const session = await fetch('/api/session', { credentials: 'same-origin' });
      if (!session.ok) throw new Error('Could not obtain the test session for the original-reference analysis');
      const testSession = await session.json();
      const response = await fetch('/api/solve', { method: 'POST', credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': testSession.csrf_token, 'Idempotency-Key': crypto.randomUUID() }, body: JSON.stringify(scenario) });
      return { ok: response.ok, status: response.status, data: await response.json() };
    }, originalInput);
    assert(originalResponse.ok, 'Original-reference analysis returned HTTP ' + originalResponse.status);
    const originalResult = originalResponse.data;
    const ordered = items => items.sort((a, b) => JSON.stringify(a).localeCompare(JSON.stringify(b)));
    const conflictFacts = items => ordered((items || []).map(item => ({ code: item.code, date: item.date, minutes: item.minutes, activity_id: item.activity_id, need_id: item.need_id, resource_id: item.resource_id })));
    const scheduleFacts = items => ordered((items || []).map(item => ({ kind: item.kind, start: item.start, end: item.end,
      start_minute: item.start_minute, end_minute: item.end_minute, date: item.date, activity_id: item.activity_id, need_id: item.need_id,
      resource_id: item.resource_id, leg_id: item.leg_id, arrangement_id: item.arrangement_id, paid_minutes: item.paid_minutes,
      dependent_id: item.dependent_id === 'dziecko 1' ? 'child-1' : item.dependent_id })));
    const semanticResult = result => ({ status: result.status, data_status: result.data_status, conflicts: conflictFacts(result.conflicts),
      baseline: { status: result.baseline?.status, conflicts: conflictFacts(result.baseline?.conflicts), schedule: scheduleFacts(result.baseline?.schedule) },
      alternatives: result.alternatives.map(item => ({ id: item.id, solver_status: item.solver_status, status: item.status, metrics: item.metrics,
        schedule: scheduleFacts(item.schedule), stages: item.proof.stages, validated: item.validation.valid })) });
    assert(JSON.stringify(semanticResult(translatedExample.result)) === JSON.stringify(semanticResult(originalResult)), 'Polish labels changed solver status, conflict facts, optimal metrics, proof stages or schedule times/IDs');
    report.example_localization = { id: 'single-parent', original_http_status: originalResponse.status, translated_http_status: translatedExample.http_status,
      original_home: originalInput.home_location, displayed_home: translatedInput.home_location, displayed_work: translatedInput.activities[0].location,
      displayed_care: translatedInput.care_resources[0].location, displayed_dependent: translatedInput.care_needs[0].dependent_id,
      origins, destinations, semantic_result_identical: true, original_status: originalResult.status, translated_status: translatedExample.result.status,
      alternatives: translatedExample.result.alternatives.map(item => ({ id: item.id, metrics: item.metrics, events: item.schedule.length, validation: item.validation.valid })) };
    report.real_api.push({ case: 'polish-example', http_status: translatedExample.http_status, status: translatedExample.result.status, data_status: translatedExample.result.data_status, alternatives: translatedExample.result.alternatives.length, all_validated: true },
      { case: 'original-example-reference', request_method: 'Browser fetch with current test-session CSRF, without changing UI state', http_status: originalResponse.status, status: originalResult.status, equivalent_to_polish_example: true });
    report.direct_api_analyses = 1;
    await screenshot('polish-example-result');
    await edit();
    await page.getByRole('button', { name: 'Własny plan', exact: true }).click();
    await page.getByRole('button', { name: 'Otwórz pusty formularz', exact: true }).click();
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    const planTitle = 'Regresja UX: zachowanie danych';
    const offerTitle = 'Oferta własna: praca w domu';
    await page.getByLabel('Nazwa Twojego planu', { exact: true }).fill(planTitle);
    await page.getByLabel('Sprawdzam od', { exact: true }).fill('2026-10-05');
    await page.getByLabel('Sprawdzam do', { exact: true }).fill('2026-10-09');
    const requiredHours = page.locator('#editor-minimum_paid_minutes');
    await requiredHours.fill('-1');
    const requestsBeforeNegative = realSolveRequests;
    await page.getByRole('button', { name: 'Sprawdź mój plan', exact: true }).click();
    const numericSummary = page.locator('#editor-validation-summary');
    await numericSummary.waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.activeElement?.id === 'editor-validation-summary');
    assert(await requiredHours.getAttribute('aria-invalid') === 'true', 'Negative required hours lack aria-invalid');
    assert((await requiredHours.getAttribute('aria-describedby') || '').split(/\s+/).includes('editor-minimum_paid_minutes-error'), 'Negative hours lack an associated field error');
    const numericError = await page.locator('#editor-minimum_paid_minutes-error').innerText();
    assert(numericError === 'Podaj co najmniej 0 godzin wymaganego płatnego czasu pracy.', 'Required hours do not explain the minimum in Polish');
    assert(realSolveRequests === requestsBeforeNegative, 'Negative required hours reached the API');
    await screenshot('negative-required-hours');
    await tabTo(numericSummary.locator('button, a').first(), 'required-hours correction link');
    await page.keyboard.press('Enter');
    assert(await focused(requiredHours), 'The minimum-hours summary does not lead to its field');
    await page.keyboard.press('Control+A');
    await page.keyboard.insertText('0');
    await page.keyboard.press('Tab');
    await page.waitForFunction(() => document.querySelector('#editor-minimum_paid_minutes')?.getAttribute('aria-invalid') !== 'true');
    assert(await page.locator('#editor-minimum_paid_minutes-error').count() === 0, 'Correcting required hours did not clear the inline error');
    const budget = page.locator('#editor-budget_grosze');
    assert(await budget.inputValue() === '', 'The new plan unexpectedly fills an unknown budget');
    await budget.fill('-1');
    await page.getByRole('button', { name: 'Sprawdź mój plan', exact: true }).click();
    await page.waitForFunction(() => document.activeElement?.id === 'editor-validation-summary');
    assert(await budget.getAttribute('aria-invalid') === 'true', 'Negative budget lacks aria-invalid');
    const budgetError = await page.locator('#editor-budget_grosze-error').innerText();
    assert(/(?:co najmniej|nie mniejszy niż) 0\s*zł/i.test(budgetError), 'Negative budget lacks a Polish minimum-zero explanation');
    await budget.fill('');
    await page.keyboard.press('Tab');
    await page.waitForFunction(() => document.querySelector('#editor-budget_grosze')?.getAttribute('aria-invalid') !== 'true');
    assert(realSolveRequests === requestsBeforeNegative, 'An invalid numeric goal reached the API');
    report.numeric_validation = { invalid_required_hours: -1, message: numericError, aria_invalid: true, summary_focus: true, corrected_required_hours: 0,
      invalid_budget: -1, budget_message: budgetError, cleared_budget_valid: true, invalid_api_requests: 0 };
    await page.getByRole('button', { name: 'Dodaj ofertę lub zajęcia', exact: true }).click();
    await page.getByLabel('Nazwa oferty lub zajęć', { exact: true }).fill(offerTitle);
    await page.getByLabel('Miejsce (krótka etykieta)').fill('dom');
    await page.getByLabel('Początek zajęć', { exact: true }).fill('09:00');
    const dates = page.locator('#editor-activities-0-dates');
    await dates.fill('2026-99-99');
    const requestsBeforeInvalid = realSolveRequests;
    await page.getByRole('button', { name: 'Sprawdź mój plan', exact: true }).click();
    const summary = page.locator('#editor-validation-summary');
    await summary.waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.activeElement?.id === 'editor-validation-summary');
    assert(await summary.getAttribute('role') === 'alert', 'Validation summary is not announced as an alert');
    assert(await summary.getAttribute('tabindex') === '-1', 'Validation summary has no deliberate focus target');
    assert(await dates.getAttribute('aria-invalid') === 'true', 'Invalid date field lacks aria-invalid');
    const describedBy = (await dates.getAttribute('aria-describedby') || '').split(/\s+/);
    assert(describedBy.includes('editor-activities-0-dates-error'), 'Invalid date field does not reference its inline error');
    const fieldError = await page.locator('#editor-activities-0-dates-error').innerText();
    assert(/dat|RRRR/i.test(fieldError) && !/input should|validation error|invalid date/i.test(fieldError), 'Date error is not a Polish field explanation: ' + fieldError);
    assert(realSolveRequests === requestsBeforeInvalid, 'Invalid date was sent to the API');
    assert(await dates.inputValue() === '2026-99-99', 'Invalid value was silently discarded');
    assert(await page.getByLabel('Nazwa Twojego planu', { exact: true }).inputValue() === planTitle, 'Plan title was lost after validation');
    assert(await page.getByLabel('Nazwa oferty lub zajęć', { exact: true }).inputValue() === offerTitle, 'Offer title was lost after validation');
    report.date_validation = { invalid_value: '2026-99-99', field_error: fieldError, aria_invalid: true, aria_describedby: describedBy, summary_focus: true, invalid_api_requests: realSolveRequests - requestsBeforeInvalid };
    await screenshot('invalid-date');
    await scan('invalid-date');
    const errorLink = summary.locator('button, a').first();
    await tabTo(errorLink, 'validation summary correction link');
    await page.keyboard.press('Enter');
    assert(await focused(dates), 'Validation summary correction did not focus the invalid date');
    await page.keyboard.press('Control+A');
    await page.keyboard.type('2026-10-05, 2026-10-06', { delay: 15 });
    assert(await dates.inputValue() === '2026-10-05, 2026-10-06', 'Typing a comma-separated list lost a separator or date before blur');
    await page.keyboard.press('Tab');
    assert(await dates.inputValue() === '2026-10-05, 2026-10-06', 'Normalizing the date list on blur lost a date');
    const corrected = await solveResponse();
    assert(corrected.result.status === 'OPTIMAL' && corrected.result.data_status === 'complete', 'Corrected real plan did not solve optimally');
    assert(corrected.result.alternatives.length > 0 && corrected.result.alternatives.every(item => item.validation.valid), 'Corrected real plan has no independently validated alternative');
    assert(corrected.input.title === planTitle && corrected.input.activities[0].label === offerTitle, 'Correcting the date lost the existing offer data');
    assert(corrected.input.activities[0].dates.join(',') === '2026-10-05,2026-10-06' && corrected.input.activities[0].start === '09:00', 'Both corrected dates or existing start failed to reach the API');
    assert(corrected.input.minimum_paid_minutes === 0 && corrected.input.budget_grosze === null, 'Numeric correction changed zero required time or the unknown-budget semantics');
    for (const day of ['2026-10-05', '2026-10-06']) assert(corrected.result.alternatives[0].schedule.some(event => event.kind === 'work' && event.start.startsWith(day + 'T09:00')), 'Corrected real schedule is missing the dated work shift: ' + day);
    await page.locator('.alternative').first().waitFor();
    report.real_api.push({ case: 'corrected-offer', http_status: corrected.http_status, status: corrected.result.status, data_status: corrected.result.data_status, alternatives: corrected.result.alternatives.length, all_validated: true, retained_title: corrected.input.title, retained_offer: corrected.input.activities[0].label, dates: corrected.input.activities[0].dates, start: corrected.input.activities[0].start });
    report.date_validation.corrected_without_data_loss = true;
    report.date_validation.character_by_character_date_list = '2026-10-05, 2026-10-06';
    await screenshot('corrected-result');
    await scan('corrected-result');
    console.log('Real API: empty-plan explanation and invalid-date correction with data preservation verified');

    phase = 'mock-status-rendering';
    let mockedResult;
    let interceptCount = 0;
    await page.route('**/api/solve', async route => {
      assert(route.request().method() === 'POST', 'Unexpected intercepted request method');
      interceptCount++;
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(mockedResult) });
    });
    const common = { status: 'UNKNOWN', data_status: 'complete', alternatives: [], conflicts: [], data_gaps: [], warnings: [], baseline: { status: 'UNKNOWN', conflicts: [], schedule: [] }, checked_period: { start: '2026-10-05', end: '2026-10-09' } };
    const cases = [
      { name: 'unknown-neutral', value: {}, heading: 'Potrzeba kolejnego sprawdzenia', retry: true, exactText: 'Obliczenia zakończyły się bez rozstrzygnięcia. Nie potwierdza to ani wykonalności planu, ani braku rozwiązania. Możesz spróbować ponownie.', noLimit: true, source: 'api/solver/engine.py: UNKNOWN with complete data and no timeout warning' },
      { name: 'unknown-limit-warning', value: { warnings: ['Budowa modelu przekroczyła wspólny limit analizy'] }, heading: 'Potrzeba kolejnego sprawdzenia', retry: true, exactText: 'Budowa modelu przekroczyła wspólny limit analizy', source: 'api/solver/engine.py: caught TimeoutError appears in warnings' },
      { name: 'unknown-limit-message', value: { message: 'Upłynął limit całej analizy. To nie oznacza braku rozwiązania.' }, heading: 'Potrzeba kolejnego sprawdzenia', retry: true, exactText: 'Upłynął limit całej analizy. To nie oznacza braku rozwiązania.', source: 'api/worker.py: process deadline response message' },
      { name: 'needs-input', value: { data_status: 'needs_input', data_gaps: [{ code: 'missing_route', message: 'Brak sprawdzonej trasy do miejsca pracy.' }] }, heading: 'Uzupełnij dane planu', retry: false, exactText: 'Brak sprawdzonej trasy do miejsca pracy.', noLimit: true, source: 'api/worker.py: incomplete route hydration; api/solver/engine.py: required facts absent' },
      { name: 'stale', value: { data_status: 'stale', data_gaps: [{ code: 'stale_source', message: 'Godziny opieki wymagają aktualizacji.' }] }, heading: 'Zaktualizuj dane planu', retry: false, exactText: 'Godziny opieki wymagają aktualizacji.', noLimit: true, source: 'api/solver/engine.py: stale_source' },
      { name: 'infeasible', value: { status: 'INFEASIBLE', conflicts: [{ code: 'budget', message: 'Budżet jest niższy od kosztu wszystkich dopuszczonych wariantów.' }] }, heading: 'Nie znaleźliśmy wykonalnego wariantu', retry: false, exactText: 'W podanych danych i dozwolonym zakresie zmian nie udało się połączyć wszystkich warunków.', noLimit: true, source: 'api/solver/engine.py: proven finite-domain infeasibility' },
      { name: 'model-invalid', value: { status: 'MODEL_INVALID' }, heading: 'Nie udało się potwierdzić wyniku', retry: false, noLimit: true, source: 'api/solver/engine.py: invalid model or independent validation rejects solution' }
    ];
    for (const fixture of cases) {
      await edit();
      mockedResult = { ...common, ...fixture.value };
      const before = interceptCount;
      const response = await solveResponse();
      assert(interceptCount === before + 1, 'Status case did not use exactly one declared mocked response');
      await page.getByRole('heading', { name: fixture.heading, exact: true }).waitFor();
      const text = await page.locator('.results').innerText();
      const retryCount = await page.getByRole('button', { name: 'Spróbuj ponownie', exact: true }).count();
      assert(retryCount === Number(fixture.retry), 'Incorrect retry action for ' + fixture.name);
      if (fixture.exactText) assert(text.includes(fixture.exactText), 'Source explanation missing in ' + fixture.name);
      if (fixture.noLimit) assert(!/limit analizy|limit całej analizy|przekroczyła wspólny limit/i.test(text), 'False timeout claim in ' + fixture.name);
      if (fixture.name === 'unknown-neutral' || fixture.name === 'model-invalid') assert(!text.includes('Nie znaleźliśmy wykonalnego wariantu'), 'Indecision or model error became an impossibility claim');
      if (['needs-input', 'stale'].includes(fixture.name)) assert(await page.getByRole('button', { name: 'Uzupełnij plan', exact: true }).count() === 1, 'Missing data does not offer correction');
      report.mocked_responses.push({ case: fixture.name, source_shape: fixture.source, status: response.result.status, data_status: response.result.data_status, heading: fixture.heading, retry_present: Boolean(retryCount), displayed_text: text });
      if (['unknown-neutral', 'unknown-limit-warning', 'infeasible'].includes(fixture.name)) await screenshot(fixture.name);
    }
    console.log('All seven explicitly mocked status rendering cases passed');

    // A failed save must keep its correction path inside the active modal.
    // Only the first response is mocked; retry and deletion exercise the API.
    let saveAttempts = 0;
    const saveInputs = [];
    const saveError = 'Zbyt wiele żądań. Spróbuj za minutę.';
    await page.route('**/api/plans', async route => {
      if (route.request().method() !== 'POST') return route.continue();
      saveAttempts++;
      saveInputs.push(route.request().postDataJSON());
      if (saveAttempts === 1) return route.fulfill({ status: 429, contentType: 'application/json', headers: { 'Retry-After': '1' }, body: JSON.stringify({ detail: saveError }) });
      await route.continue();
    });
    await page.getByRole('button', { name: 'Zapisz plan', exact: true }).click();
    const saveDialog = page.getByRole('dialog');
    await saveDialog.getByRole('heading', { name: 'Chcesz wrócić do swojego planu?', exact: true }).waitFor();
    const consent = saveDialog.getByRole('checkbox', { name: 'Chcę zapisać te dane i rozumiem sposób dostępu.' });
    await consent.check();
    const submitSave = saveDialog.getByRole('button', { name: 'Zapisz mój plan', exact: true });
    expectedSave429 = true;
    const rejectedSave = page.waitForResponse(response => new URL(response.url()).pathname === '/api/plans' && response.request().method() === 'POST');
    await submitSave.click();
    assert((await rejectedSave).status() === 429, 'The intended first-save rejection was not exercised');
    const modalAlert = saveDialog.getByRole('alert');
    await modalAlert.waitFor({ state: 'visible' });
    await page.waitForFunction(() => document.activeElement?.getAttribute('role') === 'alert' && !!document.activeElement?.closest('[role="dialog"]'));
    assert(await focused(modalAlert), 'Save failure did not move focus to its modal explanation');
    assert(await page.getByRole('alert').count() === 1, 'Save failure was duplicated outside the active modal');
    assert((await modalAlert.innerText()).includes(saveError), 'Save error is not explained inside the active modal');
    assert(await consent.isChecked(), 'A failed save discarded explicit consent');
    assert(await submitSave.isEnabled(), 'A failed save permanently disabled retry');
    const alertStyle = await modalAlert.evaluate(el => ({ visible: el.getClientRects().length > 0, hiddenAncestor: !!el.closest('[inert], [aria-hidden="true"]') }));
    assert(alertStyle.visible && !alertStyle.hiddenAncestor, 'Save error is visually or semantically hidden beneath the modal');
    report.save_retry = { first_response: 'mocked-429', error: await modalAlert.innerText(), inside_modal: true, alert_focused: true, consent_preserved: true, retry_enabled: true };
    await screenshot('save-error-modal', false);
    await scan('save-error-modal');
    expectedSave429 = false;
    const acceptedSave = page.waitForResponse(response => new URL(response.url()).pathname === '/api/plans' && response.request().method() === 'POST', { timeout: 45000 });
    await submitSave.click();
    const savedResponse = await acceptedSave;
    assert(savedResponse.ok(), 'Real retry failed with HTTP ' + savedResponse.status());
    const savedPlan = await savedResponse.json();
    assert(saveAttempts === 2 && JSON.stringify(saveInputs[0]) === JSON.stringify(saveInputs[1]), 'Retry changed or duplicated the save payload');
    assert(savedPlan.scenario.title === planTitle, 'The saved plan is not this test\'s synthetic input');
    report.save_retry.real_retry_http_status = savedResponse.status();
    report.save_retry.same_payload = true;
    await saveDialog.waitFor({ state: 'hidden', timeout: 45000 });
    await page.locator('.session-status').filter({ hasText: 'Zapisany · wersja 1' }).waitFor();
    await page.getByRole('button', { name: /Zapisane plany/ }).click();
    await page.getByRole('heading', { name: 'Twoje zapisane plany', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Bieżący plan', exact: true }).click();
    await page.getByRole('heading', { name: 'Kopia, historia i usunięcie', exact: true }).waitFor();
    await page.getByRole('button', { name: 'Usuń bieżący plan', exact: true }).click();
    await page.getByRole('heading', { name: 'Usunąć plan i jego historię?', exact: true }).waitFor();
    const deletion = page.waitForResponse(response => new URL(response.url()).pathname === '/api/plans/' + savedPlan.id && response.request().method() === 'DELETE');
    await page.getByRole('button', { name: 'Usuń plan i powiązane dane', exact: true }).click();
    assert((await deletion).ok(), 'Deletion of this test\'s saved plan failed');
    await page.getByRole('dialog').waitFor({ state: 'hidden' });
    await page.locator('.session-status').filter({ hasText: 'Bez zapisu' }).waitFor();
    await page.getByRole('button', { name: /Zapisane plany/ }).click();
    const finalSavedList = page.getByRole('dialog');
    await finalSavedList.getByRole('heading', { name: 'Twoje zapisane plany', exact: true }).waitFor();
    assert(await finalSavedList.getByText(planTitle, { exact: true }).count() === 0, 'Deleted synthetic plan remains in the session list');
    assert((await finalSavedList.innerText()).includes('Nie masz jeszcze zapisanych planów'), 'Fresh test session still has a saved plan after deletion');
    await page.keyboard.press('Escape');
    await finalSavedList.waitFor({ state: 'hidden' });
    report.save_retry.synthetic_plan_deleted = true;
    console.log('Simulated save429 stays in modal; real retry preserved input and the test plan was deleted');
    assert(realSolveRequests === 4 && report.direct_api_analyses === 1, 'Expected three UI analyses and one original-reference API analysis before mocked status cases');
    assert(!report.axe.some(scan => scan.violations.some(item => ['critical', 'serious'].includes(item.impact))), 'Serious accessibility violations occurred; see axe results');
    assert(report.page_errors.length === 0, 'JavaScript page errors occurred');
    assert(report.console_errors.length === 0, 'Browser console errors occurred');
    report.status = 'passed';
    fs.rmSync(path.join(evidence, 'ux-regression-failure.png'), { force: true });
  } catch (error) {
    report.status = 'failed';
    report.error = (error.stack || String(error)).replace(/^(\s*-?\s*(?:cookie|authorization|x-csrf-token):).*$/gim, '$1 [redacted]');
    report.focus_at_failure = await active().catch(() => null);
    await screenshot('regression-failure').catch(() => {});
    process.exitCode = 1;
  } finally {
    report.finished_at = new Date().toISOString();
    report.real_solve_requests = realSolveRequests;
    fs.writeFileSync(path.join(evidence, 'ux-regression.json'), JSON.stringify(report, null, 2));
    console.log(JSON.stringify({ status: report.status, real_api: report.real_api.map(item => item.case), mocks: report.mocked_responses.map(item => item.case), error: report.error }));
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
