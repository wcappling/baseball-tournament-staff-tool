import Foundation

struct TeamIdentity: Codable, Equatable, Hashable {
    let id: String
    let slug: String
    let displayName: String

    enum CodingKeys: String, CodingKey {
        case id
        case slug
        case displayName = "display_name"
    }
}

struct SessionToken: Codable, Equatable, Hashable {
    let token: String
    let expiresAt: Date?

    enum CodingKeys: String, CodingKey {
        case token
        case expiresAt = "expires_at"
    }
}

struct LoginResponse: Codable, Equatable {
    let team: TeamIdentity
    let session: SessionToken
}

struct MeResponse: Codable, Equatable {
    let team: TeamIdentity
}
