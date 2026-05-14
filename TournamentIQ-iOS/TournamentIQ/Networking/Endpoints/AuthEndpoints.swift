import Foundation

struct AuthEndpoints {
    let client: APIClientProtocol

    func login(teamSlug: String, password: String) async throws -> LoginResponse {
        let payload = ["team_slug": teamSlug, "password": password]
        let body = try JSONSerialization.data(withJSONObject: payload)
        let request = APIRequest(
            method: .post,
            path: "/api/v1/login",
            body: body,
            contentType: "application/json",
            requiresAuth: false
        )
        return try await client.send(request, as: LoginResponse.self)
    }

    func me() async throws -> MeResponse {
        try await client.get("/api/v1/me", as: MeResponse.self)
    }

    func logout() async throws {
        try await client.send(APIRequest(method: .post, path: "/api/v1/logout"))
    }
}
