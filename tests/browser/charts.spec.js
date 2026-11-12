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
  if (!await root.locator('[data-chart="distribution"]').count()) {
    expect(await root.evaluate(element => element.getBoundingClientRect().height)).toBeLessThanOrEqual(300);
  }
  await expect(root).toHaveCSS('margin-bottom', '8px');
  await expect(root.locator('table, select')).toHaveCount(0);
  await expect(root.getByText('View chart data')).toHaveCount(0);
  await expect(root.locator('details, .alc-panels, .alc-card[hidden]')).toHaveCount(0);
  await expect(root.locator('canvas:visible')).toHaveCount(await root.locator('canvas').count());
  expect(await root.evaluate(element => element.scrollWidth <= element.clientWidth)).toBe(true);
  const chart = await root.boundingBox();
  const changelist = await page.locator('#changelist').boundingBox();
  expect(chart.y + chart.height).toBeLessThanOrEqual(changelist.y);
  const sidebar = root.locator('.alc-sidebar:visible');
  if (await sidebar.count()) {
    // Wide layouts keep every chart on the timeline row, which may grow a little for a third distribution.
    await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(0);
    const cards = await sidebar.locator('.alc-card').count();
    expect(cards).toBeLessThanOrEqual(3);
    const sideHeight = await sidebar.evaluate(element => element.getBoundingClientRect().height);
    expect(sideHeight).toBeGreaterThanOrEqual(244);
    expect(sideHeight).toBeLessThanOrEqual(320);
    const plot = await root.locator('.alc-timeline .alc-canvas').evaluate(element => element.getBoundingClientRect().height);
    expect(plot).toBe(sideHeight - 28);
    if (cards < 3) expect(plot).toBe(216);
  } else {
    for (const canvas of await root.locator('.alc-primary > .alc-card .alc-canvas').all()) await expect(canvas).toHaveCSS('height', '216px');
  }
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

for (const counts of [false, true]) {
  for (const [name, url] of Object.entries(examples)) {
    for (const theme of ['light', 'dark']) {
      for (const [device, width] of [['desktop', 1280], ['mobile', 390]]) {
        test(`${name} ${counts ? "counts " : ""}${theme} ${device}`, async ({page}) => {
          const errors = [], external = [];
          page.on('pageerror', error => errors.push(error.message));
          page.on('request', request => {if (!request.url().startsWith('http://127.0.0.1:8765/')) external.push(request.url());});
          await page.setViewportSize({width, height: 960});
          await open(page, url + (counts ? '?_facets=True' : ''), theme);
          await compact(page);
          await expect(page.locator('.alc canvas:visible')).not.toHaveCount(0);
          const payload = JSON.parse(await page.locator('#admin-list-charts-data').textContent());
          expect(Boolean(payload.facets.length)).toBe(counts);
          if (!counts) {
            expect(payload.rates).toEqual([]);
            await expect(page.locator('.alc canvas')).toHaveCount(1);
          }
          await capture(page, `${name}${counts ? '-counts' : ''}-${theme}-${device}.png`);
          expect(errors).toEqual([]);
          expect(external).toEqual([]);
          expect(await page.evaluate(() => typeof window.Chart)).toBe('undefined');
          const issues = await new AxeBuilder({page}).include('.alc').analyze();
          expect(issues.violations).toEqual([]);
        });
      }
    }
  }
}

for (const [name, url] of Object.entries(advanced)) {
  test(`advanced ${name}`, async ({page}) => {
    await open(page, url);
    await compact(page);
    await expect(page.locator('.alc canvas')).toHaveCount(1);
    await page.getByRole('link', {name: 'Show counts', exact: true}).click();
    await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
    await compact(page);
    await expect(page.locator('.alc canvas[data-chart="metric"]')).toHaveCount(0);
    await expect(page.locator('.alc canvas[data-chart="distribution"]').first()).toBeVisible();
    await page.getByRole('link', {name: 'Hide counts', exact: true}).click();
    await expect(page.locator('.alc')).toHaveAttribute('data-ready', 'true');
    await expect(page.locator('.alc canvas')).toHaveCount(1);
  });
}

test('distributions stay beside the timeline on wide containers and stack on narrow ones', async ({page}) => {
  await page.setViewportSize({width: 2200, height: 960});
  await open(page, examples.visits + '?_facets=True');
  const root = page.locator('.alc');
  const payload = JSON.parse(await page.locator('#admin-list-charts-data').textContent());
  expect(payload.facets.length).toBeGreaterThan(2);
  const need = facet => 42 + facet.data.length * 14;
  const side = payload.facets[0].data.length + payload.facets[1].data.length >= 10 ||
    need(payload.facets[0]) + need(payload.facets[1]) + need(payload.facets[2]) + 16 > 320 ? 2 : 3;
  await expect(root.locator('.alc-sidebar .alc-card')).toHaveCount(side);
  await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(0);
  for (const width of [695, 696, 320, 1200, 320]) {
    await root.evaluate((element, width) => element.style.width = `${width}px`, width);
    await expect(root.locator('.alc-sidebar .alc-card')).toHaveCount(width >= 696 ? side : 0);
    await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(width >= 696 ? 0 : payload.facets.length);
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await compact(page);
  }
});

for (const [sizes, shown] of [[[4, 3, 3], 3], [[4, 4, 6], 2], [[6, 4, 2], 2], [[5, 5, 2], 2],
  [[3, 3, 2, 2], 3], [[8, 8], 1], [[15, 2], 0], [[20, 2], 0]]) {
  test(`distributions ${sizes.join('/')} keep ${shown} beside the timeline`, async ({page}) => {
    await page.setViewportSize({width: 1600, height: 960});
    await page.route('**/accountsubscriptions/chart-data/**', async route => {
      const response = await route.fetch();
      const payload = await response.json();
      payload.facets = sizes.map((size, chart) => ({field: `field${chart}`, label: `Field ${chart + 1}`,
        data: Array.from({length: size}, (_, index) => ({x: `Value ${index + 1}`, y: size - index, url: null}))}));
      await route.fulfill({json: payload});
    });
    await open(page, advanced.memberships + '?_facets=True');
    const root = page.locator('.alc');
    await expect(root.locator('.alc-sidebar .alc-card')).toHaveCount(shown);
    await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(0);
    const used = sizes.slice(0, shown).reduce((sum, size) => sum + 42 + size * 14, 0) + (shown - 1) * 8;
    if (shown) {
      const sidebar = await root.locator('.alc-sidebar').evaluate(element => element.getBoundingClientRect().height);
      expect(sidebar).toBe(Math.max(244, used));
    }
    await compact(page);
    await root.evaluate(element => element.style.width = '600px');
    await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(sizes.length);
    await compact(page);
    const last = root.locator('.alc-overflow canvas').last();
    await last.focus();
    await expect(root.locator('[role="status"]')).toContainText(`Field ${sizes.length}`);
    await page.evaluate(() => document.documentElement.setAttribute('data-theme', 'dark'));
    await root.evaluate(element => element.style.width = '900px');
    await expect(root.locator('.alc-sidebar .alc-card')).toHaveCount(shown);
    await expect(root.locator('.alc-overflow .alc-card')).toHaveCount(0);
    await compact(page);
  });
}

test('series controls work with the keyboard and preserve choices through resizing and themes', async ({page}) => {
  await open(page, advanced.visits + '?_facets=True');
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
  await page.getByRole('link', {name: 'Hide counts', exact: true}).click();
  await expect(root).toHaveAttribute('data-ready', 'true');
  await expect(root.locator('canvas')).toHaveCount(1);
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
  await expect(page.locator('.alc details')).toHaveCount(0);
});

test('mouse drill-down on a distribution', async ({page}) => {
  await open(page, examples.commerce + '?_facets=True');
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
  await page.goto(advanced.memberships + '?_facets=True');
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

test('lazy distributions without timelines retain full labels and missing date notes', async ({page}) => {
  const longLabel = 'A category with a very long descriptive label that must remain readable in tooltips';
  await page.addInitScript(() => {
    window.chartText = [];
    const fillText = CanvasRenderingContext2D.prototype.fillText;
    CanvasRenderingContext2D.prototype.fillText = function(text, ...args) {
      window.chartText.push(String(text));
      return fillText.call(this, text, ...args);
    };
  });
  await page.route('**/accountsubscriptions/chart-data/**', async route => {
    const response = await route.fetch();
    const payload = await response.json();
    payload.volume = [];
    payload.rates = [];
    payload.date_field = null;
    payload.missing_dates = 12;
    payload.missing_dates_label = '12 records have no date.';
    payload.facets[0].data[0].x = longLabel;
    payload.facets[0].label = longLabel;
    payload.facets = payload.facets.slice(0, 1);
    await route.fulfill({json: payload});
  });
  await page.setViewportSize({width: 390, height: 960});
  await open(page, advanced.memberships + '?_facets=True');
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
    payload.facets = [{field: 'category', label: 'Categories', data: Array.from({length: 100}, (_, index) =>
      ({x: `Category ${index + 1}`, y: 100 - index, url: null}))}];
    await route.fulfill({json: payload});
  });
  await open(page, advanced.memberships + '?_facets=True');
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
  await open(page, advanced.memberships + '?_facets=True');
  const root = page.locator('.alc');
  await root.evaluate(element => element.style.width = '320px');
  await compact(page);
  await expect(root.locator('.alc-legend button')).toHaveCount(9);
  const last = root.locator('.alc-legend button').last();
  await last.focus();
  await expect(last).toBeInViewport();
  await page.keyboard.press('Enter');
  await expect(last).toHaveAttribute('aria-pressed', 'false');
  await page.getByRole('link', {name: 'Hide counts', exact: true}).click();
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
        payload.missing_dates = 0;
      await route.fulfill({json: payload});
    });
    await open(page, advanced.memberships + '?_facets=True', theme);
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
  await open(page, advanced.commerce + '?_facets=True');
  await compact(page);
  await expect(page.locator('.alc canvas:visible')).toHaveCount(await page.locator('.alc canvas').count());
});
