import {Chart, BarController, BarElement, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Tooltip} from 'chart.js';
import {color} from 'chart.js/helpers';

Chart.register(BarController, BarElement, LineController, LineElement, PointElement,
  CategoryScale, LinearScale, Tooltip);

const root = document.querySelector('.alc');
if (root) start(root);

async function start(root) {
  root.hidden = false;
  let payload, primary, sidebar, overflow, announcement;
  let cards = [];
  let layoutKey;
  const locale = root.dataset.locale || document.documentElement.lang || 'en';
  const numbers = new Intl.NumberFormat(locale);
  const percentages = new Intl.NumberFormat(locale, {style: 'percent', maximumFractionDigits: 1});
  const compactNumbers = new Intl.NumberFormat(locale, {notation: 'compact', maximumFractionDigits: 1});
  const alpha = (value, opacity) => {
    const parsed = color(value);
    return parsed.valid ? parsed.alpha(opacity).rgbString() : value;
  };
  const isolatedPoint = context => {
    const values = context.dataset.data, index = context.dataIndex;
    return values[index] != null && values[index - 1] == null && values[index + 1] == null ? 1.5 : 0;
  };
  const text = (tag, value, parent, className = '') => {
    const element = document.createElement(tag);
    element.textContent = value;
    element.className = className;
    parent.append(element);
    return element;
  };
  const safeLink = url => {
    if (!url) return null;
    try {
      const target = new URL(url, window.location.href);
      return target.origin === window.location.origin && ['http:', 'https:'].includes(target.protocol) ? target.href : null;
    } catch {
      return null;
    }
  };
  const valueLabel = (value, rate = false) => value == null ? '—' : (rate ? percentages : numbers).format(value);
  const legendKey = `admin-list-charts:legend:${location.pathname}`;
  const SIDE_HEIGHT = 244, MAX_SIDE_HEIGHT = 320;
  const sideNeed = card => 42 + card.data.data.length * 14;

  function activate(card, index) {
    const chart = card.instance;
    if (!chart || !card.data.data.length) return;
    card.pointIndex = index;
    const active = chart.data.datasets.flatMap((dataset, datasetIndex) =>
      chart.isDatasetVisible(datasetIndex) ? [{datasetIndex, index}] : []);
    const point = chart.getDatasetMeta(0).data[index];
    chart.setActiveElements(active);
    chart.tooltip.setActiveElements(active, {
      x: Number.isFinite(point.x) ? point.x : chart.chartArea.left,
      y: Number.isFinite(point.y) ? point.y : chart.chartArea.bottom,
    });
    chart.update('none');
    announcement.textContent = [card.label, chart.data.labels[index], ...chart.data.datasets.flatMap((dataset, datasetIndex) =>
      chart.isDatasetVisible(datasetIndex) ? [`${dataset.label}: ${valueLabel(dataset.data[index], dataset.yAxisID === 'rate')}`] : [])].join('. ');
  }

  function buildCards() {
    cards.forEach(card => card.instance?.destroy());
    root.querySelectorAll('.alc-status, .alc-primary, .alc-overflow, .alc-footer, .alc-sr').forEach(element => element.remove());
    cards = [];
    layoutKey = null;
    primary = text('div', '', root, 'alc-primary');
    root.classList.toggle('alc-has-timeline', Boolean(payload.volume.length));
    sidebar = text('div', '', primary, 'alc-sidebar');
    overflow = text('div', '', root, 'alc-overflow');
    const footer = text('div', '', root, 'alc-footer');
    if (payload.missing_dates) {
      const note = text('p', payload.missing_dates_label, footer, 'alc-note');
      note.title = payload.missing_dates_label;
    }
    let restored;
    try {
      restored = JSON.parse(sessionStorage.getItem(legendKey));
      sessionStorage.removeItem(legendKey);
    } catch { /* Chart rendering also works when storage is unavailable. */ }
    announcement = text('p', '', root, 'alc-sr');
    announcement.setAttribute('role', 'status');
    announcement.setAttribute('aria-live', 'polite');
    function card(label, type, data, group) {
      const element = text('article', '', overflow, `alc-card${type === 'timeline' ? ' alc-timeline' : ''}`);
      const title = data.truncated ? `${label} (${root.dataset.topLabel})` : label;
      const header = text('div', '', element, 'alc-head');
      text('h2', title, header).title = title;
      const wrapper = text('div', '', element, 'alc-canvas');
      const canvas = text('canvas', '', wrapper);
      canvas.dataset.chart = type;
      canvas.tabIndex = 0;
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', title);
      canvas.setAttribute('aria-description', root.dataset.keyboardLabel);
      const hidden = type === 'timeline' && Array.isArray(restored) ? restored : [];
      const item = {element, canvas, label, type, data, group, pointIndex: 0, instance: null, hiddenSeries: new Set(hidden), buttons: []};
      if (type === 'timeline' && payload.rates.length) {
        const legend = text('div', '', header, 'alc-legend');
        [root.dataset.countLabel, ...payload.rates.map(rate => rate.label)].forEach((label, index) => {
          const button = text('button', '', legend);
          button.type = 'button';
          button.title = label;
          button.setAttribute('aria-pressed', String(!item.hiddenSeries.has(index)));
          text('span', '', button, 'alc-swatch').setAttribute('aria-hidden', 'true');
          text('span', label, button, 'alc-series-label');
          button.addEventListener('click', () => {
            if (!item.instance) return;
            const visible = item.hiddenSeries.has(index);
            if (visible) item.hiddenSeries.delete(index);
            else item.hiddenSeries.add(index);
            button.setAttribute('aria-pressed', String(visible));
            item.instance.setDatasetVisibility(index, visible);
            item.instance.update('none');
          });
          item.buttons.push(button);
        });
      }
      canvas.addEventListener('focus', () => activate(item, item.pointIndex));
      canvas.addEventListener('keydown', event => {
        const points = data.data;
        if (['ArrowLeft', 'ArrowUp', 'ArrowRight', 'ArrowDown', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? points.length - 1 :
            item.pointIndex + (['ArrowRight', 'ArrowDown'].includes(event.key) ? 1 : -1);
          activate(item, Math.max(0, Math.min(points.length - 1, next)));
        } else if (event.key === 'Enter') {
          event.preventDefault();
          const url = safeLink(points[item.pointIndex]?.url);
          if (url) window.location.assign(url);
        }
      });
      canvas.addEventListener('blur', () => {
        if (!item.instance) return;
        item.instance.setActiveElements([]);
        item.instance.tooltip.setActiveElements([], {x: 0, y: 0});
        item.instance.update('none');
      });
      cards.push(item);
    }
    if (payload.volume.length) card(payload.date_label, 'timeline', {data: payload.volume}, 'timeline');
    payload.facets.forEach(chart => card(chart.label, 'distribution', chart, 'facet'));
    if (!cards.length) text('p', root.dataset.emptyLabel, primary, 'alc-status');
  }

  function colors() {
    const style = getComputedStyle(root);
    const body = getComputedStyle(document.body);
    return {
      ink: body.getPropertyValue('--body-fg').trim() || '#333',
      quiet: body.getPropertyValue('--body-quiet-color').trim() || '#666',
      grid: body.getPropertyValue('--hairline-color').trim() || '#ddd',
      surface: body.getPropertyValue('--body-bg').trim() || '#fff',
      accent: payload.palette?.accent || style.getPropertyValue('--alc-accent').trim() || '#417690',
      series: payload.palette?.series?.length ? payload.palette.series :
        [style.getPropertyValue('--alc-green').trim() || '#18794e',
         style.getPropertyValue('--alc-purple').trim() || '#7750a5'],
    };
  }

  function render(refresh = false) {
    if (!primary) return;
    const palette = colors();
    Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
    cards.forEach(card => {
      if (!card.element.isConnected) return;
      const {canvas, type, data} = card;
      const mini = card.element.parentElement === sidebar;
      if (card.instance && (refresh || card.mini !== mini)) {
        card.instance.destroy();
        card.instance = null;
      }
      if (card.instance) {
        card.instance.resize();
        return;
      }
      const points = data.data;
      card.mini = mini;
      const horizontal = type === 'distribution';
      let gradient, gradientKey;
      const barFill = context => {
        const {ctx, chartArea: area} = context.chart;
        if (!area) return palette.accent;
        const key = [area.left, area.right, area.top, area.bottom].join();
        if (key !== gradientKey) {
          gradientKey = key;
          gradient = horizontal ? ctx.createLinearGradient(area.left, 0, area.right, 0) :
            ctx.createLinearGradient(0, area.top, 0, area.bottom);
          gradient.addColorStop(0, alpha(palette.accent, horizontal ? .45 : .95));
          gradient.addColorStop(1, alpha(palette.accent, horizontal ? .95 : .32));
        }
        return gradient;
      };
      const labels = points.map(point => point.label || point.x);
      const datasets = [{label: type === 'timeline' ? root.dataset.countLabel : card.label,
        data: points.map(point => point.y), backgroundColor: barFill, borderColor: palette.accent,
        order: type === 'timeline' ? 1 : 0,
        borderRadius: 4, maxBarThickness: type === 'timeline' ? 32 : 18,
        borderWidth: 0, pointRadius: 0,
        pointHoverRadius: 3, spanGaps: false}];
      if (type === 'timeline') {
        payload.rates.forEach((rate, index) => datasets.push({type: 'line', label: rate.label,
          data: rate.data.map(point => point.y), yAxisID: 'rate', borderWidth: 1.25,
          borderColor: palette.series[index % palette.series.length],
          pointRadius: isolatedPoint,
          pointHoverRadius: 3, tension: .15, spanGaps: false}));
      }
      datasets.forEach((dataset, index) => { dataset.hidden = card.hiddenSeries.has(index); });
      card.buttons.forEach((button, index) => button.style.setProperty('--alc-series-color',
        index ? palette.series[(index - 1) % palette.series.length] : palette.accent));
      // Shorten ticks only; tooltips and keyboard announcements keep full labels.
      const shortLabel = function(value) {
        const label = String(this.getLabelForValue(value));
        const limit = horizontal ? 16 : 18;
        return label.length > limit ? `${label.slice(0, limit - 1)}…` : label;
      };
      const scales = {
        x: {grid: {display: horizontal, color: alpha(palette.grid, .6)}, border: {display: false},
          ticks: {color: palette.quiet, font: {size: mini ? 10 : 11}, maxRotation: 0, autoSkip: true,
            maxTicksLimit: horizontal ? (mini ? 2 : 3) : 6,
            callback: horizontal ? value => compactNumbers.format(value) : shortLabel}},
        y: {beginAtZero: true, grid: {display: !horizontal, color: alpha(palette.grid, .6)}, border: {display: false},
          ticks: {color: palette.quiet, font: {size: mini ? 10 : 11}, precision: 0,
            ...(horizontal ? {callback: shortLabel, autoSkip: !mini} : {maxTicksLimit: 5, callback: value => compactNumbers.format(value)})}},
      };
      if (type === 'timeline' && payload.rates.length) scales.rate = {
        // Keep boundary values fully inside the plot instead of clipping their strokes.
        position: 'right', min: -.03, max: 1.03, grid: {display: false}, border: {display: false},
        afterBuildTicks: scale => { scale.ticks = [0, .5, 1].map(value => ({value})); },
        ticks: {color: palette.quiet, font: {size: 11}, callback: value => percentages.format(value)},
      };
      card.instance = new Chart(canvas, {
        type: 'bar', data: {labels, datasets},
        plugins: horizontal ? (mini ? [{id: 'alc-values', afterDatasetsDraw(chart) {
          const {ctx} = chart;
          ctx.save();
          ctx.font = `10px ${Chart.defaults.font.family}`;
          ctx.fillStyle = palette.ink;
          ctx.textBaseline = 'middle';
          chart.getDatasetMeta(0).data.forEach((bar, index) => {
            const label = compactNumbers.format(points[index].y);
            ctx.fillText(label, Math.min(bar.x + 5, chart.width - ctx.measureText(label).width - 2), bar.y);
          });
          ctx.restore();
        }}] : []) : [{id: 'alc-guide', beforeDatasetsDraw(chart) {
          const active = chart.getActiveElements()[0];
          if (!active) return;
          const {ctx, chartArea: area} = chart;
          ctx.save();
          ctx.strokeStyle = alpha(palette.quiet, .35);
          ctx.lineWidth = 1;
          ctx.setLineDash([3, 4]);
          ctx.beginPath();
          ctx.moveTo(active.element.x, area.top);
          ctx.lineTo(active.element.x, area.bottom);
          ctx.stroke();
          ctx.restore();
        }}],
        options: {
          locale, animation: false, responsive: true, maintainAspectRatio: false,
          layout: {padding: {right: mini ? 38 : 0}},
          indexAxis: horizontal ? 'y' : 'x', color: palette.ink,
          interaction: {mode: horizontal ? 'nearest' : 'index', intersect: false}, scales,
          plugins: {
            tooltip: {itemSort: (a, b) => a.datasetIndex - b.datasetIndex,
              backgroundColor: palette.surface, titleColor: palette.ink, bodyColor: palette.ink,
              borderColor: palette.grid, borderWidth: 1, cornerRadius: 6, padding: 10, boxPadding: 4,
              callbacks: {label: context => `${context.dataset.label}: ${
              valueLabel(context.raw, context.dataset.yAxisID === 'rate')}`}},
          },
          onHover: (event, elements) => { canvas.style.cursor = elements.length && safeLink(points[elements[0].index]?.url) ? 'pointer' : 'default'; },
          onClick: (event, elements) => {
            const url = elements.length && safeLink(points[elements[0].index]?.url);
            if (url) window.location.assign(url);
          },
        },
      });
      if (document.activeElement === canvas) activate(card, card.pointIndex);
    });
    root.dataset.ready = 'true';
  }

  function layout() {
    if (!primary) return;
    const timeline = cards.find(card => card.type === 'timeline');
    let candidates = cards.filter(card => ['timeline', 'facet'].includes(card.group));
    if (!candidates.length) candidates = cards.slice(0, 1);
    const width = root.getBoundingClientRect().width;
    const oneRow = Boolean(timeline) && width >= 696;
    const sideCards = [];
    let sideHeight = SIDE_HEIGHT;
    if (oneRow) {
      let used = 0;
      for (const card of candidates.filter(card => card !== timeline)) {
        // A third distribution only joins when the first two are short; the row may grow a little for it.
        if (sideCards.length === 3 || (sideCards.length === 2 &&
          sideCards[0].data.data.length + sideCards[1].data.data.length >= 10)) break;
        const height = sideNeed(card) + (sideCards.length ? 8 : 0);
        if (used + height > (sideCards.length === 2 ? MAX_SIDE_HEIGHT : SIDE_HEIGHT)) break;
        used += height;
        sideCards.push(card);
      }
      sideHeight = Math.max(SIDE_HEIGHT, used);
    }
    // Wide timeline layouts stay on one row: distributions that do not fit beside the timeline are left out.
    const count = timeline ? 1 + sideCards.length :
      Math.min(candidates.length, Math.max(1, Math.floor((width + 8) / 168)));
    const key = `${Boolean(timeline)}:${oneRow}:${count}:${sideHeight}`;
    if (key === layoutKey) return;
    layoutKey = key;
    const leading = new Set(timeline ? [timeline] : candidates.slice(0, count));
    const side = new Set(sideCards);
    let primaryIndex = 0, sidebarIndex = 0, overflowIndex = 0;
    cards.forEach(card => {
      if (oneRow && !leading.has(card) && !side.has(card)) {
        card.instance?.destroy();
        card.instance = null;
        card.element.remove();
        return;
      }
      const target = leading.has(card) ? primary : side.has(card) ? sidebar : overflow;
      const index = target === primary ? primaryIndex++ : target === sidebar ? sidebarIndex++ : overflowIndex++;
      if (target.children[index] !== card.element) target.insertBefore(card.element, target.children[index] || null);
    });
    sidebar.hidden = !sideCards.length;
    sidebar.style.gridTemplateRows = sideCards.map(card => `minmax(0, ${sideNeed(card)}fr)`).join(' ');
    primary.style.setProperty('--alc-row', `${sideHeight}px`);
    primary.classList.toggle('alc-with-sidebar', Boolean(sideCards.length));
    primary.hidden = !cards.length && !primary.querySelector('.alc-status');
    render();
  }

  async function load() {
    try {
      if (root.dataset.endpoint) {
        const response = await fetch(root.dataset.endpoint, {credentials: 'same-origin', headers: {Accept: 'application/json'}});
        if (!response.ok) throw new Error('Chart request failed');
        payload = await response.json();
      } else payload = JSON.parse(document.getElementById('admin-list-charts-data').textContent);
      buildCards();
      layout();
    } catch (error) {
      root.querySelector('.alc-status')?.remove();
      const status = text('p', root.dataset.errorLabel, root, 'alc-status');
      status.setAttribute('role', 'status');
      if (root.dataset.endpoint) {
        const retry = text('button', root.dataset.retryLabel, status);
        retry.type = 'button';
        retry.addEventListener('click', load);
      }
    }
  }
  await load();
  // Keep chart choices through Django's filter-count navigation only.
  document.querySelectorAll('#changelist-filter-extra-actions a.viewlink, #changelist-filter-extra-actions a.hidelink').forEach(link => {
    link.addEventListener('click', event => {
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const timeline = cards.find(card => card.type === 'timeline');
      try {
        sessionStorage.setItem(legendKey, JSON.stringify([...(timeline?.hiddenSeries || [])]));
      } catch { /* Optional state preservation. */ }
    });
  });
  new ResizeObserver(() => requestAnimationFrame(layout)).observe(root);
  new MutationObserver(() => render(true)).observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => render(true));
}
