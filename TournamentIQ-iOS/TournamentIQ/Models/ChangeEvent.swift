import Foundation

struct ChangeEvent: Codable, Equatable, Identifiable {
    let id: Int
    let tournamentId: Int?
    let tournamentName: String?
    let source: String
    let sourceId: String
    let field: String
    let oldValue: String?
    let newValue: String?
    let detectedAt: Date
    let staffVisible: Int?
}
