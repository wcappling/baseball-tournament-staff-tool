import Foundation

struct ShortlistEndpoints {
    let client: APIClientProtocol

    func update(tournamentId: Int, update: ShortlistUpdate) async throws -> ShortlistResponse {
        let encoder = DecodingStrategies.makeEncoder()
        let body = try encoder.encode(update)
        return try await client.send(
            APIRequest(
                method: .put,
                path: "/api/v1/tournaments/\(tournamentId)/shortlist",
                body: body,
                contentType: "application/json"
            ),
            as: ShortlistResponse.self
        )
    }
}
