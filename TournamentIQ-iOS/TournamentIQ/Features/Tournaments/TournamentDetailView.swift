import SwiftUI

struct TournamentDetailView: View {
    @Environment(AppDependencies.self) private var deps
    let tournamentId: Int
    var onUpdate: ((Tournament) -> Void)? = nil

    @State private var tournament: Tournament?
    @State private var loadError: String?
    @State private var isHydrating = false
    @State private var hydrateError: String?
    @State private var hydrateTask: Task<Void, Never>?
    @State private var showShortlistEditor = false

    var body: some View {
        Group {
            if let tournament {
                content(tournament)
            } else if let loadError {
                ContentUnavailableView {
                    Label("Couldn't load tournament", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(loadError)
                } actions: {
                    Button("Try again") { Task { await load() } }
                }
            } else {
                ProgressView().controlSize(.large)
            }
        }
        .navigationTitle(tournament?.name ?? "Tournament")
        .navigationBarTitleDisplayMode(.inline)
        .task { if tournament == nil { await load() } }
        .sheet(isPresented: $showShortlistEditor) {
            if let tournament {
                ShortlistEditorView(tournament: tournament) { updated in
                    if let updated {
                        await reloadAfterShortlistUpdate()
                        _ = updated
                    }
                }
                .environment(deps)
            }
        }
    }

    @ViewBuilder
    private func content(_ tournament: Tournament) -> some View {
        List {
            headerSection(tournament)
            divisionsSection(tournament)
            divisionTeamsSection(tournament)
            metadataSection(tournament)
        }
        .listStyle(.insetGrouped)
    }

    private func headerSection(_ tournament: Tournament) -> some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                Text(tournament.name).font(.title3.bold())
                HStack {
                    Label(DateFormatting.dateRange(tournament.startDate, tournament.endDate), systemImage: "calendar")
                    Spacer()
                    Text(tournament.source.uppercased())
                        .font(.caption2.weight(.bold))
                        .foregroundStyle(.secondary)
                }
                .font(.subheadline)
                if let location = tournament.location, !location.isEmpty {
                    Label(location, systemImage: "mappin.and.ellipse")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                if let director = tournament.director, !director.isEmpty {
                    Label(director, systemImage: "person.fill")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                HStack {
                    CountBadge(
                        count: tournament.targetTeamCount,
                        meetsThreshold: tournament.meetsTeamThreshold,
                        warning: tournament.countWarning
                    )
                    if let raw = tournament.shortlistStatus, let status = ShortlistStatus(rawValue: raw) {
                        StatusBadge(status: status)
                    }
                    Spacer()
                    Button {
                        showShortlistEditor = true
                    } label: {
                        Label("Edit shortlist", systemImage: "star")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
            }
            .padding(.vertical, 4)
        }
    }

    @ViewBuilder
    private func divisionsSection(_ tournament: Tournament) -> some View {
        if let divisions = tournament.selectedAgeDivisions, !divisions.isEmpty {
            Section("Selected divisions") {
                ForEach(divisions, id: \.division) { division in
                    HStack {
                        Text(division.division)
                        Spacer()
                        Text("\(division.registered) registered • \(division.confirmed) confirmed")
                            .font(.caption.monospacedDigit())
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private func divisionTeamsSection(_ tournament: Tournament) -> some View {
        let teams = tournament.selectedAgeTeams ?? []
        Section {
            if teams.isEmpty {
                if isHydrating {
                    HStack {
                        ProgressView()
                        Text("Loading division teams…")
                            .foregroundStyle(.secondary)
                        Spacer()
                        Button("Cancel") {
                            hydrateTask?.cancel()
                            isHydrating = false
                        }
                        .font(.caption)
                    }
                } else {
                    Button {
                        startHydration()
                    } label: {
                        Label("Load division teams", systemImage: "arrow.down.circle")
                    }
                    if let hydrateError {
                        Text(hydrateError).font(.caption).foregroundStyle(.red)
                    }
                }
            } else {
                ForEach(teams) { team in
                    DivisionTeamRowView(team: team)
                }
            }
        } header: {
            HStack {
                Text("Division teams")
                Spacer()
                if !teams.isEmpty {
                    Text("\(teams.count)").font(.caption.monospacedDigit())
                }
            }
        }
    }

    @ViewBuilder
    private func metadataSection(_ tournament: Tournament) -> some View {
        Section("Details") {
            if let stature = tournament.stature, !stature.isEmpty {
                HStack {
                    Text("Stature"); Spacer(); Text(stature).foregroundStyle(.secondary)
                }
            }
            if let format = tournament.format, !format.isEmpty {
                HStack {
                    Text("Format"); Spacer(); Text(format).foregroundStyle(.secondary)
                }
            }
            if let tags = tournament.tags, !tags.isEmpty {
                HStack {
                    Text("Tags"); Spacer(); Text(tags.joined(separator: ", ")).foregroundStyle(.secondary)
                }
            }
            if let url = tournament.detailUrl.flatMap(URL.init(string:)) {
                Link(destination: url) {
                    Label("Open original listing", systemImage: "safari")
                }
            }
            if let updated = DateFormatting.relativeUpdated(tournament.fetchedAt) {
                HStack {
                    Text("Updated"); Spacer(); Text(updated).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func startHydration() {
        hydrateError = nil
        isHydrating = true
        hydrateTask = Task { @MainActor in
            defer { isHydrating = false }
            do {
                let updated = try await TournamentEndpoints(client: deps.apiClient).hydrateTeams(id: tournamentId)
                tournament = updated
                onUpdate?(updated)
            } catch is CancellationError {
                // user-initiated cancel
            } catch APIError.cancelled {
                // ignore
            } catch {
                hydrateError = error.localizedDescription
            }
        }
    }

    private func load() async {
        loadError = nil
        do {
            let detail = try await TournamentEndpoints(client: deps.apiClient).detail(id: tournamentId)
            tournament = detail
        } catch {
            loadError = error.localizedDescription
        }
    }

    private func reloadAfterShortlistUpdate() async {
        await load()
        if let tournament { onUpdate?(tournament) }
    }
}

struct DivisionTeamRowView: View {
    let team: DivisionTeam

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(team.displayName).font(.subheadline.weight(.medium))
                Spacer()
                if team.confirmed == true {
                    Image(systemName: "checkmark.seal.fill")
                        .foregroundStyle(.green)
                        .accessibilityLabel("Confirmed")
                }
            }
            HStack(spacing: 12) {
                if let location = team.displayLocation {
                    Text(location).font(.caption).foregroundStyle(.secondary)
                }
                if let record = team.record, !record.isEmpty {
                    Text(record).font(.caption.monospacedDigit()).foregroundStyle(.secondary)
                }
                if let cls = team.teamClass, !cls.isEmpty {
                    Text(cls).font(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }
}
