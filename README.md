# Service Improvement Register ? Lloyds Banking Group themed demo

A fictional, organisation-neutral Flask/SQLite register with a responsive Bootstrap 5.3 dashboard, charts, search/filter/sort/pagination, editable request details, activity timelines and safeguarded archiving.

## VS Code / Windows installation

Open this folder in VS Code. Install Python 3.12 or later and the Python extension. In a PowerShell terminal:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1
```

Select `.venv/Scripts/python.exe` with Python: Select Interpreter. Open http://127.0.0.1:5000. No activation or PowerShell execution-policy changes are needed. Debug mode is optional for local development only.

The default database is `instance/improvements.sqlite`. On startup, additive migrations retain existing records. Stop the application and back up its database before upgrading. `DATABASE` overrides the path; `SECRET_KEY` supplies a stable random deployment secret; `HTTPS_ONLY=1` enables Secure cookies when using HTTPS. Without SECRET_KEY, a stable local secret is generated in instance/.session-secret. Keep this file private and out of source control.

Optional fictional demo data (refuses a populated register):

```powershell
$env:DATABASE = "$PWD\instance\demo.sqlite"
.\.venv\Scripts\python.exe -m flask --app app seed-demo
.\.venv\Scripts\python.exe -m flask --app app run --host 127.0.0.1
```

## Verification

```powershell
.\.venv\Scripts\python.exe -m pytest --cov=app --cov-report=term-missing
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe scripts/dependency_snapshot.py
.\.venv\Scripts\python.exe -m pip_audit -r docs/dependencies-resolved.txt --no-deps --disable-pip
.\.venv\Scripts\python.exe scripts/benchmark.py
```

For a local Waitress demonstration: `.venv\Scripts\waitress-serve.exe --host=127.0.0.1 --call app:create_app`. This is not shared-deployment approval: company SSO and role-based permissions are absent. Bootstrap and Chart.js use pinned jsDelivr URLs and need network access; core server-rendered figures remain available without charts.

Documentation: [requirements](docs/REQUIREMENTS.md), [architecture](docs/ARCHITECTURE.md), [schema/migration](docs/DATABASE.md), [user guide](docs/USER_GUIDE.md), [testing](docs/TEST_PLAN.md), [security](docs/SECURITY.md), [performance](docs/PERFORMANCE.md), [SDLC](docs/SDLC.md), [assessment evidence](docs/KSB_MATRIX.md), [AI assistance](docs/AI_ASSISTANCE.md), [release gates](docs/RELEASE_CHECKLIST.md).

## Banking demonstration

An unofficial portfolio demonstration, not a Lloyds Banking Group system or endorsement. Do not enter real customer, account or confidential company information. Existing records are retained through additive database migrations.

Requests capture business area, customer journey, channel, accountable team, risk category, customer outcome, baseline/target/actual measures, approver, review date and governance stage. Governance records decisions; company SSO, role permissions and enforced approvals remain future production work. Existing delivery statuses remain available alongside the governance stage.

The logo is sourced from https://www.lloydsbankinggroup.com/assets/images/site-wide/logos/lbg-2025/lbg-logo-2025-cancara.svg and remains the property of its owner. Colours are a themed interpretation rather than a certified brand implementation. The seed-demo command creates eight fictional banking scenarios only in an empty database.

## Community Q&A

Open `/community` or choose Community Q&A in the sidebar. Colleagues can post questions, add plain-text answers, search titles and details, filter by topic or unanswered questions, and browse paginated results. Posts are stored in SQLite alongside the register; additive migrations retain existing records. Validation, escaped rendering and the existing CSRF protection apply to posting.

New posts use the signed-in account name and user ID; older posts retain their original attribution. This local demonstration has no moderation or role permissions; peer answers are not approved bank guidance. Use fictional examples only.

## User accounts

Restart the app and choose Create account on the sign-in page. Register with an email, display name and a unique password of 12?128 characters, then sign in. All register and community pages require authentication. Every registered user can use the shared register and post questions/answers; there are no administrator or approver roles. New Q&A posts store the authenticated user ID and account display name; submitted author names are ignored. Existing records and posts are retained, without assigning historical posts to new accounts.

Passwords use Werkzeug's salted scrypt hashing. Sessions use random tokens stored as hashes in SQLite, expire after eight hours, and are revoked server-side on sign-out. Forms require CSRF tokens. Five failed sign-ins for an email within fifteen minutes trigger a temporary limit; registration is also limited to five attempts per IP within fifteen minutes. Account email addresses are case-insensitive and unique. Dynamic pages use no-store caching.

This is local app authentication, not Lloyds SSO. Registration is open and email addresses are not verified; password reset, MFA, company identity integration and role-based access are not implemented. Do not reuse bank credentials. For HTTPS deployment, configure SECRET_KEY and HTTPS_ONLY=1. Preserve the database and local session secret between restarts.


## Performance evaluation

The isolated performance suite evaluates 25, 100, 1,000, 10,000 and 100,000 synthetic records. It exports raw and summary CSV/JSON, cProfile/pstats reports, tracemalloc measurements, SQLite query plans, concurrent authenticated request results and labelled PNG/SVG graphs. It never opens the demonstration database.

Git Bash commands:

```bash
./.venv/Scripts/python.exe -m pip install -r requirements-performance.txt
./.venv/Scripts/python.exe scripts/benchmark.py --output docs/performance-results/my-new-run
./.venv/Scripts/python.exe scripts/benchmark.py --reverse-phases --output docs/performance-results/my-confirmation-run
```

Use new output directories. For the exact captured dependency environment, use `requirements-performance-lock.txt` instead of the direct-dependency performance requirements. See [the measured report](docs/PERFORMANCE.md) for methods, results, trade-offs, limitations, reproduction commands, assessment mapping and required screenshots. The optional plotting dependencies are not required to run the application.
