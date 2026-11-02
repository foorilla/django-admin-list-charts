# Automatic behavior and optional configuration

The mixin-only example is the default. Automatic discovery uses only metadata and the request's effective filters. It chooses fields before aggregation, then suppresses empty or constant charts without querying replacement candidates. It never guesses sums, averages, business meaning or currencies.

Automatic dates prefer `date_hierarchy`, then `created_at`, `created`, `date_created`, `date_joined`, `published_at`, `published`, and `timestamp`, then a sole eligible date field. Ambiguous dates omit the timeline. Modification and `auto_now` fields are not inferred. The selected field labels the timeline. Date navigation changes hourly/daily/weekly aggregation; longer ranges automatically coarsen. Locale and active Django timezone apply to labels and boundaries.

Charts sit above the list controls. The timeline takes at least two-thirds of the width, with compact distributions stacked in a sidebar where space permits. Overflow charts, top-N charts and metrics sit under “More charts”, closed initially. The timeline is 216px high; secondary grid plots are 300px. Click a series label to show or hide it. “Show counts” changes filter counts only, preserving chart size, content and disclosure state. Hidden charts are instantiated only when opened.

## Settings on ModelAdmin

| Attribute | Default | Purpose |
| --- | --- | --- |
| `chart_facet_fields` | `()` | Explicit categorical dimensions |
| `chart_rate_fields` | `()` | Explicit nullable boolean overlays |
| `chart_top_fields` | `()` | Explicit `(field, limit)` top-N charts |
| `chart_facet_max_series` | `6` | Categories per distribution |
| `chart_auto_select` | `True` | Metadata discovery |
| `chart_auto_max_facet_fields` | `3` | Automatic distribution candidates |
| `chart_auto_max_rate_fields` | `2` | Automatic rate candidates |
| `chart_metrics` | `{}` | Mapping of names to `Count`, `Sum`, or `Avg` expressions |
| `chart_labels` | `{}` | Display labels by field or metric name |
| `chart_lazy` | `False` | Load through a protected admin endpoint |
| `chart_cache_timeout` | `0` | Optional Django cache TTL in seconds |
| `chart_cache_alias` | `'default'` | Django cache alias |

Empty explicit tuples keep automatic discovery for compatibility with 0.4. Set automatic limits to zero to disable that portion; set `chart_auto_select=False` for entirely explicit configuration. Explicit charts may show a single populated category. Constant automatic charts are hidden. Categories beyond the limit are omitted with a “Top categories” label; totals across visible categories may be smaller than the changelist count. Explicit limits are capped at 100.

## Numeric metrics

```python
from django.db.models import Avg, Count, Q, Sum

class OrderAdmin(ListChartMixin, admin.ModelAdmin):
    chart_metrics = {
        'revenue': Sum('amount'),
        'average_order': Avg('amount'),
        'paid_orders': Count('pk', filter=Q(paid=True)),
    }
    chart_labels = {'revenue': 'Revenue (USD)', 'average_order': 'Average order (USD)'}
```

Each metric gets its own scale and chart. All timeline metrics share the volume/rate aggregation query. Count gaps are zero; sum/average gaps are null. Values remain numeric, without automatic currency assumptions. Metrics require a date field. Expressions must reference scalar fields/annotations or single-valued paths. For multi-valued numeric sources, first provide a scalar subquery annotation; direct multi-valued aggregates are rejected by system checks to prevent inflated volume/rates.

## Public hooks

- `get_chart_date_field(request)` returns a date field path or `None`.
- `get_chart_queryset(request, changelist)` defaults to the complete filtered `changelist.queryset`. Keep the same model and preserve your permission restrictions. A narrowed source computes its own timeline total in the grouped query.
- `get_chart_field(request, queryset, name)` resolves scalar model paths and annotation output fields. Override for synthetic metadata. System checks may call this hook for model paths with `request=None`; annotation names are resolved against the request's queryset.
- `get_chart_metrics(request)` returns the metric mapping.
- `get_chart_facet_fields`, `get_chart_rate_fields`, `get_chart_top_fields`, and the automatic-limit getters allow request-dependent configuration.
- `get_chart_palette(request)` returns optional `accent` and `series` colors.
- `get_chart_link(request, field_name, value, end=None)` returns a local filtering URL or `None`. `end` identifies a half-open timeline range.
- `get_chart_payload(request, qs, period=None, facets_on=True, total_rows=None)` remains available for full payload customization. `facets_on` is accepted but no longer hides charts. Passing a known total avoids work for empty selections; no count query is performed.

Scalar boolean annotations work with explicit `chart_rate_fields` / `chart_facet_fields`. See `memberships/admin.py` for an `Exists` subscription annotation. Explicit foreign-key top-N charts batch label lookups on the queryset's database, preferring scalar `name`, `label` or `title`, then the target key. They do not call arbitrary related `__str__` methods.

## Drill-down

Click a chart point to filter, or focus the chart and use arrow keys to explore points and Enter to follow its filtering link. Links preserve unrelated filters/search, replace the selected dimension and reset pagination. ModelAdmin lookup permissions apply. Annotation dimensions and custom filter semantics require an explicit link hook. Custom `SimpleListFilter` classes are not interpreted as model dimensions. A named field paired with a custom `FieldListFilter` is not given guessed links.

## Lazy loading and caching

`chart_lazy=True` renders the page first and fetches `chart-data/` under that model's admin URL. Django admin authentication, model view/change permission, search and filtering are reused. Failures show a retry button. Without JavaScript, Django’s list remains usable and charts stay hidden.

Caching is disabled by default. Set `chart_cache_timeout` to enable Django's configured cache. Keys include the admin/model, user, query parameters, filtered SQL and parameters, database alias, chart configuration, effective filters, palette, language and active timezone. Every request still checks permissions and rebuilds the filtered changelist. Cached data may be stale until the TTL expires; there is no write-triggered invalidation. If custom behavior depends on external state beyond those inputs, leave the built-in caching disabled. Lazy HTTP responses are private and `no-store`.

```python
ADMIN_LIST_CHARTS = {
    'palette': {'accent': '#1f5fa6', 'series': ['#2f9e44', '#d6336c']},
}
```

Use CSS-compatible concrete color strings. Default colors follow stock admin theme changes without a reload.

## Checks

`manage.py check` reports invalid metric types (`E001`), nonnegative integer configuration errors (`E002`), multi-valued metric paths (`E003`), and invalid model paths (`W001`). Request-dependent annotation names are resolved when charts load and need no startup metadata override.
