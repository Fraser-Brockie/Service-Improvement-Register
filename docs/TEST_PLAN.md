# Test plan

Unit tests target validation, creation, status rules and dashboard aggregation. Integration tests use Flask's test client to exercise HTTP input/output, persistence, filtering, redirects and 404 handling. SQLite is isolated to a temporary database per test fixture. Regression command: `pytest -q --cov=app --cov-report=term-missing`.

Risk-based cases include invalid enum values, boundary title length, unknown record IDs and unknown routes. Manual acceptance testing should also check keyboard navigation, form labels and the production command.
