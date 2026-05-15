import Foundation

struct TeamIdentity: Codable, Equatable, Hashable {
    let id: String
    let slug: String
    let displayName: String
}

struct SessionToken: Codable, Equatable, Hashable {
    let token: String
    let expiresAt: Date?
}

struct LoginResponse: Codable, Equatable {
    let team: TeamIdentity
    let session: SessionToken
}

struct MeResponse: Codable, Equatable {
    let team: TeamIdentity
}
