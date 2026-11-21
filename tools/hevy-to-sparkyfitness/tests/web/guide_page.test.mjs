// Browser tests for the command-line guide (site/command-line/): the setup
// panel rewrites every command, commands wrap instead of being cut off, and
// the Copy button copies the plain command and gets its label back.
import assert from 'node:assert/strict';

export default async function ({ browser, baseUrl }) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
  await context.grantPermissions(['clipboard-read', 'clipboard-write'], { origin: new URL(baseUrl).origin });
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  try {
    await page.goto(`${baseUrl}hevy-to-sparkyfitness/command-line/`);
    const command = (name) => page.locator(`[data-cmd="${name}"] pre`).innerText();

    await page.check('#os-unix', { force: true });
    await page.check('#src-app', { force: true });
    assert.equal(await command('convert'), 'python3 hevy_to_sparkyfitness.py workout_data.csv --weight kg --distance km');

    await page.check('#os-win', { force: true });
    await page.check('#src-web', { force: true });
    await page.check('#w-lbs', { force: true });
    await page.check('#d-miles', { force: true });
    await page.check('#use-table');
    assert.equal(await command('list'), 'py hevy_to_sparkyfitness.py workouts.csv --list-exercises');
    assert.equal(await command('convert'),
      'py hevy_to_sparkyfitness.py workouts.csv --weight lbs --distance miles --exercise-map workouts_exercises.csv');
    assert.equal(await page.locator('code[data-file="output"]').first().innerText(), 'workouts_sparkyfitness.csv');

    // The longest command fits: it wraps between arguments.
    const fits = await page.locator('[data-cmd="convert"] pre').evaluate((pre) => pre.scrollWidth <= pre.clientWidth);
    assert.equal(fits, true, 'the convert command is cut off');

    // Copy twice quickly: the label must come back to "Copy".
    const copy = page.locator('[data-cmd="convert"] .copy');
    await copy.click();
    await copy.click();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()),
      'py hevy_to_sparkyfitness.py workouts.csv --weight lbs --distance miles --exercise-map workouts_exercises.csv');
    await page.waitForTimeout(2200);
    assert.equal(await copy.innerText(), 'Copy');

    // The easy version is linked from the guide, and the download works.
    assert.equal(await page.locator('a[href="../"]').count() > 0, true);
    const [download] = await Promise.all([page.waitForEvent('download'), page.click('a[download]')]);
    assert.equal(download.suggestedFilename(), 'hevy_to_sparkyfitness.py');
    assert.deepEqual(errors, []);
  } finally {
    await context.close();
  }
}
