# Query budgets and performance

Charts aggregate the complete filtered changelist independently of pagination. Discovery performs no queries. The normal timeline, selected boolean rates, and explicit metrics share one grouped query. Each selected distribution uses one grouped query, limited in SQL to six categories plus one sentinel for truncation. Constant/empty selected candidates are suppressed without trying replacements, so suppressed charts can still consume their one grouped query.

No extra count query is added. The normal page reuses `ChangeList.result_count`. A semijoin against the filtered primary keys prevents duplicate-producing searches/filters from inflating volume, rates or scalar numeric metrics. Scalar annotations are correlated back to the filtered source. Ordering, `select_related` and prefetch work are removed from aggregation; permissions, filtering and database alias remain effective.

A timeline fetches at most 242 grouped rows: up to 240 displayed buckets, an overflow sentinel and an undated group. Sparse gaps also count toward the 240-bucket limit. If the current period overflows or spans too many buckets, another bounded query retries a coarser period. Very long year ranges use one additional min/max query and a bounded year-block aggregation. These exceptional queries preserve history. Automatic date inference itself has no range-discovery query.

Explicit related top-N charts may add one bounded batched scalar-label query. Explicit limits are capped at 100. Django admin's own counts, date-navigation queries and optional facet counts are separate from these chart budgets. Lazy loading reconstructs a ChangeList, so its HTTP request repeats normal admin count/filter work even though chart aggregation remains bounded.

## Benchmark your workload

The benchmark creates synthetic Event rows over 180 days, with two booleans and one status choice. It reports the median of three payload computations, SQL query counts, returned aggregation rows, payload size and compressed bundle size. Timings exclude seeding, base admin rendering and HTTP; they depend on your database, indexes, hardware and filters.

The development build bundles only the Chart.js bar/line components and required plugins. Consumers use the bundled assets without Node or a CDN.

## Reproduce

```bash
python scripts/benchmark.py
# On a dedicated local database; Django creates and destroys its test database:
TEST_POSTGRES=1 PGDATABASE=dalc_bench python scripts/benchmark.py --output .cache/benchmarks/postgresql.json
```

Results default to the ignored `.cache/benchmarks/sqlite.json` file. Use `--sizes 10000` for a quick run. Test DB creation must be permitted. The benchmark creates only synthetic data and never queries an internal project. Index your actual search/filter sources and measure your own workload before choosing optional lazy loading or caching.
