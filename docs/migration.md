# Migrating to 0.5.1

Keep the mixin before `admin.ModelAdmin`. App registration and ordinary static deployment stay the same. Version 0.5 is already on PyPI; 0.5.1 corrects its initial-load query regression.

## From 0.5

- Initial loads show and query only the timeline. Django’s “Show counts” enables rate overlays and standard distributions. Inline and lazy paths honor effective `ShowFacets.ALLOW`, `ALWAYS` and `NEVER` policies. Direct `get_chart_payload` callers now default to `facets_on=False`; pass `True` for distributions and rates.
- Ordinary filtered querysets aggregate directly, as in 0.4. Duplicate-producing joins and grouped/distinct sources retain duplicate-safe handling. Unused rate annotations are not selected when counts are off.
- Long histories use one requested-period aggregation followed by Python rollup to at most 240 fixed-width display intervals. The payload retains the requested `period` and exposes `bucket_step`; `year_step` is removed. Counts and known/true totals are combined before calculating rates. No date restriction or sampling is added.
- “More charts”, its disclosure state, and the secondary chart grid are removed. All enabled distributions are visible beside or directly below the timeline. The 216px timeline plot, chart positioning, keyboard controls, themes and label fixes remain. Legend choices survive counts navigation, resizing and theme changes.
- **Removed:** `chart_metrics`, `get_chart_metrics`, `chart_top_fields`, and `get_chart_top_fields`, their aggregation and metric checks (`E001`, `E003`). Existing downstream attributes/overrides are unused; remove them. Payload `metrics` and `tops` keys are removed. Use `chart_facet_fields` for standard distributions; numeric metric charts are no longer supported.
- Optional lazy loading and caching remain available. Neither guarantees cheap queries. Cache keys include effective counts mode; ordinary Django counts are separate from chart query budgets.

## From 0.4

1. Date hierarchy is optional; automatic date discovery never mutates it. Existing hierarchy navigation still works.
2. Automatic selection uses metadata and effective `get_list_filter(request)`, without data-driven candidate scoring. Related leaf paths stay intact. Arbitrary free-text filters and unrestricted foreign keys no longer become automatic charts.
3. Automatic defaults are three categorical candidates and two boolean rate candidates. Constant/empty candidates are hidden without querying replacements. Set automatic limits to zero to disable a portion; empty explicit tuples still enable discovery. Set `chart_auto_select=False` for entirely explicit configuration.
4. Facets are direct categorical distributions. `chart_facet_max_series` limits categories. Distributions include undated records; null dates are reported separately from the timeline. Truncated charts are labelled as top categories.
5. Nullable booleans exclude unknown values from rate denominators. Rate gaps are null; count gaps are zero. Duplicate-producing joins do not inflate aggregates. Long histories preserve complete totals.
6. `chart_payload` in template context is a Python mapping passed through `json_script`, rather than a pre-serialized JSON string. The old JSON `chart_data` context is removed. Custom templates must use the structured payload and external static assets. Chart.js is 4.6.1, bundled privately without a global `Chart` object.
7. Python 3.12 remains the floor. Use maintained Django 5.2, 6.0 or 6.1. Python 3.15 requires Django 6.1.3 onward.

## Replacing private overrides

| Previous private override | Public replacement |
| --- | --- |
| `_get_model_field` | `get_chart_field(request, queryset, name)` |
| `_get_auto_list_filter_facet_candidates`, `_select_auto_facet_fields` | `get_chart_facet_fields(request)` |
| `_get_auto_boolean_rate_candidates`, `_select_auto_rate_fields` | `get_chart_rate_fields(request)` |
| `_get_volume_data`, `_get_facet_data`, `_get_rate_data` | Field getters or full `get_chart_payload` customization |
| `_get_top_data` | Removed; use standard `chart_facet_fields` distributions where appropriate |
| Relation/display label helpers | `chart_labels`, scalar annotation labels or full payload customization |

`_get_chart_period(request)` is retained for date navigation. New date discovery should override `get_chart_date_field(request)`. Private aggregation and scoring methods are removed. Annotated booleans can be explicitly selected; custom filters and annotation dimensions need an explicit link hook for their own drill-down semantics.
