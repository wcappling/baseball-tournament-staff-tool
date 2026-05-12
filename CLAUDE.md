# Tournament IQ — Claude Code Notes

## Branch & Deployment Strategy

| Environment | Railway Service | GitHub Branch | When to merge |
|---|---|---|---|
| Dev | Tournament IQ Dev | `dev` | All active development PRs |
| Prod | Tournament IQ Prod | `main` | Large batch releases from `dev` when stable |

**All feature PRs target `dev`.** Never create a PR targeting `main` unless explicitly requested for a production release.

Railway auto-deploys from the connected branch on push — merging a PR to `dev` automatically redeploys Tournament IQ Dev. No separate trigger PR is needed.

## Repository Layout

- `baseball_aggregator/app.py` — FastAPI application, all HTTP endpoints
- `baseball_aggregator/stats.py` — Team record aggregation logic
- `baseball_aggregator/storage.py` — SQLite persistence layer (tournaments, shortlist, settings)
- `baseball_aggregator/static/` — Single-page frontend (index.html, app.js, styles.css)
- `tests/` — pytest test suite

## Railway Environment Variables

| Variable | Service | Value | Purpose |
|---|---|---|---|
| `DEV_AUTO_LOGIN` | Tournament IQ Dev only | `true` | Bypasses the login screen entirely — any browser hits the dev URL without a password |
| `STAFF_TOOL_PASSWORD` | Both | (secret) | Shared staff password; also enables auth when set |
| `SESSION_SECRET` | Both | (secret) | Signs session cookies |
| `STAFF_TOOL_DATA_DIR` | Both | (path) | SQLite data directory |

Never set `DEV_AUTO_LOGIN` on the Prod service.

## Development Notes

- Run tests: `python -m pytest`
- The shortlist table tracks per-team tournament interest (status: Watch / Interested / Registered / Declined)
- `division_teams` column stores scraped team lists as JSON; only populated after hydration
- Team stats (`/api/team-stats`) aggregate across all hydrated tournaments; team analysis (`/api/team-analysis`) filters to Interested/Registered only
