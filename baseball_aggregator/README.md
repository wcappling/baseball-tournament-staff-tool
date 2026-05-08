# Tournament IQ

Staff tool for discovering and shortlisting youth baseball tournaments across NCS, USSSA, and Perfect Game. Runs as a multi-tenant web app and exposes a native `/api/v1` API for iOS clients.

---

## Quick start (local)

```bat
setup.bat   :: creates .venv, installs Python deps, installs Playwright Chromium
test.bat    :: runs all Python tests + Vitest unit tests
run.bat     :: starts the server at http://127.0.0.1:8000
```

No password required locally unless `STAFF_TOOL_PASSWORD` is set. Open `http://127.0.0.1:8000` in a browser.

---

## Environment variables

| Variable | Required | Default | Purpose |
|---|---|---|---|
| `STAFF_TOOL_PASSWORD` | Prod only | — | Enables auth; shared staff password for the web UI |
| `SESSION_SECRET` | Prod only | dev fallback | Signs session cookies (min 32 chars, random) |
| `STAFF_TOOL_DATA_DIR` | Prod | `baseball_aggregator/data` | SQLite database and backup directory |
| `STAFF_TOOL_HOSTED` | Recommended | `false` | Switches secure cookie flag; startup fails without secrets |
| `STAFF_TOOL_ENABLE_HOSTED_JOBS` | Optional | `false` | Enables in-process refresh and backup loops |
| `DEV_AUTO_LOGIN` | Dev only | — | Bypasses login entirely; **never set on prod** |

Copy `.env.example` for a starting point.

---

## Team management

Each team gets its own slug, password, shortlist, notes, and settings. Manage teams from the repo root:

```bash
# Create or update a team
python -m baseball_aggregator.team_admin upsert \
  --slug 8u-hawks \
  --display-name "8U Hawks" \
  --password "<shared team password>" \
  --age 8U \
  --radius 200 \
  --home-label "Huntsville, AL" \
  --enabled-source ncs \
  --enabled-source usssa \
  --enabled-source perfect_game

# List all teams (passwords not shown)
python -m baseball_aggregator.team_admin list
```

Re-run `upsert` with the same `--slug` to update settings or rotate that team's password.

---

## Deploy to Railway

The repo ships `Procfile` and `railway.json` so Railway auto-detects the start command.

**Start command:**
```bash
python -m uvicorn baseball_aggregator.app:app --host 0.0.0.0 --port $PORT
```

**Required Railway variables:**
```
STAFF_TOOL_PASSWORD=<long shared password>
SESSION_SECRET=<long random secret>
STAFF_TOOL_DATA_DIR=/data
```

**Recommended Railway variables:**
```
STAFF_TOOL_HOSTED=true
STAFF_TOOL_ENABLE_HOSTED_JOBS=true
```

Mount a Railway persistent volume at `/data` (or whatever `STAFF_TOOL_DATA_DIR` is set to) so the SQLite database and backups survive redeploys.

Two services are maintained:

| Service | Branch | Purpose |
|---|---|---|
| Tournament IQ Dev | `dev` | Active development; `DEV_AUTO_LOGIN=true` set here |
| Tournament IQ Prod | `main` | Production; no `DEV_AUTO_LOGIN` |

All feature PRs target `dev`. Production releases are batched merges from `dev → main`.

---

## Password rotation

Change `STAFF_TOOL_PASSWORD` in Railway to rotate the shared web-UI password. Rotate `SESSION_SECRET` at the same time to invalidate all current logged-in sessions. Cookies are `httponly`, signed with HMAC-SHA256, and valid for 30 days.

---

## Data sources

| Source | Status | Team records |
|---|---|---|
| NCS | Live | WhosComing pages + Teams listing scraper |
| USSSA | Live | API-backed; seeding reports per division |
| Perfect Game | Live | API-backed; team lists per division event |
| Grand Slam | Deferred | Post-MVP; hidden from active source filters |

A manual refresh can be triggered from the Settings panel in the UI or via `POST /api/refresh`. The hosted refresh loop runs every 6 hours (configurable per team). Team lists (records) are hydrated automatically during refresh.

---

## Backups

When `STAFF_TOOL_ENABLE_HOSTED_JOBS=true` the app creates a SQLite backup at UTC midnight and retains the 7 most recent files at:

```
<STAFF_TOOL_DATA_DIR>/backups/
```

To restore: stop the app, replace `<STAFF_TOOL_DATA_DIR>/baseball_staff_tool.sqlite3` with the chosen backup, restart.

---

## Project layout

```
baseball_aggregator/
  app.py              FastAPI application — all HTTP endpoints
  auth.py             Session middleware, cookie signing, bearer token auth
  config.py           Environment variable helpers
  models.py           Tournament dataclass, DEFAULT_SETTINGS
  storage.py          SQLite schema, all queries, settings, shortlist, changes
  stats.py            W-L-T aggregation engine
  services.py         Refresh orchestration, team hydration
  maintenance.py      Backup creation and pruning
  refresh_loop.py     Optional standalone refresh cadence runner
  team_admin.py       CLI for managing team accounts
  collectors/         Source adapters (ncs, usssa, perfect_game)
  scrapers/           Direct HTML scrapers (ncs_teams)
  static/             SPA frontend (index.html, app.js, utils.js, styles.css)
  tests/              Backend tests (pytest) and frontend tests (Vitest + Playwright)
  data/               Local SQLite database — created on first run
```

See [ARCHITECTURE.md](../ARCHITECTURE.md) for a deeper walkthrough.

---

## UI captures

```bat
demo.bat
```

Starts the app with a temporary database, seeds sample data, and writes screenshots + WebM recordings to `.tmp/ui-demos`. Linux/CI equivalent:

```bash
python -m pip install -r requirements.txt -r requirements-dev.txt
python -m playwright install --with-deps chromium
python scripts/capture_ui_demo.py
```

---

## API

The web app uses cookie-authenticated routes under `/api/*`.

A native (iOS) client uses token-authenticated routes under `/api/v1/*`. See [docs/api.md](../docs/api.md) for the full reference.

---

## Tests

```bash
python -m pytest          # 64 Python backend tests
npm test                  # 74 Vitest unit tests (pure JS functions)
python -m pytest baseball_aggregator/tests/frontend/e2e/  # 8 Playwright E2E tests
```

See [docs/testing.md](../docs/testing.md) for details on each suite.
