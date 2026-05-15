import SwiftUI

@MainActor
@Observable
final class TeamStatsViewModel {
    enum Mode: String, CaseIterable, Identifiable {
        case allTeams
        case interestedRegistered

        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .allTeams: return "All teams"
            case .interestedRegistered: return "Interested/Registered"
            }
        }
    }

    private(set) var state: LoadState = .idle
    private(set) var response: TeamStatsResponse?
    private(set) var seasons: [String] = []
    private(set) var currentSeason: String?
    var mode: Mode = .allTeams
    var ageFilter: String = ""
    var seasonFilter: String = ""
    var query: String = ""

    private let endpoints: TeamStatsEndpoints

    init(endpoints: TeamStatsEndpoints) {
        self.endpoints = endpoints
    }

    var filteredTeams: [TeamRecord] {
        guard let response else { return [] }
        let q = query.trimmingCharacters(in: .whitespaces).lowercased()
        guard !q.isEmpty else { return response.teams }
        return response.teams.filter { record in
            record.teamName.lowercased().contains(q)
                || (record.cityState?.lowercased().contains(q) ?? false)
        }
    }

    func load() async {
        state = .loading
        do {
            let seasonResponse = try await endpoints.availableSeasons()
            seasons = seasonResponse.seasons
            currentSeason = seasonResponse.current
            let age = ageFilter.isEmpty ? nil : ageFilter
            let season = seasonFilter.isEmpty ? nil : seasonFilter
            response = switch mode {
            case .allTeams: try await endpoints.teamStats(age: age, season: season)
            case .interestedRegistered: try await endpoints.teamAnalysis(age: age, season: season)
            }
            state = .loaded
        } catch APIError.unauthorized {
            state = .failed("Session expired. Please sign in again.")
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}

struct TeamStatsView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var viewModel: TeamStatsViewModel?

    var body: some View {
        NavigationStack {
            Group {
                if let viewModel {
                    content(viewModel)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Teams")
        }
        .onAppear {
            if viewModel == nil {
                viewModel = TeamStatsViewModel(endpoints: TeamStatsEndpoints(client: deps.apiClient))
                Task { await viewModel?.load() }
            }
        }
    }

    @ViewBuilder
    private func content(_ viewModel: TeamStatsViewModel) -> some View {
        VStack(spacing: 0) {
            controls(viewModel)
            Divider()
            switch viewModel.state {
            case .idle, .loading:
                Spacer()
                ProgressView()
                Spacer()
            case .failed(let message):
                ContentUnavailableView {
                    Label("Couldn't load team stats", systemImage: "exclamationmark.triangle")
                } description: { Text(message) }
            case .loaded where viewModel.filteredTeams.isEmpty:
                ContentUnavailableView {
                    Label("No team records", systemImage: "person.3")
                } description: {
                    Text("Try a different age, season, or search.")
                }
            case .loaded:
                List(viewModel.filteredTeams) { record in
                    NavigationLink(value: record) {
                        TeamRecordRow(record: record)
                    }
                }
                .listStyle(.plain)
                .navigationDestination(for: TeamRecord.self) { record in
                    TeamRecordDetailView(record: record)
                }
            }
        }
        .refreshable { await viewModel.load() }
    }

    @ViewBuilder
    private func controls(_ viewModel: TeamStatsViewModel) -> some View {
        @Bindable var bindable = viewModel
        VStack(spacing: 8) {
            Picker("Mode", selection: $bindable.mode) {
                ForEach(TeamStatsViewModel.Mode.allCases) { mode in
                    Text(mode.displayName).tag(mode)
                }
            }
            .pickerStyle(.segmented)
            .onChange(of: viewModel.mode) { _, _ in
                Task { await viewModel.load() }
            }

            HStack {
                TextField("Age", text: $bindable.ageFilter)
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                    .textFieldStyle(.roundedBorder)
                    .frame(maxWidth: 70)
                if !viewModel.seasons.isEmpty {
                    Picker("Season", selection: $bindable.seasonFilter) {
                        Text("Current").tag("")
                        ForEach(viewModel.seasons, id: \.self) { Text($0).tag($0) }
                    }
                    .pickerStyle(.menu)
                }
                Button("Apply") { Task { await viewModel.load() } }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.small)
            }

            TextField("Search team or city", text: $bindable.query)
                .textFieldStyle(.roundedBorder)
        }
        .padding()
    }
}

private struct TeamRecordRow: View {
    let record: TeamRecord

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(record.teamName).font(.subheadline.weight(.medium))
                Spacer()
                Text(record.cumulativeRecord ?? "—")
                    .font(.caption.monospacedDigit())
                    .foregroundStyle(.secondary)
            }
            HStack(spacing: 12) {
                if let location = record.cityState, !location.isEmpty {
                    Text(location).font(.caption).foregroundStyle(.secondary)
                }
                if let games = record.totalGames {
                    Text("\(games) games").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                if let pct = record.winPct {
                    Text(String(format: "%.1f%%", pct * 100)).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                if let count = record.tournamentCount {
                    Text("\(count) tournaments").font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
            }
        }
    }
}

private struct TeamRecordDetailView: View {
    let record: TeamRecord

    var body: some View {
        List {
            Section("Records") {
                if let cumulative = record.cumulativeRecord { LabeledContent("Cumulative", value: cumulative) }
                if let pct = record.winPct {
                    LabeledContent("Win %", value: String(format: "%.1f%%", pct * 100))
                }
                if let ncs = record.ncsRecord, !ncs.isEmpty { LabeledContent("NCS", value: ncs) }
                if let usssa = record.usssaRecord, !usssa.isEmpty { LabeledContent("USSSA", value: usssa) }
                if let pg = record.perfectGameRecord, !pg.isEmpty { LabeledContent("Perfect Game", value: pg) }
            }
            if let appearances = record.appearances, !appearances.isEmpty {
                Section("Appearances") {
                    ForEach(appearances) { appearance in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(appearance.name).font(.subheadline.weight(.medium))
                            HStack(spacing: 8) {
                                if let source = appearance.source {
                                    Text(source.uppercased()).font(.caption2.weight(.bold)).foregroundStyle(.secondary)
                                }
                                Text(DateFormatting.dateRange(appearance.startDate, appearance.endDate))
                                    .font(.caption)
                                if let record = appearance.record {
                                    Text(record).font(.caption.monospacedDigit())
                                }
                                if let status = appearance.status {
                                    Text(status).font(.caption2)
                                }
                            }
                            .foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }
        .navigationTitle(record.teamName)
        .navigationBarTitleDisplayMode(.inline)
    }
}
