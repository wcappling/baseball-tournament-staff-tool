import Foundation

enum ShortlistStatus: String, Codable, CaseIterable, Identifiable {
    case watch = "Watch"
    case interested = "Interested"
    case registered = "Registered"
    case declined = "Declined"

    var id: String { rawValue }

    var displayName: String { rawValue }
}

struct ShortlistUpdate: Codable, Equatable {
    let status: ShortlistStatus
    let priority: Int
    let notes: String

    init(status: ShortlistStatus, priority: Int = 3, notes: String = "") {
        self.status = status
        self.priority = max(1, priority)
        self.notes = notes
    }
}

struct ShortlistResponse: Codable, Equatable {
    let teamId: String?
    let tournamentId: Int
    let status: String
    let priority: Int
    let notes: String?
    let createdAt: Date?
    let updatedAt: Date?
}
