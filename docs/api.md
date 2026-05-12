# Native API Reference — Tournament IQ

The native API (`/api/v1/`) is designed for the iOS client. All requests and responses are JSON. All endpoints except `/api/v1/login` require a bearer token.

---

## Authentication

### Login

```
POST /api/v1/login
Content-Type: application/json

{
  "team_slug": "8u-hawks",
  "password": "<team password>"
}
```

**Success (200)**
```json
{
  "team": {
    "id": "a1b2c3d4-...",
    "slug": "8u-hawks",
    "display_name": "8U Hawks"
  },
  "session": {
    "token": "<bearer token>",
    "expires_at": "2026-06-07T12:00:00+00:00"
  }
}
```

**Failure (401)**
```json
{ "error": { "code": "invalid_credentials", "message": "Invalid team login." } }
```

Store the `token` value and send it as `Authorization: Bearer <token>` on every subsequent request. Tokens expire after 30 days.

### Error format

All `/api/v1/` errors use this shape:

```json
{ "error": { "code": "snake_case_code", "message": "Human-readable message." } }
```

Common codes:

| Code | HTTP | Meaning |
|---|---|---|
| `authentication_required` | 401 | No bearer token supplied |
| `invalid_session` | 401 | Token expired or revoked |
| `not_found` | 404 | Resource does not exist |
| `invalid_parameter` | 400 | Malformed request body/param |

### Logout

```
POST /api/v1/logout
Authorization: Bearer <token>
```

Revokes the token immediately. Returns `{ "status": "ok" }`.

### Session info

```
GET /api/v1/me
Authorization: Bearer <token>
```

```json
{
  "team": { "id": "...", "slug": "8u-hawks", "display_name": "8U Hawks" },
  "session": { "expires_at": "2026-06-07T12:00:00+00:00" }
}
```

---

## Settings

### Get settings

```
GET /api/v1/settings
Authorization: Bearer <token>
```

```json
{
  "team": { "id": "...", "slug": "8u-hawks", "display_name": "8U Hawks" },
  "settings": {
    "home_zip": "35801",
    "home_label": "Huntsville, AL",
    "radius_miles": 200,
    "target_age_division": "8U",
    "team_count_threshold": 4,
    "refresh_cadence_hours": 6,
    "enabled_sources": ["ncs", "usssa", "perfect_game"],
    "brand_primary": "#0f766e",
    "brand_secondary": "#115e59",
    "brand_accent": "#0ea5a2",
    "logo_url": ""
  }
}
```

### Update settings

```
PUT /api/v1/settings
Authorization: Bearer <token>
Content-Type: application/json

{
  "radius_miles": 300,
  "target_age_division": "10U",
  "team_count_threshold": 6
}
```

All fields are optional. Only the fields you send are updated. Returns the same shape as GET settings.

Writable fields:

| Field | Type | Notes |
|---|---|---|
| `home_zip` | string | ZIP code for distance calculations |
| `home_label` | string | Display label, e.g. "Huntsville, AL" |
| `radius_miles` | int ≥ 1 | Search radius |
| `target_age_division` | string | e.g. "8U", "10U", "12U" |
| `team_count_threshold` | int ≥ 1 | Minimum teams to highlight a division |
| `refresh_cadence_hours` | int ≥ 1 | Auto-refresh interval (hosted only) |
| `enabled_sources` | string[] | Subset of `["ncs", "usssa", "perfect_game"]` |
| `brand_primary` | hex string | Theme color |
| `brand_secondary` | hex string | Theme color |
| `brand_accent` | hex string | Theme color |
| `logo_url` | string | Team logo URL |

---

## Tournaments

### List tournaments

```
GET /api/v1/tournaments
Authorization: Bearer <token>
```

Optional query parameters:

| Param | Type | Example | Notes |
|---|---|---|---|
| `source` | string | `ncs` | Filter by source |
| `age` | string | `10U` | Filter by age division |
| `division` | string (repeatable) | `division=10U+AA&division=10U+AAA` | Filter by specific division(s) |
| `threshold` | int | `6` | Override team_count_threshold for this request |
| `radius_miles` | int | `150` | Override radius for this request |
| `start_on_or_after` | date string | `2026-06-01` | Filter tournaments starting on/after date |
| `end_on_or_before` | date string | `2026-08-31` | Filter tournaments ending on/before date |
| `q` | string | `world series` | Full-text name search |

**Response** — array of tournament objects:

```json
[
  {
    "id": 42,
    "source": "usssa",
    "source_id": "407473",
    "name": "Bat To The Future",
    "detail_url": "https://usssa.com/baseball/event_home/?eventID=407473",
    "location": "Oxford, MS",
    "start_date": "2026-05-01",
    "end_date": "2026-05-03",
    "distance_miles": 143,
    "age_divisions": ["10U", "10U OPEN", "10U AA", "12U", "12U AA"],
    "target_count": 12,
    "count_scope": "division",
    "registered_teams": 91,
    "division_team_counts": { "10U OPEN": 8, "10U AA": 12, "10U": 20 },
    "stature": "USSSA NIT",
    "format": "Pool to 3GG",
    "shortlist": {
      "status": "Interested",
      "priority": 2,
      "notes": "Good venue, check field count"
    }
  }
]
```

`target_count` is the team count for the team's configured `target_age_division` (or the age filter if provided). `count_scope` is `"division"` when a division-level count is known, `"event"` for event-level fallback.

### Get tournament detail

```
GET /api/v1/tournaments/{id}
Authorization: Bearer <token>
```

Optional query params: `age`, `division` (same as list).

Returns a single tournament with full `division_teams`, `division_details`, and shortlist info. Returns 404 if not found.

### Hydrate team lists

```
POST /api/v1/tournaments/{id}/teams?age=10U
Authorization: Bearer <token>
```

Fetches team lists from the source for any un-populated divisions at `age`. Writes them to the database. Returns the updated tournament detail (same shape as GET detail).

This is an on-demand complement to the automatic hydration that runs during refresh.

### Update shortlist

```
PUT /api/v1/tournaments/{id}/shortlist
Authorization: Bearer <token>
Content-Type: application/json

{
  "status": "Interested",
  "priority": 2,
  "notes": "Good venue, check field count"
}
```

`status` must be one of: `Watch`, `Interested`, `Registered`, `Declined`.  
`priority` is 1–5 (default 3).  
`notes` is free text (default empty string).

Returns the updated shortlist record.

---

## Divisions

```
GET /api/v1/divisions?age=10U&source=usssa
Authorization: Bearer <token>
```

Returns distinct divisions in the database filtered by the team's `target_age_division` (overridden by `age` param) and optionally by `source`.

---

## Refresh

```
POST /api/v1/refresh
Authorization: Bearer <token>
```

Triggers an immediate refresh of all sources enabled for this team. Returns a summary dict keyed by source:

```json
{
  "ncs":          { "status": "success", "inserted": 3, "updated": 12, "unchanged": 41 },
  "usssa":        { "status": "success", "inserted": 1, "updated": 4,  "unchanged": 28 },
  "perfect_game": { "status": "success", "inserted": 0, "updated": 2,  "unchanged": 17 }
}
```

If a refresh is already running: `{ "status": "skipped", "message": "Refresh already running" }`.

---

## Change log

```
GET /api/v1/changes?limit=50
Authorization: Bearer <token>
```

Returns up to `limit` (max 500, default 50) recent change-log entries:

```json
[
  {
    "id": 1,
    "tournament_id": 42,
    "tournament_name": "Bat To The Future",
    "source": "usssa",
    "change_type": "new",
    "field": null,
    "old_value": null,
    "new_value": null,
    "detected_at": "2026-05-08T10:00:00+00:00"
  }
]
```

`change_type` is `"new"` (first discovery) or `"updated"` (field changed). `field`, `old_value`, `new_value` are set for `"updated"` entries.

---

## Refresh runs

```
GET /api/v1/refresh-runs
Authorization: Bearer <token>
```

Returns the most recent refresh run per source:

```json
[
  {
    "source": "ncs",
    "started_at": "2026-05-08T10:00:00+00:00",
    "finished_at": "2026-05-08T10:00:14+00:00",
    "status": "success",
    "message": "OK",
    "tournament_count": 56
  }
]
```
