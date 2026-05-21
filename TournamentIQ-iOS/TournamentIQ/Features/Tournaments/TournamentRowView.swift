import SwiftUI

struct TournamentRowView: View {
    let tournament: Tournament

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(tournament.name)
                    .font(.headline)
                    .lineLimit(2)
                Spacer()
                if let raw = tournament.shortlistStatus, let status = ShortlistStatus(rawValue: raw) {
                    StatusBadge(status: status)
                }
            }

            HStack(spacing: 8) {
                if let location = tournament.location, !location.isEmpty {
                    Label(location, systemImage: "mappin.and.ellipse")
                        .labelStyle(.titleAndIcon)
                }
                if let miles = tournament.distanceMiles {
                    Text(String(format: "%.0f mi", miles))
                        .foregroundStyle(.secondary)
                }
            }
            .font(.subheadline)
            .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                Text(DateFormatting.dateRange(tournament.startDate, tournament.endDate))
                    .font(.subheadline)
                Spacer()
                Text(tournament.source.uppercased())
                    .font(.caption2.weight(.bold))
                    .foregroundStyle(.secondary)
                CountBadge(
                    count: tournament.targetTeamCount,
                    meetsThreshold: tournament.meetsTeamThreshold,
                    warning: tournament.countWarning
                )
            }
        }
        .padding(.vertical, 4)
        .accessibilityElement(children: .combine)
    }
}
