import Foundation

struct TeamAppearance: Codable, Equatable, Hashable, Identifiable {
    let id: Int
    let name: String
    let source: String?
    let startDate: Date?
    let endDate: Date?
    let detailUrl: String?
    let status: String?
    let record: String?
}

struct AnalysisTournament: Codable, Equatable, Identifiable {
    let id: Int
    let name: String
    let source: String?
    let startDate: Date?
    let endDate: Date?
    let detailUrl: String?
    let status: String?
}

struct TeamRecord: Codable, Equatable, Hashable, Identifiable {
    let teamName: String
    let cityState: String?
    let ncsRecord: String?
    let usssaRecord: String?
    let perfectGameRecord: String?
    let cumulativeRecord: String?
    let winPct: Double?
    let totalGames: Int?
    let sourcesSeen: [String]?
    let tournamentCount: Int?
    let appearances: [TeamAppearance]?

    var id: String { teamName }
}

struct TeamStatsResponse: Codable, Equatable {
    let age: String
    let season: String
    let teams: [TeamRecord]
    let totalTeams: Int
    let tournaments: [AnalysisTournament]?
}

struct AvailableSeasonsResponse: Codable, Equatable {
    let seasons: [String]
    let current: String
}
