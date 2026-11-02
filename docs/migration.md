# Migrating from 0.4 to 0.5

Keep the mixin before `admin.ModelAdmin`. App registration and ordinary static deployment stay the same. Existing `date_hierarchy`, `chart_facet_fields`, `chart_rate_fields`, `chart_top_fields`, palette settings, and public field/limit getters remain usable.

1. Charts now appear without Django's “Show counts”. Date hierarchy is optional; automatic date discovery never mutates it. Existing hierarchy navigation still works.
2. Automatic selection uses metadata and effective `get_list_filter(request)`, without data-driven scoring. Related leaf paths stay intact. Arbitrary free-text filters and unrestricted foreign keys no longer become automatic charts; use `chart_top_fields` explicitly if useful.
3. Automatic defaults are three categorical candidates and two boolean rate candidates. Constant/empty candidates are hidden without querying replacements. To disable a portion, set its automatic limit to zero; empty explicit tuples still enable discovery, as in 0.4.
4. Facets are direct categorical distributions. `chart_facet_max_series` still limits categories. Distributions include undated records; null dates are reported separately from the timeline. Truncated charts are labelled as top categories.
5. Nullable booleans exclude unknown values from denominators. Gaps in rates, sums and averages are null, while count gaps are zero. Duplicate-producing joins do not inflate aggregates. Numeric aggregates require explicit `chart_metrics` expressions.
6. Timelines coarsen automatically to at most 240 buckets. They do not drop old history to satisfy the bound.
7. `chart_payload` in template context is now a Python mapping passed through `json_script`, rather than a pre-serialized JSON string. The old JSON `chart_data` context is removed. Custom templates must use the new structured payload and external static assets. Chart.js is now 4.6.1, bundled privately; the package no longer creates a global `Chart` object.
8. Python 3.12 remains the floor. Use maintained Django 5.2, 6.0 or 6.1. Python 3.15 requires Django 6.1.3 onward.

Charts appear above the list controls. The compact row moves overflow charts, top-N charts and metrics into a closed “More charts” section. “Show counts” changes filter counts only. No additional configuration is needed.

## Replacing private overrides

| Previous private override | Public replacement |
| --- | --- |
| `_get_model_field` | `get_chart_field(request, queryset, name)` |
| `_get_auto_list_filter_facet_candidates`, `_select_auto_facet_fields` | `get_chart_facet_fields(request)` |
| `_get_auto_boolean_rate_candidates`, `_select_auto_rate_fields` | `get_chart_rate_fields(request)` |
| `_get_volume_data`, `_get_facet_data`, `_get_rate_data`, `_get_top_data` | Field/metric getters, or full `get_chart_payload` customization |
| Relation/display label helpers | `chart_labels`, scalar annotation labels, or full payload customization |

`_get_chart_period(request)` is retained for the existing date-navigation behavior, but new date discovery should override `get_chart_date_field(request)`. The private aggregation and scoring methods were removed. `get_chart_payload` still accepts `facets_on`, which no longer controls chart visibility.

Admins with annotated subscription booleans can explicitly select those scalar annotations; related company/source filters are resolved at the leaf. Custom filter and annotation dimensions need an explicit link hook to supply their own drill-down semantics.
