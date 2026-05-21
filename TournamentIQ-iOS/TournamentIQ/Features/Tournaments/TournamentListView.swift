import SwiftUI

struct TournamentListView: View {
    @Bindable var viewModel: TournamentsViewModel
    @State private var showFilters = false

    var body: some View {
        Group {
            switch viewModel.state {
            case .idle, .loading:
                ProgressView()
                    .controlSize(.large)
            case .failed(let message):
                ContentUnavailableView {
                    Label("Couldn't load tournaments", systemImage: "exclamationmark.triangle")
                } description: {
                    Text(message)
                } actions: {
                    Button("Try again") { Task { await viewModel.refresh() } }
                }
            case .loaded where viewModel.tournaments.isEmpty:
                ContentUnavailableView {
                    Label("No tournaments", systemImage: "calendar")
                } description: {
                    Text("Try widening your filters or check back after the next refresh.")
                } actions: {
                    Button("Clear filters") { Task { await viewModel.clearFilters() } }
                        .disabled(viewModel.filters.isEmpty)
                }
            case .loaded:
                listContent
            }
        }
        .navigationTitle("Tournaments")
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    showFilters = true
                } label: {
                    Image(systemName: viewModel.filters.isEmpty ? "line.3.horizontal.decrease.circle" : "line.3.horizontal.decrease.circle.fill")
                }
                .accessibilityLabel("Filters")
            }
        }
        .sheet(isPresented: $showFilters) {
            TournamentFiltersView(
                filters: viewModel.filters,
                sort: viewModel.sort,
                availableDivisions: viewModel.availableDivisions,
                onApply: { filters, sort in
                    Task {
                        viewModel.updateSort(sort)
                        await viewModel.applyFilters(filters)
                    }
                },
                onReset: {
                    Task { await viewModel.clearFilters() }
                }
            )
        }
        .task { if viewModel.state == .idle { await viewModel.load() } }
        .refreshable { await viewModel.refresh() }
    }

    private var listContent: some View {
        List(viewModel.tournaments) { tournament in
            NavigationLink(value: tournament.id) {
                TournamentRowView(tournament: tournament)
            }
        }
        .listStyle(.plain)
    }
}
