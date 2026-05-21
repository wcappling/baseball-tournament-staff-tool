import SwiftUI

struct TournamentsTabView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var viewModel: TournamentsViewModel?
    @State private var path: [Int] = []

    var body: some View {
        NavigationStack(path: $path) {
            Group {
                if let viewModel {
                    TournamentListView(viewModel: viewModel)
                } else {
                    ProgressView().controlSize(.large)
                }
            }
            .navigationDestination(for: Int.self) { tournamentId in
                TournamentDetailView(tournamentId: tournamentId) { updated in
                    viewModel?.replace(updated)
                }
            }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = TournamentsViewModel(endpoints: TournamentEndpoints(client: deps.apiClient))
            }
        }
    }
}
