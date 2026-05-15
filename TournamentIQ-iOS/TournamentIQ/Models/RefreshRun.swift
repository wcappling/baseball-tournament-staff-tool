import Foundation

struct RefreshRun: Codable, Equatable, Identifiable {
    let id: Int
    let source: String
    let startedAt: Date
    let finishedAt: Date?
    let status: String
    let message: String?
    let tournamentsSeen: Int?
}
