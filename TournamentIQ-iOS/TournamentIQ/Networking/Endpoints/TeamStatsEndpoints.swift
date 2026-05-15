import Foundation

struct TeamStatsEndpoints {
    let client: APIClientProtocol

    func teamStats(age: String? = nil, season: String? = nil) async throws -> TeamStatsResponse {
        var query: [URLQueryItem] = []
        if let age, !age.isEmpty { query.append(URLQueryItem(name: "age", value: age)) }
        if let season, !season.isEmpty { query.append(URLQueryItem(name: "season", value: season)) }
        return try await client.send(
            APIRequest(method: .get, path: "/api/v1/team-stats", query: query),
            as: TeamStatsResponse.self
        )
    }

    func teamAnalysis(age: String? = nil, season: String? = nil) async throws -> TeamStatsResponse {
        var query: [URLQueryItem] = []
        if let age, !age.isEmpty { query.append(URLQueryItem(name: "age", value: age)) }
        if let season, !season.isEmpty { query.append(URLQueryItem(name: "season", value: season)) }
        return try await client.send(
            APIRequest(method: .get, path: "/api/v1/team-analysis", query: query),
            as: TeamStatsResponse.self
        )
    }

    func availableSeasons() async throws -> AvailableSeasonsResponse {
        try await client.send(
            APIRequest(method: .get, path: "/api/v1/available-seasons"),
            as: AvailableSeasonsResponse.self
        )
    }
}
