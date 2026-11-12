# Automatic behavior and optional configuration

The mixin-only example is the default. Automatic discovery uses only metadata and the request's effective filters. It chooses fields before aggregation, then suppresses empty or constant charts without querying replacement candidates. It never guesses sums, averages, business meaning or currencies.

Automatic dates prefer `date_hierarchy`, then `created_at`, `created`, `date_created`, `date_joined`, `published_at`, `published`, and `timestamp`, then a sole eligible date field. Ambiguous dates omit the timeline. Modification and `auto_now` fields are not inferred. The selected field labels the timeline. Date navigation changes hourly/daily/weekly aggregation; longer ranges automatically coarsen. Locale and active Django timezone apply to labels and boundaries.

Charts sit above the list controls. Initially only the timeline is queried and shown. Django’s “Show counts” enables rate overlays and distributions; `ShowFacets.ALWAYS` enables them on every request and `NEVER` disables them even when `_facets` is present. Inline rendering and lazy loading use the effective `ChangeList.add_facets` value.

On wide containers every chart stays on one row. The timeline takes at least two-thirds of the width, with up to three compact distributions stacked in a sidebar. The third distribution is shown only when the first two have fewer than 10 categories combined; the row then grows by up to 76px (to at most 320px) to fit it. Distributions that do not fit beside the timeline are left out rather than wrapped onto a separate row. Narrow containers stack all distributions below the timeline. The timeline plot is 216px high unless the row grows. Click a series label to show or hide it. Legend choices survive counts navigation, resizing and theme changes.

## Settings on ModelAdmin

| Attribute | Default | Purpose |
| --- | --- | --- |
| `chart_facet_fields` | `()` | Explicit categorical dimensions |
| `chart_rate_fields` | `()` | Explicit nullable boolean overlays |
| `chart_facet_max_series` | `6` | Categories per distribution |
| `chart_auto_select` | `True` | Metadata discovery |
| `chart_auto_max_facet_fields` | `3` | Automatic distribution candidates |
| `chart_auto_max_rate_fields` | `2` | Automatic rate candidates |
| `chart_labels` | `{}` | Display labels by field name |
| `chart_lazy` | `False` | Load through a protected admin endpoint |
| `chart_cache_timeout` | `0` | Optional Django cache TTL in seconds |
| `chart_cache_alias` | `'default'` | Django cache alias |

Empty explicit tuples keep automatic discovery for compatibility with 0.4. Set automatic limits to zero to disable that portion; set `chart_auto_select=False` for entirely explicit configuration. Explicit charts may show a single populated category. Constant automatic charts are hidden. Categories beyond the limit are omitted with a “Top categories” label; totals across visible categories may be smaller than the changelist count. Explicit limits are capped at 100.

## Public hooks

- `get_chart_date_field(request)` returns a date field path or `None`.
- `get_chart_queryset(request, changelist)` defaults to the complete filtered `changelist.queryset`. Keep the same model and preserve your permission restrictions. A narrowed source computes its own timeline total in the grouped query.
- `get_chart_field(request, queryset, name)` resolves scalar model paths and annotation output fields. Override for synthetic metadata. System checks may call this hook for model paths with `request=None`; annotation names are resolved against the request's queryset.
- `get_chart_facet_fields`, `get_chart_rate_fields`, and the automatic-limit getters allow request-dependent configuration.
- `get_chart_palette(request)` returns optional `accent` and `series` colors.
- `get_chart_link(request, field_name, value, end=None)` returns a local filtering URL or `None`. `end` identifies a half-open timeline range.
- `get_chart_payload(request, qs, period=None, facets_on=False, total_rows=None)` remains available for full payload customization. `facets_on` enables rate overlays and distributions; its default restores the timeline-only behavior. Passing a known total avoids work for empty selections; no count query is performed.

Scalar boolean annotations work with explicit `chart_rate_fields` / `chart_facet_fields`. See `memberships/admin.py` for an `Exists` subscription annotation. Explicit foreign-key distributions batch label lookups on the queryset's database, preferring scalar `name`, `label` or `title`, then the target key. They do not call arbitrary related `__str__` methods.

## Drill-down

Click a chart point to filter, or focus the chart and use arrow keys to explore points and Enter to follow its filtering link. Links preserve unrelated filters/search, replace the selected dimension and reset pagination. ModelAdmin lookup permissions apply. Annotation dimensions and custom filter semantics require an explicit link hook. Custom `SimpleListFilter` classes are not interpreted as model dimensions. A named field paired with a custom `FieldListFilter` is not given guessed links.

## Lazy loading and caching

`chart_lazy=True` renders the page first and fetches `chart-data/` under that model's admin URL. Django admin authentication, model view/change permission, search and filtering are reused. Failures show a retry button. Lazy loading moves aggregation to another request; it does not make that aggregation cheaper. Without JavaScript, Django’s list remains usable and charts stay hidden.

Caching is disabled by default and does not guarantee cheap queries: a miss still performs exact aggregation. Set `chart_cache_timeout` to enable Django's configured cache. Keys include the admin/model, user, query parameters, filtered SQL and parameters, database alias, chart configuration, effective counts mode, filters, palette, language and active timezone. Every request still checks permissions and rebuilds the filtered changelist. Cached data may be stale until the TTL expires; there is no write-triggered invalidation. If custom behavior depends on external state beyond those inputs, leave the built-in caching disabled. Lazy HTTP responses are private and `no-store`.

```python
ADMIN_LIST_CHARTS = {
    'palette': {'accent': '#1f5fa6', 'series': ['#2f9e44', '#d6336c']},
}
```

Use CSS-compatible concrete color strings. Default colors follow stock admin theme changes without a reload.

## Checks

`manage.py check` reports nonnegative integer configuration errors (`E002`) and invalid model paths (`W001`). Metric checks and the metric/top-N settings and getters were removed in 0.5.1; downstream attributes are unused. Request-dependent annotation names are resolved when charts load and need no startup metadata override.
