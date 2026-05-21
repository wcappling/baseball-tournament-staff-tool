import Foundation
import Observation
import os

@MainActor
@Observable
final class TournamentsViewModel {
    private(set) var state: LoadState = .idle
    private(set) var tournaments: [Tournament] = []
    private(set) var availableDivisions: [String] = []
    var filters: TournamentFilters
    var sort: TournamentSort

    private let endpoints: TournamentEndpoints
    private let prefs: PreferencesStore
    private let log = Logger(subsystem: "com.tournamentiq.ios", category: "ui")

    init(endpoints: TournamentEndpoints, prefs: PreferencesStore = PreferencesStore()) {
        self.endpoints = endpoints
        self.prefs = prefs
        self.filters = prefs.load(TournamentFilters.self, forKey: PreferenceKey.tournamentFilters) ?? TournamentFilters()
        self.sort = prefs.load(TournamentSort.self, forKey: PreferenceKey.tournamentSort) ?? .startDateAsc
    }

    func load() async {
        state = .loading
        do {
            async let listing = endpoints.list(filters: filters)
            async let divisions = endpoints.divisions()
            let (items, divs) = try await (listing, divisions)
            tournaments = sort.sort(items)
            availableDivisions = divs
            state = .loaded
        } catch APIError.unauthorized {
            state = .failed("Session expired. Please sign in again.")
        } catch {
            log.error("Tournaments load failed: \(String(describing: error), privacy: .public)")
            state = .failed(error.localizedDescription)
        }
    }

    func refresh() async { await load() }

    func applyFilters(_ next: TournamentFilters) async {
        filters = next
        prefs.save(filters, forKey: PreferenceKey.tournamentFilters)
        await load()
    }

    func clearFilters() async {
        filters = TournamentFilters()
        prefs.clear(forKey: PreferenceKey.tournamentFilters)
        await load()
    }

    func updateSort(_ next: TournamentSort) {
        sort = next
        prefs.save(sort, forKey: PreferenceKey.tournamentSort)
        tournaments = sort.sort(tournaments)
    }

    func replace(_ tournament: Tournament) {
        guard let index = tournaments.firstIndex(where: { $0.id == tournament.id }) else { return }
        tournaments[index] = tournament
    }
}
