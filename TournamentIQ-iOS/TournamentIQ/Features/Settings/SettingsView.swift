import SwiftUI

@MainActor
@Observable
final class SettingsViewModel {
    private(set) var state: LoadState = .idle
    private(set) var team: TeamIdentity?
    private(set) var settings: TeamSettings?
    private let endpoints: SettingsEndpoints

    init(endpoints: SettingsEndpoints) {
        self.endpoints = endpoints
    }

    func load() async {
        state = .loading
        do {
            let response = try await endpoints.get()
            team = response.team
            settings = response.settings
            state = .loaded
        } catch APIError.unauthorized {
            state = .failed("Session expired. Please sign in again.")
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}

struct SettingsView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var viewModel: SettingsViewModel?
    @State private var showEnvSwitcher = false
    @State private var showSignOutConfirm = false

    var body: some View {
        NavigationStack {
            Group {
                if let viewModel {
                    content(viewModel)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Settings")
            .toolbar {
                ToolbarItem(placement: .topBarTrailing) {
                    Menu {
                        Button("Sign out", role: .destructive) { showSignOutConfirm = true }
                        Divider()
                        Button("Backend URL…") { showEnvSwitcher = true }
                    } label: {
                        Image(systemName: "ellipsis.circle")
                    }
                }
            }
            .sheet(isPresented: $showEnvSwitcher) {
                EnvironmentSwitcherView().environment(deps)
            }
            .confirmationDialog(
                "Sign out of Tournament IQ?",
                isPresented: $showSignOutConfirm,
                titleVisibility: .visible
            ) {
                Button("Sign out", role: .destructive) {
                    Task { await deps.authSession.signOut(using: deps.authEndpoints) }
                }
            }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = SettingsViewModel(endpoints: SettingsEndpoints(client: deps.apiClient))
                Task { await viewModel?.load() }
            }
        }
    }

    @ViewBuilder
    private func content(_ viewModel: SettingsViewModel) -> some View {
        switch viewModel.state {
        case .idle, .loading:
            ProgressView()
        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't load settings", systemImage: "exclamationmark.triangle")
            } description: { Text(message) }
        case .loaded:
            Form {
                if let team = viewModel.team {
                    Section("Team") {
                        LabeledContent("Name", value: team.displayName)
                        LabeledContent("Code", value: team.slug)
                    }
                }
                if let settings = viewModel.settings {
                    Section("Defaults") {
                        if let age = settings.targetAgeDivision { LabeledContent("Target age", value: age) }
                        if let radius = settings.radiusMiles { LabeledContent("Radius", value: "\(radius) mi") }
                        if let threshold = settings.teamCountThreshold { LabeledContent("Min teams", value: String(threshold)) }
                        if let zip = settings.homeZip { LabeledContent("Home ZIP", value: zip) }
                        if let label = settings.homeLabel { LabeledContent("Home label", value: label) }
                    }
                    Section("Branding") {
                        if let primary = settings.brandPrimary { LabeledContent("Primary", value: primary) }
                        if let secondary = settings.brandSecondary { LabeledContent("Secondary", value: secondary) }
                        if let accent = settings.brandAccent { LabeledContent("Accent", value: accent) }
                        if let logoUrl = settings.logoUrl, !logoUrl.isEmpty {
                            LabeledContent("Logo URL", value: logoUrl)
                                .lineLimit(1)
                                .truncationMode(.middle)
                        }
                    }
                }
            }
        }
    }
}
