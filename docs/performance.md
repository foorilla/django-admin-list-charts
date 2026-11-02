# Query budgets and performance

The initial view queries only the timeline: **one chart aggregation**, or zero for an empty selection or a model without an eligible date. Counts-off SQL does not select rate annotations or query distributions. Discovery uses model metadata without candidate-scoring queries.

Django’s “Show counts” enables rates and distributions. The timeline and selected boolean rates share one grouped query. Each selected standard distribution uses one grouped query, limited in SQL to the configured category limit plus one sentinel for truncation. Constant/empty candidates are suppressed without trying replacements, so they can still consume their grouped query. Explicit related distributions can also require one batched scalar-label query on the queryset’s database.

Query count is separate from database work. Exact aggregation still processes the complete filtered dataset; it does not sample or automatically restrict dates. A single grouped query can remain expensive for millions of records or costly filter/annotation expressions. Index the actual search/filter paths and measure the actual queryset. Restoring the ordinary 0.4 query path removes added initial-load work; confirming a downstream timeout is resolved requires testing that project’s queryset.

Ordinary querysets aggregate directly, preserving filters, permission restrictions and database routing. Only duplicate-producing joins or already-grouped/distinct sources use a primary-key semijoin. Only annotations used by a chart are selected; annotations needed by source filters remain effective. Ordering, `select_related` and prefetch work are removed from aggregation.

A timeline fetches the requested-period grouped results **once**, including its undated group. There are no coarsening retries or separate bounds queries. Python sums these results into at most 240 display intervals, using fixed multiples of the requested period anchored at the first bucket. Counts and known/true totals are summed before calculating rates. Complete history and zero-count/null-rate gaps remain visible. Returned SQL groups and memory use can exceed 240 for long, dense histories; only display intervals are bounded.

No chart count query is added. The normal page reuses `ChangeList.result_count`; narrowed custom timeline sources compute totals from the grouped results. Ordinary Django counts, date-navigation queries and optional filter facet counts remain separate. Lazy loading rebuilds a ChangeList and repeats its normal count/filter work; it defers aggregation without guaranteeing cheap queries. Optional caching can avoid aggregation on a hit, but misses still do exact work and every request rebuilds the filtered changelist.

## Benchmark your workload

The benchmark creates isolated synthetic Event rows over 180 days and reports the median of three payload computations, SQL and timings, payload size and compressed bundle size. Timings exclude seeding, base admin rendering and HTTP; they depend on the database, indexes, hardware and filters. Both timeline-only and counts-enabled modes are measured.

```bash
python scripts/benchmark.py --sizes 10000
# Django creates and destroys a dedicated test database:
TEST_POSTGRES=1 PGDATABASE=dalc_bench python scripts/benchmark.py --output .cache/benchmarks/postgresql.json
# Compare against the repository’s 0.4 source on identical data, including scale:
TEST_POSTGRES=1 PGDATABASE=dalc_bench python scripts/benchmark.py --sizes 10000 1000000 50000000 --compare-04 --output .cache/benchmarks/comparison.json
```

Results stay in ignored `.cache/benchmarks/` files. Test database creation must be permitted. PostgreSQL seeding uses `generate_series` for scale. The comparison loads the 0.4 admin implementation from commit `fadd278` and records source versions, SQL shapes and per-run timings. Its counts-enabled charts differ from 0.5.1, so that comparison includes differences in discovery and chart semantics. The timeline-only comparison uses the same grouping and filtered source. This synthetic benchmark does not establish the runtime of a downstream project’s actual queryset.

The development build bundles only the Chart.js bar/line components and required plugins. Consumers use bundled assets without Node or a CDN.
