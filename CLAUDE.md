# Tournament IQ — Claude Code Notes

## Branch & Deployment Strategy

| Branch | Purpose | Receives changes from | Deploys to |
|---|---|---|---|
| `dev` | Active feature development | Feature PRs from short-lived branches | Tournament IQ Dev (Railway) |
| `main` | Stable production releases | Promoted from `dev` in batches | Tournament IQ Prod (Railway) |
| `ios` | iOS app source + snapshot of backend the app ships against | Forward-merges from `main`; direct iOS-only commits | Xcode / TestFlight builds |

**All web/backend feature PRs target `dev`.** Never create a PR targeting `main` unless explicitly requested for a production release.

Railway auto-deploys from the connected branch on push — merging a PR to `dev` automatically redeploys Tournament IQ Dev. No separate trigger PR is needed.

### iOS branch rules

- `ios` is **long-lived** and was created from `main`.
- All commits under `/TournamentIQ-iOS/` go directly on `ios` (or via short-lived branches that PR into `ios`).
- `ios` never PRs back into `dev` or `main`.
- To pick up backend / web changes, `ios` does a forward `git merge origin/main` periodically. Flow for shared changes is `dev → main → ios`.
- New backend endpoints required by the iOS app (e.g. `/api/v1/*` bearer-auth forwarders) land on `dev` first, promote to `main`, then arrive on `ios` via the next forward-merge. They may be cherry-picked onto `ios` short-term to unblock app development.
- TestFlight / App Store builds are cut from tags on the `ios` branch.

## Repository Layout

- `baseball_aggregator/app.py` — FastAPI application, all HTTP endpoints
- `baseball_aggregator/stats.py` — Team record aggregation logic
- `baseball_aggregator/storage.py` — SQLite persistence layer (tournaments, shortlist, settings)
- `baseball_aggregator/static/` — Single-page frontend (index.html, app.js, styles.css)
- `tests/` — pytest test suite
- `TournamentIQ-iOS/` — Native iOS app (Swift / SwiftUI). Only present on the `ios` branch. Generates an `.xcodeproj` from `project.yml` via XcodeGen; do not commit the generated project.

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
