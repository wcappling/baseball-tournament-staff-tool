import Foundation

struct DivisionTeam: Codable, Equatable, Hashable, Identifiable {
    let number: Int?
    let teamName: String?
    let confirmed: Bool?
    let division: String?
    let cityState: String?
    let city: String?
    let state: String?
    let record: String?
    let teamClass: String?
    let nationalRank: String?

    var id: String {
        if let number, let teamName { return "\(number)-\(teamName)" }
        return teamName ?? UUID().uuidString
    }

    var displayName: String { teamName ?? "Unknown team" }

    var displayLocation: String? {
        if let cityState, !cityState.isEmpty { return cityState }
        switch (city, state) {
        case (let c?, let s?) where !c.isEmpty && !s.isEmpty: return "\(c), \(s)"
        case (let c?, _) where !c.isEmpty: return c
        case (_, let s?) where !s.isEmpty: return s
        default: return nil
        }
    }
}
