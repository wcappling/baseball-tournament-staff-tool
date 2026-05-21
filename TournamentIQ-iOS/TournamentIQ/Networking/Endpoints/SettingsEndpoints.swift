import Foundation

struct SettingsEndpoints {
    let client: APIClientProtocol

    func get() async throws -> TeamSettingsResponse {
        try await client.send(APIRequest(method: .get, path: "/api/v1/settings"), as: TeamSettingsResponse.self)
    }

    func update(_ update: TeamSettingsUpdate) async throws -> TeamSettingsResponse {
        let encoder = DecodingStrategies.makeEncoder()
        let body = try encoder.encode(update)
        return try await client.send(
            APIRequest(
                method: .put,
                path: "/api/v1/settings",
                body: body,
                contentType: "application/json"
            ),
            as: TeamSettingsResponse.self
        )
    }
}
