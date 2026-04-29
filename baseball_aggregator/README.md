# Baseball Tournament Staff Tool

Staff-only web app for discovering and shortlisting baseball tournaments across
NCS, USSSA, and Perfect Game.

V1 defaults to a Huntsville, AL team profile, a 200-mile radius, an 8U target
division, dark mode, and a 4-team highlight threshold.

## Quick start

From the repository root:

```bat
setup.bat
test.bat
run.bat
```

Then open <http://127.0.0.1:8000>.

Local development does not require a password unless `STAFF_TOOL_PASSWORD` is
set.

## Current status

| Source | Status | Notes |
|---|---|---|
| NCS | Live collector + parser | Uses public event pages and Who's Coming pages for age-bracket team counts. |
| USSSA | Live API-backed collector + parser | Uses public event search and division endpoints for team-entered and approved counts. |
| Perfect Game | Live collector + parser | Uses public search data and lazy team-list loading from event pages. |
| Grand Slam | Deferred | Planned after the shareable web MVP and iOS path. Hidden from active source filters. |

## Staff-shareable Railway deploy

The recommended first hosted release is Railway Hobby with a Railway-generated
URL and a persistent volume for SQLite.

Railway start command from the repository root:

```bash
python -m uvicorn baseball_aggregator.app:app --host 0.0.0.0 --port $PORT
```

This repository includes both `Procfile` and `railway.json` with that start
command, plus root-level `requirements.txt` and `.python-version` files so
Railway detects the app as Python.

Required Railway variables:

```text
STAFF_TOOL_PASSWORD=<shared staff password>
SESSION_SECRET=<long random secret>
STAFF_TOOL_DATA_DIR=/data
```

Recommended Railway variables:

```text
STAFF_TOOL_HOSTED=true
STAFF_TOOL_ENABLE_HOSTED_JOBS=true
```

Railway also sets `RAILWAY_ENVIRONMENT`; when hosted mode is detected, startup
fails clearly unless password, session secret, and data directory are configured.
Mount the Railway volume at the same path used by `STAFF_TOOL_DATA_DIR`, such as
`/data`, so the SQLite database and backups survive redeploys.

## Password rotation

Change `STAFF_TOOL_PASSWORD` in Railway to rotate the shared password for new
logins. Rotate `SESSION_SECRET` at the same time when current logged-in staff
sessions should be invalidated. Session cookies are HTTP-only, signed, and valid
for 30 days.

## Backups and restore

Hosted jobs run inside the app process when `STAFF_TOOL_ENABLE_HOSTED_JOBS=true`.
They refresh sources every 6 hours based on the app settings and create a SQLite
backup at UTC midnight each day. The newest 7 backup files are retained under:

```text
<STAFF_TOOL_DATA_DIR>/backups
```

To restore, stop the app, replace `<STAFF_TOOL_DATA_DIR>/baseball_staff_tool.sqlite3`
with the chosen backup file, then restart the app.

## Project layout

```text
baseball_aggregator/
  app.py                  FastAPI app and API routes
  models.py               Normalized tournament model and defaults
  storage.py              SQLite schema, persistence, settings, shortlist, changes
  services.py             Refresh orchestration
  refresh_loop.py         Optional 6-hour local refresh loop
  collectors/             Source adapters
  static/                 Browser UI
  tests/                  Offline parser, storage, and API tests
  data/                   Local SQLite database, created automatically
```

## Core behavior

- Dense sortable tournament table with source, date, location, age, team count,
  status, and notes.
- Team-count-first comparison with a default 4+ team threshold.
- NCS bracket-level counts from Who's Coming pages, with event-level fallback.
- Warning when only event-level team count is known.
- Shortlist statuses: Watch, Interested, Registered, Declined.
- Local change log for newly discovered tournaments and tracked field changes.
- Manual refresh endpoint and optional `python -m baseball_aggregator.refresh_loop`
  cadence runner.

## API sketch

- `GET /api/settings`
- `PUT /api/settings`
- `GET /api/tournaments`
- `GET /api/divisions`
- `POST /api/refresh`
- `POST /api/tournaments/{id}/teams`
- `GET /api/changes`
- `GET /api/refresh-runs`
- `PUT /api/tournaments/{id}/shortlist`

## Next source work

NCS, USSSA, and Perfect Game are the live V1 sources. Grand Slam remains a
deferred post-MVP source so staff are not confused by an active filter with no
results.
