import {test, expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';
import {readFile} from 'node:fs/promises';

const examples = {
  visits: '/admin/demo/visit/', commerce: '/admin/commerce/order/',
  memberships: '/admin/memberships/account/', publishing: '/admin/publishing/job/',
};
const advanced = {
  visits: '/admin/demo/visitexplorer/', commerce: '/admin/commerce/ordermetrics/',
  memberships: '/admin/memberships/accountsubscriptions/', publishing: '/admin/publishing/jobexplorer/',
};

test.beforeEach(async ({page}) => {
  await page.goto('/admin/login/');
  await page.getByLabel('Username:').fill('demo');
  await page.getByLabel('Password:').fill('demo');
  await page.getByRole('button', {name: 'Log in', exact: true}).click();
  await expect(page).toHaveURL('/admin/');
  await page.route('**/gallery-font.woff2', async route => route.fulfill({
    contentType: 'font/woff2', body: await readFile('node_modules/@fontsource/inter/files/inter-latin-400-normal.woff2'),
  }));
});

async function open(page, url, theme = 'light') {
  await page.addInitScript(theme => localStorage.setItem('theme', theme), theme);
  await page.goto(url);
  await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
  await styleCharts(page, theme);
}

async function styleCharts(page, theme) {
  await page.addStyleTag({content: "@font-face{font-family:Gallery;src:url('/gallery-font.woff2')}body,canvas{font-family:Gallery,sans-serif!important}"});
  await page.evaluate(async theme => {
    await document.fonts.ready;
    document.documentElement.setAttribute('data-theme', theme);
  }, theme);
}

async function compact(page) {
  const root = page.locator('.alc');
  expect(await root.evaluate(element => element.getBoundingClientRect().height)).toBeLessThanOrEqual(300);
  await expect(root).toHaveCSS('margin-bottom', '8px');
  await expect(root.locator('table, select')).toHaveCount(0);
  await expect(root.getByText('View chart data')).toHaveCount(0);
  await expect(root.locator('details[open]')).toHaveCount(0);
  expect(await root.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  const chart = await root.boundingBox();
  const changelist = await page.locator('#changelist').boundingBox();
  expect(chart.y + chart.height).toBeLessThanOrEqual(changelist.y);
  for (const canvas of await root.locator('.alc-primary > .alc-card .alc-canvas').all()) await expect(canvas).toHaveCSS('height', '216px');
  const timeline = root.locator('.alc-timeline');
  if (await timeline.count()) {
    const width = await timeline.evaluate(element => element.getBoundingClientRect().width);
    expect(width).toBeGreaterThanOrEqual((await root.boundingBox()).width * 2 / 3 - 1);
  }
  for (const heading of await root.locator('h2').all()) await expect(heading).toHaveCSS('background-color', 'rgba(0, 0, 0, 0)');
}

async function capture(page, filename) {
  const browser = test.info().project.use.browserName || 'chromium';
  const canonical = browser === 'chromium' && process.platform === 'darwin';
  const directory = canonical ? 'test-results/gallery' : `test-results/gallery-${browser}-${process.platform}`;
  await page.locator('.alc').screenshot({path: `${directory}/${filename}`});
  if (['visits-light-desktop.png', 'commerce-counts-dark-desktop.png'].includes(filename)) {
    await page.screenshot({path: `test-results/layout/${filename}`});
  }
  if (canonical) {
    await expect(page.locator('.alc')).toHaveScreenshot(filename);
  } else test.info().annotations.push({type: 'visual-comparison-skipped', description: 'Baselines target Chromium on macOS.'});
}

async function hiddenCanvasesAreEmpty(page) {
  await expect.poll(() => page.locator('.alc canvas').evaluateAll(canvases => canvases.filter(canvas => !canvas.checkVisibility()).every(canvas =>
    !canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data.some(value => value)))).toBe(true);
}

for (const [name, url] of Object.entries(examples)) {
  for (const theme of ['light', 'dark']) {
    for (const [device, width] of [['desktop', 1280], ['mobile', 390]]) {
      test(`${name} ${theme} ${device}`, async ({page}) => {
        const errors = [], external = [];
        page.on('pageerror', error => errors.push(error.message));
        page.on('request', request => {if (!request.url().startsWith('http://127.0.0.1:8765/')) external.push(request.url());});
        await page.setViewportSize({width, height: 960});
        await open(page, url, theme);
        await compact(page);
        await expect(page.locator('.alc canvas:visible')).not.toHaveCount(0);
        await hiddenCanvasesAreEmpty(page);
        await capture(page, `${name}-${theme}-${device}.png`);
        expect(errors).toEqual([]);
        expect(external).toEqual([]);
        expect(await page.evaluate(() => typeof window.Chart)).toBe('undefined');
        const issues = await new AxeBuilder({page}).include('.alc').analyze();
        expect(issues.violations).toEqual([]);
      });
    }
  }
}

for (const [name, url] of Object.entries(advanced)) {
  test(`advanced ${name}`, async ({page}) => {
    await open(page, url);
    await compact(page);
    if (name === 'commerce') {
      await expect(page.locator('.alc canvas[aria-label="Revenue (USD)"]')).toBeHidden();
      await page.locator('.alc summary').click();
      await expect(page.locator('.alc canvas[aria-label="Revenue (USD)"]')).toBeVisible();
    }
    if (name === 'memberships') expect(await page.locator('.alc').getAttribute('data-endpoint')).toContain('chart-data');
    const issues = await new AxeBuilder({page}).include('.alc').analyze();
    expect(issues.violations).toEqual([]);
  });
}

for (const mode of ['more', 'counts']) {
  for (const theme of ['light', 'dark']) {
    for (const [device, width] of [['desktop', 1280], ['mobile', 390]]) {
      test(`${mode === 'counts' ? 'counts preserve charts' : 'expanded more'} ${theme} ${device}`, async ({page}) => {
        await page.setViewportSize({width, height: 960});
        await open(page, advanced.commerce, theme);
        const root = page.locator('.alc');
        const initial = await root.screenshot();
        if (mode === 'more') {
          await page.locator('.alc summary').focus();
          await page.keyboard.press('Enter');
          await expect(page.locator('.alc details')).toHaveAttribute('open', '');
        } else {
          await page.getByRole('link', {name: 'Show counts', exact: true}).click();
          await expect(root).toHaveAttribute('data-ready', 'true');
          await styleCharts(page, theme);
          await compact(page);
          expect(await root.screenshot()).toEqual(initial);
        }
        if (mode === 'more') await expect(root.locator('canvas:visible')).toHaveCount(await root.locator('canvas').count());
        expect(await root.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
        await capture(page, `commerce-${mode}-${theme}-${device}.png`);
        const issues = await new AxeBuilder({page}).include('.alc').analyze();
        expect(issues.violations).toEqual([]);
        if (mode === 'counts') {
          await page.getByRole('link', {name: 'Hide counts', exact: true}).click();
          await expect(root).toHaveAttribute('data-ready', 'true');
          await styleCharts(page, theme);
          await compact(page);
          expect(await root.screenshot()).toEqual(initial);
        }
      });
    }
  }
}

test('filter counts preserve an open More charts disclosure without persisting regular reloads', async ({page}) => {
  await open(page, advanced.commerce);
  const root = page.locator('.alc');
  await root.locator('summary').click();
  await root.locator('summary').evaluate(element => element.blur());
  const initial = await root.screenshot();
  for (const label of ['Show counts', 'Hide counts']) {
    await page.getByRole('link', {name: label, exact: true}).click();
    await expect(root).toHaveAttribute('data-ready', 'true');
    await styleCharts(page, 'light');
    await expect(root.locator('details')).toHaveAttribute('open', '');
    expect(await root.screenshot()).toEqual(initial);
  }
  await page.reload();
  await expect(root).toHaveAttribute('data-ready', 'true');
  await compact(page);
});

test('container overflow, keyboard expansion, resizing and themes preserve disclosure state', async ({page}) => {
  await page.setViewportSize({width: 2200, height: 960});
  await open(page, examples.visits);
  const root = page.locator('.alc');
  const count = await root.locator('.alc-card').count();
  await expect(root.locator('.alc-sidebar .alc-card')).toHaveCount(2);
  await expect(root.locator('canvas:visible')).toHaveCount(3);
  await root.evaluate(element => element.style.width = '695px');
  await expect(root.locator('canvas:visible')).toHaveCount(1);
  await root.evaluate(element => element.style.width = '696px');
  await expect(root.locator('canvas:visible')).toHaveCount(3);
  await compact(page);
  await root.evaluate(element => element.style.width = '320px');
  await expect(root.locator('canvas:visible')).toHaveCount(1);
  await expect(root.locator('.alc-timeline canvas')).toBeVisible();
  await compact(page);
  await hiddenCanvasesAreEmpty(page);
  await root.locator('summary').focus();
  await page.keyboard.press('Enter');
  await expect(root.locator('canvas:visible')).toHaveCount(count);
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  await expect(root.locator('details')).toHaveAttribute('open', '');
  await root.evaluate(element => element.style.width = '1200px');
  await compactOpen(page);
  await root.evaluate(element => element.style.width = '320px');
  await expect(root.locator('details')).toHaveAttribute('open', '');
  await expect(root.locator('canvas:visible')).toHaveCount(count);
  await root.locator('summary').click();
  await expect(root.locator('canvas:visible')).toHaveCount(1);
  await hiddenCanvasesAreEmpty(page);
  await compact(page);
});

async function compactOpen(page) {
  const root = page.locator('.alc');
  const timeline = await root.locator('.alc-timeline').boundingBox();
  expect(timeline.width).toBeGreaterThanOrEqual((await root.boundingBox()).width * 2 / 3 - 1);
  await expect(root.locator('details')).toHaveAttribute('open', '');
}

test('series controls work with the keyboard and preserve choices through resizing and themes', async ({page}) => {
  await open(page, advanced.visits);
  const root = page.locator('.alc');
  const control = root.locator('.alc-legend button').nth(1);
  const label = (await control.textContent()).trim();
  await control.focus();
  await page.keyboard.press('Enter');
  await expect(control).toHaveAttribute('aria-pressed', 'false');
  await root.locator('.alc-timeline canvas').focus();
  await expect(root.locator('[role="status"]')).not.toContainText(`${label}:`);
  await root.evaluate(element => element.style.width = '320px');
  await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
  await expect(control).toHaveAttribute('aria-pressed', 'false');
  await root.locator('.alc-timeline canvas').focus();
  await page.keyboard.press('ArrowRight');
  await expect(root.locator('[role="status"]')).not.toContainText(`${label}:`);
  await page.getByRole('link', {name: 'Show counts', exact: true}).click();
  await expect(root).toHaveAttribute('data-ready', 'true');
  await expect(control).toHaveAttribute('aria-pressed', 'false');
  await control.focus();
  await page.keyboard.press('Space');
  await expect(control).toHaveAttribute('aria-pressed', 'true');
  await root.locator('.alc-timeline canvas').focus();
  await expect(root.locator('[role="status"]')).toContainText(`${label}:`);
  const issues = await new AxeBuilder({page}).include('.alc').analyze();
  expect(issues.violations).toEqual([]);
});

test('filters, search, duplicate joins, keyboard drill-down and empty results', async ({page}) => {
  await open(page, advanced.publishing + '?q=python&status__exact=live');
  const payload = JSON.parse(await page.locator('#admin-list-charts-data').textContent());
  expect(payload.volume.reduce((sum, row) => sum + row.y, 0) + payload.missing_dates).toBe(payload.total_count);
  const canvas = page.locator('.alc-timeline canvas');
  await canvas.focus();
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.alc [role="status"]')).toContainText(payload.volume[1].label);
  const url = payload.volume[1].url;
  const target = new URL(url, page.url()).href;
  expect(url).toContain('q=python');
  expect(url).toContain('status__exact=live');
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(target);
  await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
  await open(page, advanced.publishing + '?q=missing-nonexistent-value');
  await expect(page.locator('.alc')).toContainText('No chart data for this selection.');
  await expect(page.locator('.alc summary')).toBeHidden();
});

test('mouse drill-down on a distribution', async ({page}) => {
  await open(page, examples.commerce);
  const payload = JSON.parse(await page.locator('#admin-list-charts-data').textContent());
  const chart = page.locator('.alc-primary canvas[data-chart="distribution"]').first();
  const box = await chart.boundingBox();
  const target = new URL(payload.facets[0].data[0].url, page.url()).href;
  await chart.click({position: {x: box.width / 2, y: 20}});
  await expect(page).toHaveURL(target);
});

test('auto theme transitions without a reload', async ({page}) => {
  await page.emulateMedia({colorScheme: 'light'});
  await open(page, examples.visits, 'auto');
  const light = await page.locator('.alc canvas').first().screenshot();
  await page.emulateMedia({colorScheme: 'dark'});
  await expect(async () => expect(await page.locator('.alc canvas').first().screenshot()).not.toEqual(light)).toPass();
  await expect(page.locator('html')).toHaveAttribute('data-theme', 'auto');
});

test('lazy failure, retry, counts and hostile labels', async ({page}) => {
  await page.route('**/accountsubscriptions/chart-data/**', route => route.fulfill({status: 500}));
  await page.goto(advanced.memberships);
  await expect(page.locator('.alc')).toContainText('Charts could not be loaded.');
  await page.unroute('**/accountsubscriptions/chart-data/**');
  const attack = '<img src=x onerror="window.compromised=true">';
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.facets[0].data[0].x = attack;
    payload.facets[0].data[0].url = 'javascript:window.compromised=true';
    await route.fulfill({json: payload});
  });
  await page.getByRole('button', {name: 'Retry', exact: true}).click();
  await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
  await page.getByRole('link', {name: 'Show counts', exact: true}).click();
  await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
  await compact(page);
  const canvas = page.locator('.alc canvas[data-chart="distribution"]').first();
  await canvas.focus();
  await expect(page.locator('.alc [role="status"]')).toContainText(attack);
  const previous = page.url();
  await page.keyboard.press('Enter');
  await expect(page).toHaveURL(previous);
  await expect(page.locator('.alc img')).toHaveCount(0);
  expect(await page.evaluate(() => window.compromised)).toBeUndefined();
});

test('lazy charts without timelines, long labels, missing dates and primary top-N fallback', async ({page}) => {
  const longLabel = 'A category with a very long descriptive label that must remain readable in tooltips';
  await page.addInitScript(() => {
    window.chartText = [];
    const fillText = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      window.chartText.push(String(text));
      return fillText.call(this, text, ...args);
    };
  });
  let topOnly = false;
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.volume = [];
    payload.rates = [];
    payload.metrics = [];
    payload.date_field = null;
    payload.missing_dates = 12;
    payload.missing_dates_label = '12 records have no date.';
    payload.facets[0].data[0].x = longLabel;
    payload.facets[0].label = longLabel;
    if (topOnly) { payload.tops = payload.facets.slice(0, 1); payload.facets = []; }
    await route.fulfill({json: payload});
  });
  await page.setViewportSize({width: 390, height: 960});
  await open(page, advanced.memberships);
  const root = page.locator('.alc');
  await root.evaluate(element => element.style.width = '320px');
  await expect(root.locator('canvas[data-chart="timeline"]')).toHaveCount(0);
  await expect(root.locator('canvas:visible')).toHaveCount(1);
  await expect(root.locator('canvas:visible')).toHaveAttribute('aria-label', longLabel);
  await expect(root.locator('.alc-note')).toHaveText('12 records have no date.');
  await compact(page);
  expect(await page.evaluate(() => window.chartText)).toContain(longLabel.slice(0, 15) + '…');
  expect(await page.evaluate(() => window.chartText)).not.toContain(longLabel);
  const canvas = root.locator('canvas:visible');
  const box = await canvas.boundingBox();
  await page.mouse.move(box.x + box.width - 20, box.y + 20);
  await expect.poll(() => page.evaluate(label => window.chartText.includes(label), longLabel)).toBe(true);
  await canvas.focus();
  await expect(root.locator('[role="status"]')).toContainText(longLabel);
  await page.keyboard.press('ArrowDown');
  await expect(root.locator('[role="status"]')).not.toContainText(`. ${longLabel}.`);
  topOnly = true;
  await open(page, advanced.memberships);
  await expect(root.locator('canvas:visible')).toHaveCount(1);
  await expect(root.locator('summary')).toBeHidden();
  await compact(page);
});

test('metrics and top-N stay secondary until expanded', async ({page}) => {
  await open(page, advanced.commerce);
  const metrics = page.locator('.alc canvas[data-chart="metric"]');
  await expect(metrics.first()).toBeHidden();
  await page.locator('.alc summary').click();
  await expect(metrics).toHaveCount(2);
  await expect(metrics.first()).toBeVisible();
  await metrics.first().focus();
  await page.keyboard.press('End');
  await expect(page.locator('.alc [role="status"]')).toContainText('Revenue (USD)');
  await open(page, advanced.publishing);
  const payload = JSON.parse(await page.locator('#admin-list-charts-data').textContent());
  expect(payload.tops.length).toBeGreaterThan(0);
  const top = page.locator('.alc-panels canvas').last();
  await expect(page.locator('.alc-panels canvas').last()).toBeHidden();
  await page.locator('.alc summary').click();
  await expect(top).toBeVisible();
});

test('lazy decimal metrics preserve unknown values during keyboard navigation', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    window.metricDots = [];
    const arc = CanvasRenderingContext2D.prototype.arc;
    CanvasRenderingContext2D.prototype.arc = function(x, y, radius, ...args) {
      if (this.canvas.dataset.chart === 'metric') window.metricDots.push(radius);
      return arc.call(this, x, y, radius, ...args);
    };
  });
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.metrics = [{label: 'Revenue', data: payload.volume.map((point, index) => ({...point, y: index === 1 ? '12.50' : null}))}];
    await route.fulfill({json: payload});
  });
  await open(page, advanced.memberships);
  await page.locator('.alc summary').click();
  await expect.poll(() => page.evaluate(() => window.metricDots.some(radius => radius > 0))).toBe(true);
  await page.locator('.alc canvas[data-chart="metric"]').focus();
  await expect(page.locator('.alc [role="status"]')).toContainText('Revenue: —');
  await page.keyboard.press('ArrowRight');
  await expect(page.locator('.alc [role="status"]')).toContainText('Revenue: 12.5');
  expect(errors).toEqual([]);
});

test('large explicit distributions keep labels readable and all categories keyboard-accessible', async ({page}) => {
  await page.addInitScript(() => {
    window.categoryTicks = new Set();
    const fillText = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      if (/^Category \d+$/.test(String(text))) window.categoryTicks.add(String(text));
      return fillText.call(this, text, ...args);
    };
  });
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.volume = [];
    payload.rates = [];
    payload.facets = [];
    payload.metrics = [];
    payload.tops = [{field: 'category', label: 'Categories', data: Array.from({length: 100}, (_, index) =>
      ({x: `Category ${index + 1}`, y: 100 - index, url: null}))}];
    await route.fulfill({json: payload});
  });
  await open(page, advanced.memberships);
  expect(await page.evaluate(() => window.categoryTicks.size)).toBeLessThan(25);
  await page.locator('.alc canvas').focus();
  await page.keyboard.press('End');
  await expect(page.locator('.alc [role="status"]')).toContainText('Category 100');
});

test('many explicit rates, modern palette colors and blocked chart storage remain usable', async ({page}) => {
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.addInitScript(() => {
    for (const method of ['getItem', 'setItem']) {
      const original = Storage.prototype[method];
      Storage.prototype[method] = function(key, ...args) {
        if (key.startsWith('admin-list-charts:')) throw new DOMException('Storage unavailable', 'SecurityError');
        return original.call(this, key, ...args);
      };
    }
  });
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.palette = {accent: 'oklch(65% 0.12 230)', series: []};
    payload.rates = Array.from({length: 8}, (_, index) => ({label: `Long descriptive rate ${index + 1}`,
      data: payload.volume.map((point, month) => ({...point, y: (index + month) % 2}))}));
    await route.fulfill({json: payload});
  });
  await open(page, advanced.memberships);
  const root = page.locator('.alc');
  await root.evaluate(element => element.style.width = '320px');
  await compact(page);
  await expect(root.locator('.alc-legend button')).toHaveCount(9);
  const last = root.locator('.alc-legend button').last();
  await last.focus();
  await expect(last).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(last).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('link', {name: 'Show counts', exact: true}).click();
  await expect(root).toHaveAttribute('data-ready', 'true');
  expect(errors).toEqual([]);
});

for (const theme of ['light', 'dark']) {
  test(`dense history ${theme}`, async ({page}) => {
    await page.setViewportSize({width: 1280, height: 960});
    await page.route('**/accountsubscriptions/chart-data/**', async route => {
      const response = await route.fetch();
      const payload = await response.json();
      const dates = new Intl.DateTimeFormat('en-US', {month: 'long', year: 'numeric', timeZone: 'UTC'});
      payload.volume = Array.from({length: 120}, (_, index) => {
        const date = new Date(Date.UTC(2016, index, 1));
        return {x: date.toISOString(), label: dates.format(date),
          y: index < 75 ? 50 + index % 7 * 30 : 1000 + (index - 75) ** 2 * 12, url: null};
      });
      payload.rates.forEach((rate, series) => {
        rate.data = payload.volume.map((point, index) => ({...point,
          y: index === 68 || index === 88 ? null : series ? (index < 60 ? 0 : .025 + (index % 9) / 500) :
            index < 60 ? 1 : Math.max(.15, .99 - (index - 60) / 75 + Math.sin(index) / 12)}));
      });
      payload.facets = [];
      payload.tops = [];
      payload.metrics = [];
      payload.missing_dates = 0;
      await route.fulfill({json: payload});
    });
    await open(page, advanced.memberships, theme);
    await compact(page);
    await expect(page.locator('.alc canvas:visible')).toHaveCount(1);
    // Long runs at 0% and 100% must paint actual series pixels inside the plot.
    const edges = await page.locator('.alc canvas').evaluate(canvas => {
      const {data} = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height);
      const bands = [0, 0];
      for (let y = 0; y < canvas.height; y++) {
        for (let x = 60; x < 300; x++) {
          const offset = (y * canvas.width + x) * 4;
          const [r, g, b] = data.subarray(offset, offset + 3);
          if (y < 30 && g > r * 1.3 && g > b * 1.1) bands[0]++;
          if (y > canvas.height - 40 && r > g * 1.1 && b > g * 1.2) bands[1]++;
        }
      }
      return bands;
    });
    expect(edges[0]).toBeGreaterThan(120);
    expect(edges[1]).toBeGreaterThan(120);
    await capture(page, `dense-history-${theme}-desktop.png`);
    await page.locator('.alc canvas').focus();
    await page.keyboard.press('End');
    await expect(page.locator('.alc [role="status"]')).toContainText('December 2025');
    for (let index = 0; index < 34; index++) await page.keyboard.press('ArrowLeft');
    await capture(page, `dense-inspection-${theme}-desktop.png`);
  });
}

test('ordinary changelist works without JavaScript and chart tables', async ({page, browser}) => {
  const context = await browser.newContext({javaScriptEnabled: false,
    baseURL: 'http://127.0.0.1:8765', storageState: await page.context().storageState()});
  try {
    const plain = await context.newPage();
    await plain.goto(advanced.commerce);
    await expect(plain.locator('.alc')).toBeHidden();
    await expect(plain.locator('#result_list')).toBeVisible();
    await plain.getByRole('link', {name: 'Show counts', exact: true}).click();
    await expect(plain.getByRole('link', {name: 'Hide counts', exact: true})).toBeVisible();
    await expect(plain.locator('.alc table')).toHaveCount(0);
  } finally {
    await context.close();
  }
});


test('charts render when a host theme clears chart color variables', async ({page}) => {
  await page.route('**/admin_list_charts/css/charts.css', async route => {
    const response = await route.fetch();
    await route.fulfill({response, body: await response.text() +
      '\n.alc { --alc-accent: ; --alc-green: ; --alc-purple: ; }'});
  });
  await open(page, advanced.commerce);
  await compact(page);
  await page.locator('.alc summary').click();
  await expect(page.locator('.alc canvas:visible')).toHaveCount(await page.locator('.alc canvas').count());
});
