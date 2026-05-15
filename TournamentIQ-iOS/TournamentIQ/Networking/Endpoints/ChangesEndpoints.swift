import Foundation

struct ChangesEndpoints {
    let client: APIClientProtocol

    func recent(limit: Int = 200) async throws -> [ChangeEvent] {
        try await client.send(
            APIRequest(method: .get, path: "/api/v1/changes", query: [URLQueryItem(name: "limit", value: String(limit))]),
            as: [ChangeEvent].self
        )
    }

    func refreshRuns() async throws -> [RefreshRun] {
        try await client.send(
            APIRequest(method: .get, path: "/api/v1/refresh-runs"),
            as: [RefreshRun].self
        )
    }
}
