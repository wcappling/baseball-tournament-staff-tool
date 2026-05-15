import Foundation

struct TeamSettings: Codable, Equatable {
    var homeZip: String?
    var homeLabel: String?
    var radiusMiles: Int?
    var targetAgeDivision: String?
    var teamCountThreshold: Int?
    var refreshCadenceHours: Int?
    var enabledSources: [String]?
    var brandPrimary: String?
    var brandSecondary: String?
    var brandAccent: String?
    var logoUrl: String?
}

struct TeamSettingsResponse: Codable, Equatable {
    let team: TeamIdentity
    let settings: TeamSettings
}

struct TeamSettingsUpdate: Codable, Equatable {
    var homeZip: String?
    var homeLabel: String?
    var radiusMiles: Int?
    var targetAgeDivision: String?
    var teamCountThreshold: Int?
    var refreshCadenceHours: Int?
    var enabledSources: [String]?
    var brandPrimary: String?
    var brandSecondary: String?
    var brandAccent: String?
    var logoUrl: String?
}
