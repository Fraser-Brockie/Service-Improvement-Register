"""Correctness controls for performance comparisons; no timing thresholds."""
from scripts.benchmark import CANDIDATE_INDEXES, describe, memory_operations, operations, normal, seed, concurrency
from app import repository
from app.db import get_db


def test_benchmark_equivalence_and_cleanup(app):
    with app.app_context():
        db = get_db()
        seed(db, 25)
        methods = memory_operations(db)
        assert normal(methods['sql_filter']()) == normal(methods['python_filter']())
        before = [dict(r) for r in db.execute('SELECT * FROM improvement ORDER BY id')]
        history = [dict(r) for r in db.execute('SELECT * FROM activity ORDER BY id')]
        for operation, cleanup in operations(db, 25).values():
            result = operation()
            if cleanup:
                cleanup(result)
        assert [dict(r) for r in db.execute('SELECT * FROM improvement ORDER BY id')] == before
        assert [dict(r) for r in db.execute('SELECT * FROM activity ORDER BY id')] == history


def test_stable_sorted_pages_across_indexes(app):
    with app.app_context():
        db = get_db()
        seed(db, 25)
        db.execute("UPDATE improvement SET due_date='2026-01-01', title='Equal title'")
        db.commit()
        expected = [r[0] for r in db.execute('SELECT id FROM improvement WHERE archived=0 ORDER BY id')]
        for name in CANDIDATE_INDEXES:
            db.execute(f'DROP INDEX IF EXISTS {name}')
        for phase in ('baseline', 'candidate'):
            if phase == 'candidate':
                for sql in CANDIDATE_INDEXES.values():
                    db.execute(sql)
                db.commit()
            for sort in ('title', 'due'):
                result = []
                for page in (1, 2, 3):
                    rows, total = repository.search_items({'sort': sort}, page)
                    result.extend(r['id'] for r in rows)
                assert result == expected
                assert total == len(expected)


def test_percentile_nearest_rank():
    result = describe(list(range(1, 21)))
    assert result == dict(mean=10.5, median=10.5, minimum=1, maximum=20, p95=19)


def test_concurrent_workloads_are_isolated(app, tmp_path):
    with app.app_context():
        db = get_db()
        seed(db, 25)
        before = [dict(r) for r in db.execute('SELECT * FROM improvement ORDER BY id')]
        rows, probes = concurrency(db, tmp_path, 25, tmp_path, 2, 2, 1)
        assert len(rows) == 16
        assert all(not r['error'] for r in rows if r['busy_timeout_ms'] == 5000)
        assert len(probes) == 4
        assert all(p['error'] == 'database is locked' for p in probes)
        assert [dict(r) for r in db.execute('SELECT * FROM improvement ORDER BY id')] == before
        assert db.execute('SELECT COUNT(*) FROM app_user').fetchone()[0] == 0
