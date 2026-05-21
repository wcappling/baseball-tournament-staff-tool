import SwiftUI
import Observation

@MainActor
@Observable
final class Theme {
    var primary: Color = .accentColor
    var secondary: Color = .secondary
    var accent: Color = .accentColor
    var logoURL: URL?

    func apply(_ settings: TeamSettings) {
        if let hex = settings.brandPrimary, let color = Color(hex: hex) {
            primary = color
        }
        if let hex = settings.brandSecondary, let color = Color(hex: hex) {
            secondary = color
        }
        if let hex = settings.brandAccent, let color = Color(hex: hex) {
            accent = color
        }
        if let raw = settings.logoUrl, !raw.isEmpty, let url = URL(string: raw) {
            logoURL = url
        }
    }
}

extension Color {
    init?(hex: String) {
        let trimmed = hex.trimmingCharacters(in: .whitespacesAndNewlines)
        let stripped = trimmed.hasPrefix("#") ? String(trimmed.dropFirst()) : trimmed
        guard stripped.count == 6, let value = UInt32(stripped, radix: 16) else { return nil }
        let r = Double((value >> 16) & 0xFF) / 255.0
        let g = Double((value >> 8) & 0xFF) / 255.0
        let b = Double(value & 0xFF) / 255.0
        self = Color(red: r, green: g, blue: b)
    }
}
