# Testing — Tournament IQ

Three suites cover different layers: Python backend logic, JavaScript pure functions, and browser E2E flows.

---

## Running all tests

```bash
# Python backend (64 tests)
python -m pytest

# JavaScript unit tests (74 tests)
npm test

# Playwright E2E (8 tests)
python -m pytest baseball_aggregator/tests/frontend/e2e/ -v
```

---

## Python backend tests

**Runner:** pytest  
**Location:** `baseball_aggregator/tests/`  
**Count:** 64

### What's covered

| File | Tests |
|---|---|
| `test_collectors.py` | HTML/JSON parsers for all three sources; division normalization; team hydration enrichment (PG + USSSA, including HTTP error paths) |
| `test_storage_api.py` | SQLite upsert, shortlist CRUD, change-log recording, settings read/write, team isolation |
| `test_hosted_mvp.py` | Hosted-mode startup assertions, auth middleware bypass rules |
| `test_ncs_teams_scraper.py` | NCS Teams listing scraper |
| `test_team_admin_cli.py` | `team_admin` CLI upsert/list commands |
| `test_team_scoped_ios_readiness.py` | Multi-team data isolation |
| `test_distance.py` | ZIP-code distance calculations |

### Fixtures

HTML/JSON fixtures for parsers are in `baseball_aggregator/tests/fixtures/`. Network calls are never made during unit tests — either fixtures are parsed directly or `unittest.mock.patch` intercepts HTTP calls.

### Running a subset

```bash
python -m pytest baseball_aggregator/tests/test_collectors.py -v
python -m pytest -k "usssa" -v
```

---

## JavaScript unit tests

**Runner:** Vitest 2  
**Location:** `baseball_aggregator/tests/frontend/unit/utils.test.js`  
**Count:** 74

### What's covered

All 15 pure functions in `baseball_aggregator/static/utils.js`:

| Function | Tests |
|---|---|
| `escapeHtml` | Ampersand, `<`, `>`, double-quote, single-quote, null/undefined, XSS payload |
| `sourceLabel` | All three sources + unknown passthrough |
| `formatDate` | TBD, single date, range, no end |
| `formatDistance` | null/undefined → "Unknown", rounding |
| `formatWinPct` | null/NaN/undefined → "—", 0, 0.5, 1.0 |
| `skillLevel` | All three sources × all tier levels + unknown source/division |
| `statusClass` | null/Watch → "status-open", Interested, Registered, Declined |
| `normalizeHex` | With/without `#`, invalid → fallback |
| `hexToRgb` / `rgbToHex` | Black, white, brand teal, roundtrip |
| `mixHex` | Weight 0/0.5/1 endpoints, clamp below 0 and above 1 |
| `relativeLuminance` | Black = 0, white ≈ 1, mid-gray in range |
| `contrastRatio` | Black/white ≈ 21, same color = 1, symmetry |
| `teamThemeTokens` | All required CSS vars present, dark ≠ light, fallback defaults, on-primary contrast |

### How it works

`utils.js` is loaded into a Node.js `vm.createContext()` sandbox using `vm.Script`. This lets Vitest test the plain `<script>` globals without converting `utils.js` to ES modules.

### Running

```bash
npm test           # single run
npm run test:watch # watch mode
```

Node.js must be on PATH. If not installed, download from nodejs.org or extract the ZIP to a local directory and add it to PATH.

---

## Playwright E2E tests

**Runner:** pytest + playwright  
**Location:** `baseball_aggregator/tests/frontend/e2e/`  
**Count:** 8

### What's covered

| Test | What it checks |
|---|---|
| `test_page_loads_title` | `<title>Tournament IQ</title>` present |
| `test_sidebar_nav_links_present` | "Tournaments" nav link visible |
| `test_tournaments_table_renders` | `#tournamentsTable` visible after load |
| `test_view_switching_shows_correct_section` | Clicking Team Analysis shows the analysis section |
| `test_theme_toggle_persists` | Toggle changes theme; reload preserves it in localStorage |
| `test_no_js_errors_on_load` | Zero `pageerror` events during initial load |
| `test_filter_controls_are_interactive` | Filter controls are visible and interactive |
| `test_shortlist_status_dropdown_present` | Status select visible when table has rows |

### Server fixture

`conftest.py` starts a real uvicorn server on port 18765 with `DEV_AUTO_LOGIN=true` and a temp SQLite directory. The fixture polls until the server accepts connections (up to 15 s) then yields the base URL. The server is terminated after the session.

This means E2E tests hit the real FastAPI app with a real (empty) database.

### Running

```bash
# Install Playwright browser if not already installed
python -m playwright install chromium

python -m pytest baseball_aggregator/tests/frontend/e2e/ -v
```

---

## Test matrix

| Layer | Framework | Command | Count |
|---|---|---|---|
| Backend | pytest | `python -m pytest` | 64 |
| JS utils | Vitest | `npm test` | 74 |
| Browser E2E | Playwright | `python -m pytest baseball_aggregator/tests/frontend/e2e/` | 8 |
| **Total** | | | **146** |

---

## Adding tests

**New parser test** — add a fixture HTML/JSON file to `tests/fixtures/` and a test function in `test_collectors.py`. Mock any HTTP calls with `unittest.mock.patch`.

**New JS utility** — add the function to `baseball_aggregator/static/utils.js` as a plain function declaration, then add `describe`/`it` blocks to `utils.test.js`.

**New E2E flow** — add a `def test_*` function to `test_ui_flows.py`. The `page` fixture provides a fresh Playwright page for each test; `live_server` provides the base URL.
