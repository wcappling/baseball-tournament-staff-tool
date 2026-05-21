import SwiftUI

@MainActor
@Observable
final class UpcomingViewModel {
    private(set) var state: LoadState = .idle
    private(set) var tournaments: [Tournament] = []
    private let endpoints: TournamentEndpoints

    init(endpoints: TournamentEndpoints) {
        self.endpoints = endpoints
    }

    func load() async {
        state = .loading
        do {
            let all = try await endpoints.list(filters: TournamentFilters())
            let now = Calendar.current.startOfDay(for: Date())
            tournaments = all
                .filter { tournament in
                    guard let status = tournament.shortlistStatus,
                          status == ShortlistStatus.interested.rawValue || status == ShortlistStatus.registered.rawValue
                    else { return false }
                    if let end = tournament.endDate { return end >= now }
                    return true
                }
                .sorted { (lhs, rhs) in
                    (lhs.startDate ?? .distantFuture) < (rhs.startDate ?? .distantFuture)
                }
            state = .loaded
        } catch APIError.unauthorized {
            state = .failed("Session expired. Please sign in again.")
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}

struct UpcomingView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var viewModel: UpcomingViewModel?
    @State private var path: [Int] = []

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                if let viewModel {
                    content(viewModel)
                } else {
                    ProgressView().controlSize(.large)
                }
            }
            .navigationTitle("Upcoming")
            .navigationDestination(for: Int.self) { id in
                TournamentDetailView(tournamentId: id)
            }
            .refreshable { await viewModel?.load() }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = UpcomingViewModel(endpoints: TournamentEndpoints(client: deps.apiClient))
                Task { await viewModel?.load() }
            }
        }
    }

    @ViewBuilder
    private func content(_ viewModel: UpcomingViewModel) -> some View {
        switch viewModel.state {
        case .idle, .loading:
            ProgressView().controlSize(.large)
        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't load upcoming", systemImage: "exclamationmark.triangle")
            } description: { Text(message) }
        case .loaded where viewModel.tournaments.isEmpty:
            ContentUnavailableView {
                Label("Nothing upcoming", systemImage: "calendar.badge.checkmark")
            } description: {
                Text("Mark tournaments as Interested or Registered to see them here.")
            }
        case .loaded:
            List(viewModel.tournaments) { tournament in
                NavigationLink(value: tournament.id) {
                    TournamentRowView(tournament: tournament)
                }
            }
            .listStyle(.plain)
        }
    }
}
