import SwiftUI

struct StatusBadge: View {
    let status: ShortlistStatus

    var body: some View {
        Text(status.displayName)
            .font(.caption2.weight(.semibold))
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .background(background, in: Capsule())
            .foregroundStyle(foreground)
            .accessibilityLabel("Status: \(status.displayName)")
    }

    private var background: Color {
        switch status {
        case .watch: return Color.gray.opacity(0.2)
        case .interested: return Color.blue.opacity(0.18)
        case .registered: return Color.green.opacity(0.22)
        case .declined: return Color.red.opacity(0.18)
        }
    }

    private var foreground: Color {
        switch status {
        case .watch: return .secondary
        case .interested: return .blue
        case .registered: return .green
        case .declined: return .red
        }
    }
}

struct CountBadge: View {
    let count: Int?
    let meetsThreshold: Bool?
    let warning: Bool?

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: warning == true ? "exclamationmark.triangle.fill" : "person.3.fill")
                .font(.caption2)
            Text(count.map(String.init) ?? "—")
                .font(.caption.monospacedDigit())
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 3)
        .background(background, in: Capsule())
        .foregroundStyle(foreground)
        .accessibilityLabel(accessibilityLabel)
    }

    private var background: Color {
        if warning == true { return Color.orange.opacity(0.18) }
        if meetsThreshold == true { return Color.green.opacity(0.18) }
        return Color.secondary.opacity(0.15)
    }

    private var foreground: Color {
        if warning == true { return .orange }
        if meetsThreshold == true { return .green }
        return .secondary
    }

    private var accessibilityLabel: String {
        let n = count.map(String.init) ?? "unknown"
        if warning == true { return "\(n) teams (count is event-wide, not division-specific)" }
        if meetsThreshold == true { return "\(n) teams (meets threshold)" }
        return "\(n) teams"
    }
}
