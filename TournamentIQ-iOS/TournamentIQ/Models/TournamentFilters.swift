import Foundation

struct TournamentFilters: Codable, Equatable {
    var sources: Set<String> = []
    var age: String?
    var divisions: Set<String> = []
    var teamCountThreshold: Int?
    var radiusMiles: Int?
    var startOnOrAfter: Date?
    var endOnOrBefore: Date?
    var singleDay: Bool?
    var query: String?

    var isEmpty: Bool {
        sources.isEmpty
            && age == nil
            && divisions.isEmpty
            && teamCountThreshold == nil
            && radiusMiles == nil
            && startOnOrAfter == nil
            && endOnOrBefore == nil
            && singleDay == nil
            && (query?.isEmpty ?? true)
    }

    var queryItems: [URLQueryItem] {
        var items: [URLQueryItem] = []
        for source in sources.sorted() {
            items.append(URLQueryItem(name: "source", value: source))
        }
        if let age, !age.isEmpty {
            items.append(URLQueryItem(name: "age", value: age))
        }
        for division in divisions.sorted() {
            items.append(URLQueryItem(name: "division", value: division))
        }
        if let teamCountThreshold {
            items.append(URLQueryItem(name: "threshold", value: String(teamCountThreshold)))
        }
        if let radiusMiles {
            items.append(URLQueryItem(name: "radius_miles", value: String(radiusMiles)))
        }
        if let startOnOrAfter {
            items.append(URLQueryItem(name: "start_on_or_after", value: TournamentFilters.dateFormatter.string(from: startOnOrAfter)))
        }
        if let endOnOrBefore {
            items.append(URLQueryItem(name: "end_on_or_before", value: TournamentFilters.dateFormatter.string(from: endOnOrBefore)))
        }
        if let singleDay {
            items.append(URLQueryItem(name: "single_day", value: singleDay ? "true" : "false"))
        }
        if let query, !query.isEmpty {
            items.append(URLQueryItem(name: "q", value: query))
        }
        return items
    }

    static let dateFormatter: DateFormatter = {
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.timeZone = TimeZone(secondsFromGMT: 0)
        f.dateFormat = "yyyy-MM-dd"
        return f
    }()
}

enum TournamentSort: String, Codable, CaseIterable, Identifiable {
    case startDateAsc
    case startDateDesc
    case teamCountDesc
    case distanceAsc
    case nameAsc

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .startDateAsc: return "Start date (soonest)"
        case .startDateDesc: return "Start date (latest)"
        case .teamCountDesc: return "Team count"
        case .distanceAsc: return "Distance"
        case .nameAsc: return "Name"
        }
    }

    func sort(_ tournaments: [Tournament]) -> [Tournament] {
        tournaments.sorted { lhs, rhs in
            switch self {
            case .startDateAsc:
                return (lhs.startDate ?? .distantFuture) < (rhs.startDate ?? .distantFuture)
            case .startDateDesc:
                return (lhs.startDate ?? .distantPast) > (rhs.startDate ?? .distantPast)
            case .teamCountDesc:
                return (lhs.targetTeamCount ?? -1) > (rhs.targetTeamCount ?? -1)
            case .distanceAsc:
                return (lhs.distanceMiles ?? .greatestFiniteMagnitude) < (rhs.distanceMiles ?? .greatestFiniteMagnitude)
            case .nameAsc:
                return lhs.name.localizedCaseInsensitiveCompare(rhs.name) == .orderedAscending
            }
        }
    }
}
