import SwiftUI

@MainActor
@Observable
final class ChangeLogViewModel {
    private(set) var state: LoadState = .idle
    private(set) var events: [ChangeEvent] = []
    private let endpoints: ChangesEndpoints

    init(endpoints: ChangesEndpoints) {
        self.endpoints = endpoints
    }

    func load() async {
        state = .loading
        do {
            events = try await endpoints.recent()
            state = .loaded
        } catch APIError.unauthorized {
            state = .failed("Session expired. Please sign in again.")
        } catch {
            state = .failed(error.localizedDescription)
        }
    }
}

struct ChangeLogView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var viewModel: ChangeLogViewModel?

    var body: some View {
        NavigationStack {
            Group {
                if let viewModel {
                    content(viewModel)
                } else {
                    ProgressView()
                }
            }
            .navigationTitle("Changes")
            .refreshable { await viewModel?.load() }
        }
        .onAppear {
            if viewModel == nil {
                viewModel = ChangeLogViewModel(endpoints: ChangesEndpoints(client: deps.apiClient))
                Task { await viewModel?.load() }
            }
        }
    }

    @ViewBuilder
    private func content(_ viewModel: ChangeLogViewModel) -> some View {
        switch viewModel.state {
        case .idle, .loading:
            ProgressView()
        case .failed(let message):
            ContentUnavailableView {
                Label("Couldn't load changes", systemImage: "exclamationmark.triangle")
            } description: { Text(message) }
        case .loaded where viewModel.events.isEmpty:
            ContentUnavailableView {
                Label("No changes yet", systemImage: "clock.arrow.circlepath")
            } description: {
                Text("Tournament updates will appear here as data refreshes.")
            }
        case .loaded:
            List(viewModel.events) { event in
                ChangeEventRow(event: event)
            }
            .listStyle(.plain)
        }
    }
}

private struct ChangeEventRow: View {
    let event: ChangeEvent

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(event.tournamentName ?? "Unknown tournament")
                    .font(.subheadline.weight(.medium))
                Spacer()
                if let relative = DateFormatting.relativeUpdated(event.detectedAt) {
                    Text(relative).font(.caption2.monospacedDigit()).foregroundStyle(.secondary)
                }
            }
            HStack(alignment: .firstTextBaseline, spacing: 6) {
                Text(event.field.replacingOccurrences(of: "_", with: " "))
                    .font(.caption.weight(.semibold))
                    .foregroundStyle(.secondary)
                if let new = event.newValue {
                    Text(new).font(.caption)
                } else {
                    Text("(removed)").font(.caption.italic()).foregroundStyle(.secondary)
                }
            }
            if let old = event.oldValue, !old.isEmpty {
                Text("was: \(old)")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
    }
}
