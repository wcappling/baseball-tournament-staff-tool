import Foundation

struct TeamRecord: Codable, Equatable, Identifiable {
    let teamName: String
    let cityState: String?
    let ncsRecord: String?
    let usssaRecord: String?
    let perfectGameRecord: String?
    let cumulativeRecord: String?
    let winPct: Double?
    let totalGames: Int?
    let sourcesSeen: [String]?

    var id: String { teamName }
}

struct TeamStatsResponse: Codable, Equatable {
    let age: String
    let season: String
    let teams: [TeamRecord]
    let totalTeams: Int
}

struct AvailableSeasonsResponse: Codable, Equatable {
    let seasons: [String]
    let current: String
}
