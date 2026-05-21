# TournamentIQ iOS

Native SwiftUI client for the Tournament IQ staff coordination tool. Targets iOS 17+, universal (iPhone + iPad), talking to the existing FastAPI `/api/v1/*` surface.

## Branch

This directory exists **only on the `ios` branch.** See the top-level `CLAUDE.md` for the full branch model. In short:

- All iOS commits go on `ios`.
- Web/backend changes flow `dev → main`, then `ios` forward-merges `main`.
- `ios` never PRs back into `dev` or `main`.

## Generating the Xcode project

The Xcode project is **not committed** — it's generated from `project.yml` using [XcodeGen](https://github.com/yonaskolb/XcodeGen).

```bash
brew install xcodegen
cd TournamentIQ-iOS
xcodegen
open TournamentIQ.xcodeproj
```

Re-run `xcodegen` after adding new source files or changing `project.yml`.

## Layout

```
TournamentIQ-iOS/
├── project.yml              # XcodeGen spec (committed)
├── TournamentIQ.xcodeproj/  # GENERATED, gitignored
├── TournamentIQ/            # App sources
│   ├── TournamentIQApp.swift
│   ├── App/                 # Environment, dependencies, root view
│   ├── Networking/          # APIClient, endpoints, error types
│   ├── Models/              # Codable domain models
│   ├── Storage/             # Keychain, UserDefaults preferences
│   ├── Features/            # SwiftUI views grouped by feature
│   ├── Design/              # Theme, status/skill badges
│   └── Util/                # Logging, date formatting, helpers
├── TournamentIQTests/       # XCTest unit tests
└── TournamentIQUITests/     # XCUITest smoke-flow tests
```

## Backend

The app talks to bearer-auth endpoints under `/api/v1/*` on the deployed Tournament IQ backend. The hidden debug menu (7 taps on the login logo) toggles between Dev / Prod / Custom URL.

Backend endpoints required but not yet on `main` are listed in the plan; they land on `dev` first and reach `ios` via forward-merge from `main`.

## Status

Scaffold only — no real screens yet. See the implementation plan for the build order.
