import XCTest
@testable import TournamentIQ

final class DecodingTests: XCTestCase {
    private let decoder = DecodingStrategies.makeDecoder()

    func testLoginResponseDecodes() throws {
        let data = try FixtureLoader.data("login_response")
        let response = try decoder.decode(LoginResponse.self, from: data)

        XCTAssertEqual(response.team.slug, "8u-hawks")
        XCTAssertEqual(response.team.displayName, "8U Hawks")
        XCTAssertFalse(response.session.token.isEmpty)
        XCTAssertNotNil(response.session.expiresAt)
    }

    func testMeResponseDecodes() throws {
        let data = try FixtureLoader.data("me_response")
        let response = try decoder.decode(MeResponse.self, from: data)
        XCTAssertEqual(response.team.slug, "8u-hawks")
    }

    func testTournamentDetailDecodes() throws {
        let data = try FixtureLoader.data("tournament_detail")
        let tournament = try decoder.decode(Tournament.self, from: data)

        XCTAssertEqual(tournament.id, 1)
        XCTAssertEqual(tournament.source, "ncs")
        XCTAssertEqual(tournament.sourceId, "fixture-1")
        XCTAssertEqual(tournament.name, "Spring Classic")
        XCTAssertEqual(tournament.location, "Madison, AL")
        XCTAssertEqual(tournament.director, "Jane Doe")
        XCTAssertEqual(tournament.ageDivisions, ["8U", "8U OPEN", "9U", "9U AA"])
        XCTAssertEqual(tournament.registeredTeams, 12)
        XCTAssertEqual(tournament.divisionTeamCounts?["8U OPEN"], 6)
        XCTAssertEqual(tournament.divisionTeams?["8U OPEN"]?.count, 2)
        XCTAssertEqual(tournament.divisionTeams?["8U OPEN"]?.first?.teamName, "Hawks 8U")
        XCTAssertEqual(tournament.shortlistStatus, "Interested")
        XCTAssertEqual(tournament.shortlistPriority, 2)
        XCTAssertEqual(tournament.shortlistNotes, "front-runner")
        XCTAssertEqual(tournament.selectedAgeDivisions?.first?.division, "8U OPEN")
        XCTAssertEqual(tournament.targetTeamCount, 2)
        XCTAssertEqual(tournament.countWarning, false)

        let startComponents = Calendar(identifier: .gregorian).dateComponents(in: TimeZone(secondsFromGMT: 0)!, from: tournament.startDate!)
        XCTAssertEqual(startComponents.year, 2026)
        XCTAssertEqual(startComponents.month, 6)
        XCTAssertEqual(startComponents.day, 12)

        XCTAssertNotNil(tournament.fetchedAt)
    }

    func testTournamentsListDecodes() throws {
        let data = try FixtureLoader.data("tournaments_list")
        let tournaments = try decoder.decode([Tournament].self, from: data)
        XCTAssertFalse(tournaments.isEmpty)
        XCTAssertTrue(tournaments.contains { $0.name == "Spring Classic" })
    }

    func testSettingsResponseDecodes() throws {
        let data = try FixtureLoader.data("settings_response")
        let response = try decoder.decode(TeamSettingsResponse.self, from: data)
        XCTAssertEqual(response.team.slug, "8u-hawks")
        XCTAssertEqual(response.settings.targetAgeDivision, "8U")
        XCTAssertEqual(response.settings.radiusMiles, 200)
    }

    func testChangesResponseDecodes() throws {
        let data = try FixtureLoader.data("changes_response")
        let events = try decoder.decode([ChangeEvent].self, from: data)
        XCTAssertGreaterThan(events.count, 0)
        XCTAssertEqual(events.first?.field, "created")
        XCTAssertNotNil(events.first?.detectedAt)
    }

    func testTeamStatsResponseDecodes() throws {
        let data = try FixtureLoader.data("team_stats_response")
        let response = try decoder.decode(TeamStatsResponse.self, from: data)
        XCTAssertEqual(response.age, "8U")
        XCTAssertEqual(response.totalTeams, response.teams.count)
        XCTAssertEqual(response.teams.first?.teamName, "Hawks 8U")
        XCTAssertEqual(response.teams.first?.winPct, 0.8, accuracy: 0.0001)
    }

    func testAvailableSeasonsDecodes() throws {
        let data = try FixtureLoader.data("available_seasons_response")
        let response = try decoder.decode(AvailableSeasonsResponse.self, from: data)
        XCTAssertFalse(response.current.isEmpty)
    }

    func testRefreshRunsDecodesEmptyArray() throws {
        let data = try FixtureLoader.data("refresh_runs_response")
        let runs = try decoder.decode([RefreshRun].self, from: data)
        XCTAssertEqual(runs.count, 0)
    }

    func testErrorEnvelopeDecodes() throws {
        let data = try FixtureLoader.data("error_unauthenticated")
        let envelope = try decoder.decode(APIErrorEnvelope.self, from: data)
        XCTAssertEqual(envelope.error.code, "authentication_required")
    }

    func testDateStrategyHandlesAllThreeFormats() throws {
        let payloads: [String: (Int, Int, Int)] = [
            "\"2026-05-15\"": (2026, 5, 15),
            "\"2026-05-15T01:38:58+00:00\"": (2026, 5, 15),
            "\"2026-05-15T01:38:58.394070+00:00\"": (2026, 5, 15)
        ]
        for (raw, expected) in payloads {
            let data = Data(raw.utf8)
            let date = try decoder.decode(Date.self, from: data)
            let comps = Calendar(identifier: .gregorian).dateComponents(in: TimeZone(secondsFromGMT: 0)!, from: date)
            XCTAssertEqual(comps.year, expected.0)
            XCTAssertEqual(comps.month, expected.1)
            XCTAssertEqual(comps.day, expected.2)
        }
    }

    func testDateStrategyRejectsGarbage() {
        let data = Data("\"not-a-date\"".utf8)
        XCTAssertThrowsError(try decoder.decode(Date.self, from: data))
    }
}
