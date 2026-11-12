# Changelog

## 0.5.2

- Keep wide timeline layouts on one row: no full-width overflow row for distributions. Up to three distributions sit beside the timeline; the third appears only when the first two have fewer than 10 categories combined, and the row grows up to 320px to fit it. Sidebar rows are sized by category count.
- Restore all distributions when resizing to narrow containers, including when none fit the wide sidebar, and preserve keyboard controls and theme changes.

## 0.5.1

- Restore timeline-only initial loads and `facets_on=False`; Django’s effective counts mode enables rates/distributions for inline and lazy rendering.
- Restore direct aggregation for ordinary querysets, avoiding unconditional primary-key wrappers and unused rate annotations. Keep duplicate-safe handling for multiplying joins and grouped/distinct sources.
- Aggregate timelines once at the requested period and roll up counts and rate totals in Python to at most 240 display intervals, preserving complete history and drill-down boundaries.
- Remove More charts, hidden panels, numeric metrics and top-N settings/getters/checks. Enabled distributions remain visible; preserve styling, positioning, keyboard controls, themes, labels and legend choices.
- Include effective counts mode in cache keys. Clarify exact-aggregation costs, separate Django counts and lazy/cache limits; refresh examples and gallery.

## 0.5

- Automatic date, choice and boolean discovery, independent of Django’s filter counts.
- Wide timeline with stacked summaries, responsive secondary charts, keyboard filtering and theme-aware styling.
- Bounded, duplicate-safe aggregation; nullable rates, complete date ranges and explicit Count, Sum and Avg metrics.
- Optional protected lazy loading and per-user caching, with safe labels and local drill-down links.
- Bundled Chart.js assets, deterministic examples, SQLite/PostgreSQL tests and browser coverage.
- Python 3.12–3.15 metadata and Django 5.2/6.0/6.1 support; Python 3.15 requires Django 6.1.3 onward.

See [upgrading from 0.4](migration.md) for changes to defaults and private hooks.
