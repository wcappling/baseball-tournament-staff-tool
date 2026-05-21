import Foundation

enum AppEnvironment: String, CaseIterable, Identifiable {
    case prod
    case dev
    case custom

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .prod: return "Production"
        case .dev: return "Development"
        case .custom: return "Custom URL"
        }
    }

    static let prodURL = URL(string: "https://tournamentiq-prod.up.railway.app")!
    static let devURL = URL(string: "https://tournamentiq-dev.up.railway.app")!

    static var defaultForBuild: AppEnvironment {
        #if DEBUG
        return .dev
        #else
        return .prod
        #endif
    }
}

struct EnvironmentResolver {
    private static let envKey = "tiq.env.selected"
    private static let customURLKey = "tiq.env.customURL"
    private let defaults: UserDefaults

    init(defaults: UserDefaults = .standard) {
        self.defaults = defaults
    }

    var selected: AppEnvironment {
        get {
            if let raw = defaults.string(forKey: Self.envKey),
               let env = AppEnvironment(rawValue: raw) {
                return env
            }
            return AppEnvironment.defaultForBuild
        }
        nonmutating set {
            defaults.set(newValue.rawValue, forKey: Self.envKey)
        }
    }

    var customURLString: String {
        get { defaults.string(forKey: Self.customURLKey) ?? "" }
        nonmutating set { defaults.set(newValue, forKey: Self.customURLKey) }
    }

    func resolveBaseURL() -> URL? {
        switch selected {
        case .prod:
            return AppEnvironment.prodURL
        case .dev:
            return AppEnvironment.devURL
        case .custom:
            let raw = customURLString.trimmingCharacters(in: .whitespacesAndNewlines)
            guard let url = URL(string: raw), let scheme = url.scheme?.lowercased() else { return nil }
            return scheme == "https" ? url : nil
        }
    }
}
