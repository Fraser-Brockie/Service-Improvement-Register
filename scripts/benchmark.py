"""Isolated, reproducible Flask/SQLite performance evaluation (see docs/PERFORMANCE.md)."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import cProfile
import csv
from datetime import date, timedelta, datetime, timezone
import gc
import hashlib
import importlib.metadata
import io
import json
import math
import os
from pathlib import Path
import platform
import pstats
import random
import sqlite3
import statistics
import subprocess
import sys
import tempfile
import threading
from time import perf_counter_ns
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app, repository
from app.db import get_db, PERFORMANCE_INDEXES
from app.services import change_status, create_item, dashboard

# Applied ONLY to disposable benchmark databases. Baseline removes these even after
# an equivalent production migration is introduced, preserving the A/B comparison.
CANDIDATE_INDEXES = PERFORMANCE_INDEXES


def describe(values):
    ordered = sorted(values)
    return dict(mean=statistics.mean(values), median=statistics.median(values),
                minimum=min(values), maximum=max(values),
                p95=ordered[max(0, math.ceil(.95 * len(ordered)) - 1)])


def write_csv(path, rows):
    if rows:
        with path.open('w', newline='', encoding='utf-8') as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)


def application(path):
    return create_app({'TESTING': True, 'SECRET_KEY': 'isolated-benchmark-only', 'DATABASE': str(path)})


def seed(db, size):
    rng = random.Random(601)
    categories = ('Process', 'Quality', 'Technology', 'Customer')
    priorities = ('Low', 'Medium', 'High')
    statuses = ('New', 'In Progress', 'Done')
    epoch = date(2026, 1, 1)
    rows = []
    for n in range(size):
        day = (epoch + timedelta(days=rng.randrange(180))).isoformat()
        rows.append((f'Fictional request {n:06d}', rng.choice(categories), rng.choice(priorities),
                     'New' if n == 0 else rng.choice(statuses), day + ' 09:00:00',
                     ('needle ' if n % 20 == 0 else '') + 'Synthetic service improvement. ' * 8,
                     None if n % 4 == 0 else (epoch + timedelta(days=rng.randrange(240))).isoformat(),
                     day + ' 09:00:00', int(n != 0 and n % 10 == 0)))
    with db:
        db.executemany('''INSERT INTO improvement(title,category,priority,status,created_at,
                       description,due_date,updated_at,archived) VALUES (?,?,?,?,?,?,?,?,?)''', rows)
        db.executemany("INSERT INTO activity(item_id,message) VALUES (?, 'Synthetic creation')",
                       ((n + 1,) for n in range(size)))
    return hashlib.sha256(json.dumps(rows).encode()).hexdigest()


def normal(value):
    if isinstance(value, sqlite3.Row):
        return dict(value)
    if isinstance(value, dict):
        return {key: normal(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [normal(val) for val in value]
    return value


def memory_operations(db):
    # Identical projection, ordering, page size AND total count. Includes fetch cost.
    def sql_filter():
        return repository.search_items({'status': 'New'}, 1)

    def python_filter():
        rows = db.execute('SELECT * FROM improvement ORDER BY id DESC').fetchall()
        selected = [row for row in rows if not row['archived'] and row['status'] == 'New']
        return selected[:10], len(selected)

    return {'sql_filter': sql_filter, 'python_filter': python_filter}


def operations(db, size):
    active = db.execute('SELECT COUNT(*) FROM improvement WHERE archived=0').fetchone()[0]

    def generate_dashboard():
        # Same server-side data calls as routes.index, excluding HTML/authentication.
        return dashboard(include_items=False), repository.search_items({}, 1), repository.metrics()

    def create():
        item_id, result = create_item('Fictional measured creation', 'Process', 'High', 'Synthetic benchmark')
        assert result.valid
        return item_id

    def clean_creation(item_id):
        with db:
            db.execute('DELETE FROM activity WHERE item_id=?', (item_id,))
            db.execute('DELETE FROM improvement WHERE id=?', (item_id,))

    original_updated = db.execute('SELECT updated_at FROM improvement WHERE id=1').fetchone()[0]

    def reset_status(_):
        with db:
            db.execute("UPDATE improvement SET status='New', updated_at=? WHERE id=1", (original_updated,))
            db.execute("DELETE FROM activity WHERE item_id=1 AND message!='Synthetic creation'")

    ops = {
        'dashboard': (generate_dashboard, None),
        'substring_search': (lambda: repository.search_items({'q': 'needle'}, 1), None),
        'combined_filter': (lambda: repository.search_items({'status': 'New', 'priority': 'High', 'category': 'Process'}, 1), None),
        'page_first': (lambda: repository.search_items({}, 1), None),
        'page_deep': (lambda: repository.search_items({}, max(1, math.ceil(active / 10))), None),
        'sort_title': (lambda: repository.search_items({'sort': 'title'}, 1), None),
        'sort_due': (lambda: repository.search_items({'sort': 'due'}, 1), None),
        'aggregation': (repository.summary_counts, None),
        'request_creation': (create, clean_creation),
        'status_update': (lambda: change_status(1, 'Done'), reset_status),
    }
    return ops


def plans(db, size, phase):
    queries = {
        'substring': ("SELECT * FROM improvement WHERE archived=0 AND (instr(lower(title),lower(?))>0 OR instr(lower(description),lower(?))>0) ORDER BY id DESC LIMIT 10", ('needle', 'needle')),
        'filter': ("SELECT * FROM improvement WHERE archived=0 AND status=? AND priority=? AND category=? ORDER BY id DESC LIMIT 10", ('New', 'High', 'Process')),
        'page_first': ('SELECT * FROM improvement WHERE archived=0 ORDER BY id DESC LIMIT 10 OFFSET 0', ()),
        'page_deep': ('SELECT * FROM improvement WHERE archived=0 ORDER BY id DESC LIMIT 10 OFFSET ?', ((math.ceil(db.execute('SELECT COUNT(*) FROM improvement WHERE archived=0').fetchone()[0] / 10)-1)*10,)),
        'count': ('SELECT COUNT(*) FROM improvement WHERE archived=0', ()),
        'aggregation': ('SELECT status,priority,COUNT(*) FROM improvement WHERE archived=0 GROUP BY status,priority', ()),
        'sort_title': ('SELECT * FROM improvement WHERE archived=0 ORDER BY title COLLATE NOCASE,id LIMIT 10', ()),
        'sort_due': ('SELECT * FROM improvement WHERE archived=0 ORDER BY due_date IS NULL,due_date,id LIMIT 10', ()),
        'trend': ('SELECT substr(created_at,1,10) day,COUNT(*) FROM improvement WHERE archived=0 GROUP BY day ORDER BY day DESC LIMIT 30', ()),
    }
    return [dict(size=size, phase=phase, operation=name, sql=sql, parameters=args,
                 plan=[dict(row) for row in db.execute('EXPLAIN QUERY PLAN ' + sql, args)])
            for name, (sql, args) in queries.items()]


def profile_operations(ops, output, label, repeats):
    profiler = cProfile.Profile()
    profiler.enable()
    for _ in range(repeats):
        for operation, cleanup in ops.values():
            result = operation()
            if cleanup:
                cleanup(result)
    profiler.disable()
    profiler.dump_stats(str(output / f'{label}.prof'))
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream).strip_dirs()
    stats.sort_stats('cumulative').print_stats(35)
    stats.sort_stats('calls').print_stats(20)
    (output / f'{label}.txt').write_text(stream.getvalue(), encoding='utf-8')


def concurrent_requests(app, workers, per_worker, rounds):
    """Independent clients/connections, shared database; session setup is untimed."""
    records = []
    for trial in range(rounds):
        barrier = threading.Barrier(workers)

        def worker(number):
            client = app.test_client()
            with client.session_transaction() as session:
                session['auth_token'] = f'benchmark-token-{number}'
                session['csrf_token'] = 'benchmark-csrf'
            barrier.wait(timeout=30)
            rows = []
            for index in range(per_worker):
                write = (index + number) % 2 == 0
                start = perf_counter_ns()
                status, error = None, ''
                try:
                    if write:
                        response = client.post('/items', data={
                            'title': f'Concurrent fictional {number}-{index}',
                            'category': 'Process', 'priority': 'High',
                            'csrf_token': 'benchmark-csrf'})
                    else:
                        response = client.get('/requests?status=New')
                    status = response.status_code
                    if status != (302 if write else 200):
                        error = f'unexpected HTTP {status}'
                except Exception as exc:
                    error = f'{type(exc).__name__}: {exc}'
                rows.append(dict(trial=trial, worker=number, request=index,
                                 operation='write' if write else 'read',
                                 ms=(perf_counter_ns() - start) / 1e6, status=status, error=error))
            return rows

        start = perf_counter_ns()
        with ThreadPoolExecutor(max_workers=workers) as pool:
            batches = list(pool.map(worker, range(workers)))
        elapsed = (perf_counter_ns() - start) / 1e9
        for batch in batches:
            for row in batch:
                row['round_seconds'] = elapsed
                records.append(row)
    return records


def concurrency(source, directory, size, output, workers, per_worker, rounds):
    rows, probes = [], []
    for journal in ('DELETE', 'WAL'):
        for timeout in (0, 5000):
            target = directory / f'concurrency-{journal}-{timeout}.sqlite'
            with closing(sqlite3.connect(target)) as dest, dest:
                source.backup(dest)
                dest.execute(f'PRAGMA journal_mode={journal}')
                for name, sql in CANDIDATE_INDEXES.items():
                    dest.execute(f'DROP INDEX IF EXISTS {name}')
                    dest.execute(sql)
                dest.execute("INSERT INTO app_user(email,display_name,password_hash) VALUES ('bench@example.test','Synthetic','unused')")
                for n in range(workers):
                    dest.execute('INSERT INTO auth_session VALUES (?,?,?)', (
                        hashlib.sha256(f'benchmark-token-{n}'.encode()).hexdigest(), 1, 4102444800))
            app = application(target)
            app.logger.disabled = True

            def busy_timeout():
                # Benchmark policy only: production connection defaults remain unchanged.
                get_db().execute(f'PRAGMA busy_timeout={timeout}')

            # Install before authentication: even its first SELECT uses this policy.
            app.before_request_funcs.setdefault(None, []).insert(0, busy_timeout)
            measured = concurrent_requests(app, workers, per_worker, rounds)
            rows.extend(dict(size=size, journal=journal, busy_timeout_ms=timeout, **row) for row in measured)
            with closing(sqlite3.connect(target)) as verify:
                committed = verify.execute('SELECT COUNT(*) FROM improvement').fetchone()[0] - size
                successful = sum(r['operation'] == 'write' and not r['error'] for r in measured)
                assert committed == successful, (committed, successful)
            print(f'concurrency {journal}/{timeout} ms: {sum(bool(r["error"]) for r in measured)}/{len(measured)} failed', flush=True)
            # Deterministic writer contention: hold a RESERVED lock, test a second
            # connection in another thread. This is NOT a request/throughput sample.
            holder = sqlite3.connect(target)
            holder.execute('BEGIN IMMEDIATE')

            def contender():
                with closing(sqlite3.connect(target, timeout=.05)) as connection, connection:
                    start = perf_counter_ns()
                    read_count = connection.execute('SELECT COUNT(*) FROM improvement').fetchone()[0]
                    try:
                        connection.execute("UPDATE improvement SET status='Done' WHERE id=1")
                        error = ''
                    except sqlite3.OperationalError as exc:
                        error = str(exc)
                    return dict(journal=journal, workload_timeout_ms=timeout, requested_timeout_ms=50, read_count=read_count,
                                error=error, elapsed_ms=(perf_counter_ns()-start)/1e6)

            try:
                with ThreadPoolExecutor(max_workers=1) as pool:
                    probes.append(pool.submit(contender).result(timeout=30))
            finally:
                holder.rollback()
                holder.close()
    write_csv(output / 'concurrency.csv', rows)
    return rows, probes


def graphs(output, timing, memory):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10})
    fig, axes = plt.subplots(2, 2, figsize=(12, 9))
    groups = [
        ('dashboard', 'aggregation'), ('substring_search', 'combined_filter'),
        ('page_first', 'page_deep', 'sort_title', 'sort_due'), ('request_creation', 'status_update')]
    for ax, names in zip(axes.flat, groups):
        for number, name in enumerate(names):
            for phase, style in (('baseline', '--'), ('candidate', '-')):
                rows = [r for r in timing if r['operation'] == name and r['phase'] == phase]
                ax.plot([r['size'] for r in rows], [r['median'] for r in rows],
                        style, color=f'C{number}', marker='o', label=f'{name} {phase}')
                ax.fill_between([r['size'] for r in rows], [r['median'] for r in rows],
                                [r['p95'] for r in rows], color=f'C{number}', alpha=.08)
        ax.set(xscale='log', yscale='log', xlabel='Synthetic improvement records (log scale)',
               ylabel='Median execution time / ms (log scale)')
        if 'request_creation' in names:
            ax.set_yscale('linear')
            ax.set_ylim(bottom=0)
            ax.set_ylabel('Median execution time / ms')
        ax.grid(True, alpha=.25)
        ax.legend(fontsize=7)
    fig.suptitle('Flask/SQLite: baseline (dashed), candidate (solid); faint bands extend to p95')
    fig.tight_layout()
    fig.savefig(output / 'timings.png', dpi=160)
    fig.savefig(output / 'timings.svg')
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(9, 5))
    for method in ('sql_filter', 'python_filter'):
        rows = [r for r in memory if r['phase'] == 'candidate' and r['operation'] == method]
        ax.plot([r['size'] for r in rows], [r['peak_median_bytes']/1024 for r in rows], marker='o', label=method)
    ax.set(xscale='log', yscale='log', xlabel='Synthetic improvement records (log scale)',
           ylabel='Median peak traced Python allocation / KiB (log scale)',
           title='Equivalent status filtering: up to 10 returned rows plus total count')
    ax.grid(True, alpha=.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output / 'memory.png', dpi=160)
    fig.savefig(output / 'memory.svg')
    plt.close(fig)


def run(args):
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'results.json').exists():
        raise SystemExit('Choose a new --output directory; existing results are retained.')
    started = datetime.now(timezone.utc).isoformat()
    timings, raw, memory, memory_raw, query_plans, datasets, equivalence = [], [], [], [], [], [], []
    concurrent, probes = [], []
    # No DATABASE environment lookup or demonstration DB access: every app receives
    # an explicit newly created path AND an explicit secret.
    with tempfile.TemporaryDirectory(prefix='sir-performance-') as temp:
        directory = Path(temp)
        for size in args.sizes:
            path = directory / f'{size}.sqlite'
            app = application(path)
            with app.app_context():
                db = get_db()
                for name in CANDIDATE_INDEXES:
                    db.execute(f'DROP INDEX IF EXISTS {name}')
                checksum = seed(db, size)
                db.execute('ANALYZE')
                db.commit()
                datasets.append(dict(size=size, sha256=checksum,
                                     improvement_rows=db.execute('SELECT COUNT(*) FROM improvement').fetchone()[0],
                                     activity_rows=db.execute('SELECT COUNT(*) FROM activity').fetchone()[0],
                                     schema=[dict(r) for r in db.execute("SELECT type,name,sql FROM sqlite_master WHERE sql IS NOT NULL")]))
                expected = None
                # Counterbalance phase order across dataset sizes to reduce systematic drift.
                phases = ('baseline', 'candidate') if args.sizes.index(size) % 2 == 0 else ('candidate', 'baseline')
                if args.reverse_phases:
                    phases = tuple(reversed(phases))
                for phase in phases:
                    for name in CANDIDATE_INDEXES:
                        db.execute(f'DROP INDEX IF EXISTS {name}')
                    if phase == 'candidate':
                        for sql in CANDIDATE_INDEXES.values():
                            db.execute(sql)
                    db.execute('ANALYZE')
                    db.commit()
                    ops = operations(db, size)
                    check = {name: normal(op()) for name, (op, cleanup) in ops.items() if cleanup is None}
                    if expected is None:
                        expected = check
                    else:
                        assert check == expected, f'Index change altered results at {size}: {[k for k in check if check[k] != expected[k]]}'
                        equivalence.append(dict(size=size, baseline_candidate_equal=True))
                    query_plans.extend(plans(db, size, phase))
                    page_size = db.execute('PRAGMA page_size').fetchone()[0]
                    dataset_bytes = db.execute('PRAGMA page_count').fetchone()[0] * page_size
                    live_bytes = dataset_bytes - db.execute('PRAGMA freelist_count').fetchone()[0] * page_size
                    # Warm every workload, then randomise operation order per repetition.
                    for operation, cleanup in ops.values():
                        for _ in range(args.warmups):
                            result = operation()
                            if cleanup:
                                cleanup(result)
                    samples = {name: [] for name in ops}
                    rng = random.Random(927)
                    for repeat in range(args.repeats):
                        names = list(ops)
                        rng.shuffle(names)
                        for name in names:
                            operation, cleanup = ops[name]
                            start = perf_counter_ns()
                            result = operation()
                            elapsed = (perf_counter_ns() - start) / 1e6
                            if cleanup:
                                cleanup(result)
                            samples[name].append(elapsed)
                            raw.append(dict(size=size, phase=phase, operation=name, repeat=repeat, ms=elapsed))
                    for name, values in samples.items():
                        timings.append(dict(size=size, phase=phase, operation=name, unit='ms',
                                            samples=len(values), database_bytes=dataset_bytes,
                                            live_database_bytes=live_bytes, **describe(values)))
                    memops = memory_operations(db)
                    assert normal(memops['sql_filter']()) == normal(memops['python_filter']())
                    for name, op in memops.items():
                        peaks = []
                        for repeat in range(args.memory_repeats):
                            gc.collect()
                            tracemalloc.start()
                            try:
                                result = op()
                                _, peak = tracemalloc.get_traced_memory()
                            finally:
                                tracemalloc.stop()
                            peaks.append(peak)
                            memory_raw.append(dict(size=size, phase=phase, operation=name, repeat=repeat, peak_bytes=peak))
                            del result
                        memory.append(dict(size=size, phase=phase, operation=name, equivalent_results=True,
                                           samples=len(peaks), peak_median_bytes=statistics.median(peaks),
                                           peak_max_bytes=max(peaks)))
                    if size == max(args.sizes):
                        profile_operations(ops, output, f'cpu-{phase}-{size}', args.profile_repeats)
                    print(f'{size:>6} records / {phase}: dashboard median {statistics.median(samples["dashboard"]):.3f} ms', flush=True)
                if size == max(args.sizes):
                    concurrent, probes = concurrency(db, directory, size, output, args.workers,
                                                     args.requests_per_worker, args.concurrency_rounds)
    timing_order = {name: n for n, name in enumerate(('baseline', 'candidate'))}
    timings.sort(key=lambda r: (r['size'], timing_order[r['phase']], r['operation']))
    write_csv(output / 'timings.csv', timings)
    write_csv(output / 'timing-samples.csv', raw)
    write_csv(output / 'memory.csv', memory)
    write_csv(output / 'memory-samples.csv', memory_raw)
    summaries = []
    for journal in ('DELETE', 'WAL'):
        for timeout in (0, 5000):
            for operation in ('read', 'write'):
                selected = [r for r in concurrent if r['journal'] == journal and r['busy_timeout_ms'] == timeout and r['operation'] == operation]
                successes = [r['ms'] for r in selected if not r['error']]
                summaries.append(dict(journal=journal, busy_timeout_ms=timeout, operation=operation,
                                      requests=len(selected), failures=sum(bool(r['error']) for r in selected),
                                      **(describe(successes) if successes else {})))
    write_csv(output / 'concurrency-summary.csv', summaries)
    environment = dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                       processor=platform.processor(), logical_cpus=os.cpu_count(), sqlite=sqlite3.sqlite_version,
                       packages={p: importlib.metadata.version(p) for p in ('Flask', 'pytest', 'pytest-cov', 'ruff', 'matplotlib')},
                       git_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                       working_tree=subprocess.check_output(['git', 'status', '--short'], text=True),
                       source_hashes={str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in
                                      [Path('scripts/benchmark.py'), *Path('app').glob('*.py')]},
                       journal_mode='DELETE', synchronous=2, connection_timeout_seconds=5,
                       timer='perf_counter_ns; milliseconds', percentile='nearest rank ceil(0.95*n)',
                       started_utc=started, finished_utc=datetime.now(timezone.utc).isoformat(),
                       command=' '.join(sys.argv), configuration={k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()})
    results = dict(environment=environment, datasets=datasets, timings=timings, memory=memory,
                   equivalence=equivalence, query_plans=query_plans, concurrency_summary=summaries,
                   lock_probes=probes, candidate_indexes=CANDIDATE_INDEXES)
    (output / 'results.json').write_text(json.dumps(results, indent=2), encoding='utf-8')
    (output / 'query-plans.json').write_text(json.dumps(query_plans, indent=2), encoding='utf-8')
    graphs(output, timings, memory)
    print(f'Results: {output}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sizes', nargs='+', type=int, default=[25, 100, 1000, 10000, 100000])
    parser.add_argument('--reverse-phases', action='store_true', help='Reverse A/B order at every dataset size')
    parser.add_argument('--warmups', type=int, default=3)
    parser.add_argument('--repeats', type=int, default=30)
    parser.add_argument('--memory-repeats', type=int, default=3)
    parser.add_argument('--profile-repeats', type=int, default=5)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--requests-per-worker', type=int, default=12)
    parser.add_argument('--concurrency-rounds', type=int, default=3)
    parser.add_argument('--output', type=Path, default=Path('docs/performance-results') / datetime.now(timezone.utc).strftime('run-%Y%m%d-%H%M%S'))
    args = parser.parse_args()
    if min(args.sizes) < 1 or len(set(args.sizes)) != len(args.sizes):
        parser.error('sizes must be positive and unique')
    if min(args.warmups, args.repeats, args.memory_repeats, args.profile_repeats,
           args.workers, args.requests_per_worker, args.concurrency_rounds) < 1:
        parser.error('all measurement counts must be positive')
    run(args)


if __name__ == '__main__':
    main()
