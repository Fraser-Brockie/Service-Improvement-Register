Initial evaluation, 24 November 2026.

Timing, memory, query-plan and cProfile artifacts are genuine retained measurements.
The two experimental indexes have the same column definitions as the subsequently
adopted indexes; their initial names were idx_perf_summary and idx_perf_title.
The benchmark source used for this run is retained as benchmark-source.py.txt.

The concurrent workload installed its busy_timeout override after authentication,
so the first authentication SELECT could still use the connection default timeout.
Do not treat its zero-timeout concurrency results as a uniform request-wide policy.
The confirmation run fixes hook ordering and is the authoritative concurrency run.
The confirmation also records the precise deep-page OFFSET used by its timed workload.
See ../confirmation-2026-11-24 and ../../PERFORMANCE.md for final conclusions.
