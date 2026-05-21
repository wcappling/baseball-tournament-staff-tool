import Foundation

final class PreferencesStore {
    private let defaults: UserDefaults
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
        self.encoder = JSONEncoder()
        self.decoder = JSONDecoder()
    }

    func load<T: Decodable>(_ type: T.Type, forKey key: String) -> T? {
        guard let data = defaults.data(forKey: key) else { return nil }
        return try? decoder.decode(T.self, from: data)
    }

    func save<T: Encodable>(_ value: T, forKey key: String) {
        guard let data = try? encoder.encode(value) else { return }
        defaults.set(data, forKey: key)
    }

    func clear(forKey key: String) {
        defaults.removeObject(forKey: key)
    }
}

enum PreferenceKey {
    static let tournamentFilters = "tiq.tournament.filters"
    static let tournamentSort = "tiq.tournament.sort"
    static let teamStatsFilters = "tiq.teamStats.filters"
}
