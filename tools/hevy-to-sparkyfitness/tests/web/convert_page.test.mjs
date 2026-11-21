// Browser tests for the easy, in-browser version (site/index.html). The page runs
// the same Python script with Pyodide, so its downloads must be byte-identical
// to the command line's expected files in tests/expected/.
import { mkdtemp, readFile, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import assert from 'node:assert/strict';

export default async function ({ browser, baseUrl, toolDir }) {
  const fixtures = path.join(toolDir, 'tests', 'fixtures');
  const expected = path.join(toolDir, 'tests', 'expected');
  const pageUrl = `${baseUrl}hevy-to-sparkyfitness/`;

  async function freshPage() {
    const context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    const errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('requestfailed', (r) => errors.push(`request failed: ${r.url()}`));
    page.on('request', (r) => {
      if (!r.url().startsWith(baseUrl) && !r.url().startsWith('blob:') && !r.url().startsWith('data:')) {
        errors.push(`third-party request: ${r.url()}`);
      }
    });
    await page.goto(pageUrl);
    return { page, context, errors };
  }

  async function open(page, fixture) {
    await page.setInputFiles('#file-input', path.join(fixtures, fixture));
    await page.waitForFunction(() => {
      const s = document.getElementById('file-status').textContent;
      return s.startsWith('✓') || !document.getElementById('file-error').hidden;
    }, null, { timeout: 120000 });
  }

  async function convertAndRead(page) {
    await page.click('#convert');
    await page.waitForFunction(() => !document.getElementById('result').hidden ||
      !document.getElementById('convert-error').hidden, null, { timeout: 60000 });
    const error = await page.textContent('#convert-error');
    assert.equal(await page.isHidden('#convert-error'), true, `conversion failed: ${error}`);
    const summary = await page.textContent('#summary');
    assert.doesNotMatch(summary, / --[a-z]/, `the summary mentions a command-line option: ${summary}`);
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('#download')]);
    return { name: download.suggestedFilename(), bytes: await readFile(await download.path()) };
  }

  async function check(fixture, expectedName, setup) {
    const { page, context, errors } = await freshPage();
    try {
      if (setup?.before) await setup.before(page);
      await open(page, fixture);
      if (setup?.after) await setup.after(page);
      const { name, bytes } = await convertAndRead(page);
      assert.equal(name, fixture.replace(/\.csv$/, '') + '_sparkyfitness.csv');
      const want = await readFile(path.join(expected, expectedName));
      assert.ok(bytes.equals(want), `${fixture}: download differs from expected/${expectedName}`);
      assert.deepEqual(errors, []);
    } finally {
      await context.close();
    }
  }

  // Same files as the command line, for several formats and both unit settings.
  await check('app_en_lbs_miles.csv', 'app_en_lbs_miles__kg_km.csv');
  await check('localized_assisted.csv', 'localized_assisted__kg_km.csv');
  await check('utf16_tab.csv', 'utf16_tab__kg_km.csv');
  await check('excel_semicolon_decimal_comma.csv', 'excel_semicolon_decimal_comma__kg_km.csv');
  await check('app_en_kg_km.csv', 'app_en_kg_km__lbs_miles.csv', {
    after: async (page) => { await page.check('#w-lbs', { force: true }); await page.check('#d-miles', { force: true }); },
  });
  await check('localized_assisted.csv', 'localized_assisted__assisted_positive.csv', {
    after: async (page) => {
      await page.click('details.advanced > summary');
      await page.check('#assisted-positive');
    },
  });

  // Exercise table: the visual table gives the same file as --exercise-map.
  await check('exercise_table_export.csv', 'exercise_table__kg_km.csv', {
    after: async (page) => {
      await page.click('#paste-box > summary');
      await page.fill('#user-names', 'Pull-up\nBarbell Bench Press\n');
      const targets = {
        'Pull Up': 'Pull-up',
        'Pull Up (Assisted)': 'Pull-up',
        'Bench Press (Barbell)': 'Barbell Bench Press',
        'Press Banca (Barra)': 'Barbell Bench Press',
      };
      for (const [hevy, target] of Object.entries(targets)) {
        const input = page.getByLabel(`SparkyFitness name for ${hevy}`, { exact: true });
        await input.fill(target);
        await input.blur();
      }
      const hints = await page.locator('.hint.ok').count();
      assert.equal(hints, 4, 'every chosen name is recognised as one of the pasted names');
    },
  });

  // Look-alike exercises: joined with one click, from either row, the page
  // gives the same file as the command line with a table that joins them.
  await check('similar_names.csv', 'similar_names_joined__kg_km.csv', {
    after: async (page) => {
      const hintOf = async (hevy) => page.locator(`#${await page.getByLabel(`SparkyFitness name for ${hevy}`,
        { exact: true }).getAttribute('aria-describedby')}`);
      const pullUp = await hintOf('Pull-up');
      assert.match(await pullUp.textContent(), /Looks like the same exercise as “Pull Up”/);
      await pullUp.getByRole('button', { name: 'Join with “Pull Up”' }).click();
      assert.equal(await page.getByLabel('SparkyFitness name for Pull-up', { exact: true }).inputValue(), 'Pull Up');
      assert.match(await (await hintOf('Pull Up')).textContent(), /Joined with “Pull-up” from Hevy/);
      assert.equal(await page.getByLabel('SparkyFitness name for Pull-up', { exact: true })
        .evaluate((el) => el === document.activeElement), true, 'focus stays in the row');

      const bench = await hintOf('Bench Press (Barbell)');
      await bench.getByRole('button', { name: 'Join “Barbell Bench Press” with this one' }).click();
      assert.equal(await page.getByLabel('SparkyFitness name for Barbell Bench Press', { exact: true }).inputValue(),
        'Bench Press (Barbell)');
      assert.doesNotMatch(await page.textContent('#names-tools'), /Looks like the same exercise/);
      assert.match(await page.textContent('#names-summary'), /4 joined into 2/);
      assert.equal(await (await hintOf('Pull Up (Assisted)')).locator('.join').count(), 0,
        'an assisted variant is not the same exercise');
    },
  });

  // Before joining, the summary says how to join them on this page.
  {
    const { page, context } = await freshPage();
    try {
      await open(page, 'similar_names.csv');
      await page.click('#convert');
      await page.waitForSelector('#result:not([hidden])');
      const summary = await page.textContent('#summary');
      assert.match(summary, /look like the same exercise but stay separate exercises: Barbell Bench Press = Bench Press \(Barbell\); Pull Up = Pull-up\. To join them, give each group the same SparkyFitness name in step 3/);
      assert.doesNotMatch(summary, /sparkyfitness_name|exercise table|--/);
    } finally {
      await context.close();
    }
  }

  // Ambiguous Excel dates: the page asks for the date order, then works.
  {
    const { page, context } = await freshPage();
    try {
      await open(page, 'excel_ambiguous_dates.csv');
      assert.match(await page.textContent('#file-error'), /date order/i);
      assert.equal(await page.isDisabled('#convert'), true);
      await page.selectOption('#date-order', 'dmy');
      await page.waitForFunction(() => document.getElementById('file-status').textContent.startsWith('✓'));
      assert.equal(await page.isDisabled('#convert'), false);
    } finally {
      await context.close();
    }
  }

  // Suggestions, capital-letter check, table download and the remembered units.
  {
    const { page, context } = await freshPage();
    try {
      await page.check('#w-lbs', { force: true });
      await open(page, 'app_en_kg_km.csv');
      const benchHint = page.locator('tr', { hasText: 'Bench Press (Barbell)' }).locator('.hint');
      assert.match(await benchHint.textContent(), /Use “Barbell Bench Press - Medium Grip”/);
      await benchHint.locator('button').click();
      assert.equal(await page.getByLabel('SparkyFitness name for Bench Press (Barbell)', { exact: true }).inputValue(),
        'Barbell Bench Press - Medium Grip');

      await page.click('#paste-box > summary');
      await page.fill('#user-names', 'Pull-up\n');
      const pullUp = page.getByLabel('SparkyFitness name for Pull Up', { exact: true });
      await pullUp.fill('pull-UP');
      await pullUp.blur();
      const pullHint = page.locator('tr', { hasText: '8 sets' }).first();
      assert.ok(pullHint, 'row exists');
      const hint = page.locator(`#${await pullUp.getAttribute('aria-describedby')}`);
      assert.match(await hint.textContent(), /Capitals differ/);
      await hint.locator('button').click();
      assert.equal(await pullUp.inputValue(), 'Pull-up');

      await page.click('text=Save these names for later');
      const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save-table')]);
      assert.equal(download.suggestedFilename(), 'app_en_kg_km_exercises.csv');
      const table = (await readFile(await download.path())).toString('utf8');
      assert.ok(table.startsWith('﻿hevy_name,sparkyfitness_name,sets,last_done,kind\r\n'));
      assert.match(table, /\r\nPull Up,Pull-up,2,2026-11-05,bodyweight\r\n/);

      await page.reload();
      assert.equal(await page.isChecked('#w-lbs'), true, 'units are remembered');
      assert.equal(await page.inputValue('#user-names'), 'Pull-up\n', 'pasted names are remembered');
    } finally {
      await context.close();
    }
  }

  // A file made before a name changed is never offered; names loaded for
  // exercises not in this export are kept; an exact Free Exercise DB name
  // gets no other suggestion.
  {
    const { page, context } = await freshPage();
    try {
      await open(page, 'app_en_kg_km.csv');
      await page.click('#convert');
      await page.waitForSelector('#result:not([hidden])');
      const pull = page.getByLabel('SparkyFitness name for Pull Up', { exact: true });
      await pull.fill('Pull-up');
      assert.equal(await page.isHidden('#result'), true, 'an out-of-date download is still offered');

      const plankHint = page.locator(`#${await page.getByLabel('SparkyFitness name for Plank', { exact: true }).getAttribute('aria-describedby')}`);
      assert.equal(await plankHint.locator('button').count(), 0, 'Plank is a Free Exercise DB name: no suggestion');

      const dir = await mkdtemp(path.join(tmpdir(), 'hevy-web-'));
      const table = path.join(dir, 'old_table.csv');
      await writeFile(table, 'hevy_name,sparkyfitness_name,sets,last_done,kind\r\nRunning,Run,1,2026-11-05,cardio\r\nOld Hevy Exercise,Sparky Old,0,,\r\n');
      await page.click('text=Save these names for later');
      await page.setInputFiles('#load-table', table);
      await page.waitForFunction(() => /loaded 1 names/.test(document.getElementById('names-summary').textContent));
      assert.equal(await page.getByLabel('SparkyFitness name for Running', { exact: true }).inputValue(), 'Run');
      const [download] = await Promise.all([page.waitForEvent('download'), page.click('#save-table')]);
      const saved = (await readFile(await download.path())).toString('utf8');
      assert.match(saved, /\r\nOld Hevy Exercise,Sparky Old,0,,\r\n/, 'a loaded name for another export was dropped');
    } finally {
      await context.close();
    }
  }

  // If the engine fails to download, the page says so and the next try works.
  {
    const context = await browser.newContext({ acceptDownloads: true });
    const page = await context.newPage();
    try {
      let block = true;
      await page.route('**/pyodide.asm.wasm', (route) => (block ? route.abort() : route.continue()));
      await page.goto(pageUrl);
      await open(page, 'app_en_kg_km.csv');
      assert.equal(await page.isVisible('#file-error'), true, 'no error after a failed engine download');
      assert.match(await page.textContent('#file-error'), /could not start/);
      block = false;
      await page.setInputFiles('#file-input', path.join(fixtures, 'app_en_lbs_miles.csv'));
      await page.waitForFunction(() => document.getElementById('file-status').textContent.startsWith('✓'), null, { timeout: 120000 });
    } finally {
      await context.close();
    }
  }
}
