"""Reproducible synthetic-data benchmark; never opens the application database."""

import json
import sys
import tempfile
from pathlib import Path
from time import perf_counter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import create_app
from app.db import get_db
from app import repository

with tempfile.TemporaryDirectory() as directory:
    app = create_app({"TESTING": True, "DATABASE": str(Path(directory) / "bench.sqlite")})
    with app.app_context():
        db = get_db()
        db.executemany(
            "INSERT INTO improvement(title,category,priority) VALUES (?,'Process','High')",
            ((f"Synthetic {n}",) for n in range(10000)),
        )
        db.commit()
        results = {}
        for name, operation in {
            "full_list": lambda: repository.list_items(),
            "page_10": lambda: repository.search_items({}, 1),
            "metrics": repository.metrics,
        }.items():
            start = perf_counter()
            for _ in range(20):
                operation()
            results[name + "_mean_ms"] = round((perf_counter() - start) * 1000 / 20, 3)
        results["records"] = 10000
        results["page_query_plan"] = [
            tuple(row)
            for row in db.execute(
                "EXPLAIN QUERY PLAN SELECT * FROM improvement WHERE archived=0 AND status='New' ORDER BY id DESC LIMIT 10"
            )
        ]
        print(json.dumps(results, indent=2))
