import Foundation

struct SelectedDivisionSummary: Codable, Equatable, Hashable {
    let division: String
    let registered: Int
    let confirmed: Int
}

struct Tournament: Codable, Equatable, Identifiable {
    let id: Int
    let source: String
    let sourceId: String?
    let name: String
    let detailUrl: String?
    let location: String?
    let director: String?
    let startDate: Date?
    let endDate: Date?
    let ageDivisions: [String]?
    let registeredTeams: Int?
    let divisionTeamCounts: [String: Int]?
    let divisionConfirmedCounts: [String: Int]?
    let divisionTeams: [String: [DivisionTeam]]?
    let teamCountScope: String?
    let stature: String?
    let format: String?
    let tags: [String]?
    let logoUrl: String?
    let distanceMiles: Double?
    let fetchedAt: Date?

    let selectedAgeDivisions: [SelectedDivisionSummary]?
    let selectedAgeTeams: [DivisionTeam]?
    let selectedAgeConfirmedCount: Int?
    let targetAgeDivision: String?
    let targetTeamCount: Int?
    let countWarning: Bool?
    let meetsTeamThreshold: Bool?

    let shortlistStatus: String?
    let shortlistPriority: Int?
    let shortlistNotes: String?
}
