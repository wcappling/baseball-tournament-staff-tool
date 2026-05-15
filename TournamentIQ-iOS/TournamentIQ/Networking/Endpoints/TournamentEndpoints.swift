import Foundation

struct TournamentEndpoints {
    let client: APIClientProtocol

    func list(filters: TournamentFilters) async throws -> [Tournament] {
        try await client.send(
            APIRequest(method: .get, path: "/api/v1/tournaments", query: filters.queryItems),
            as: [Tournament].self
        )
    }

    func detail(id: Int, age: String? = nil, divisions: [String] = []) async throws -> Tournament {
        var query: [URLQueryItem] = []
        if let age, !age.isEmpty { query.append(URLQueryItem(name: "age", value: age)) }
        for division in divisions { query.append(URLQueryItem(name: "division", value: division)) }
        return try await client.send(
            APIRequest(method: .get, path: "/api/v1/tournaments/\(id)", query: query),
            as: Tournament.self
        )
    }

    func hydrateTeams(id: Int) async throws -> Tournament {
        try await client.send(
            APIRequest(method: .post, path: "/api/v1/tournaments/\(id)/teams", timeout: 60),
            as: Tournament.self
        )
    }

    func divisions() async throws -> [String] {
        try await client.send(
            APIRequest(method: .get, path: "/api/v1/divisions"),
            as: [String].self
        )
    }
}
