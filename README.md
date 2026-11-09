# Anonymous Service Improvement Register

A small Flask application created for the Advanced Programming summative. The scenario is deliberately fictional and organisation-neutral.

## Quick start (PyCharm terminal)
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
flask --app app run --debug
```
Open http://127.0.0.1:5000

## Tests
```bash
pytest -q
pytest --cov=app --cov-report=term-missing
```

See `docs/SDLC.md`, `docs/KSB_MATRIX.md`, `docs/COMMIT_TRAIL.md` and `docs/TEST_PLAN.md`.
