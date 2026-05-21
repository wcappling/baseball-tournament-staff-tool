import SwiftUI

struct MainTabView: View {
    @Environment(AppDependencies.self) private var deps
    @State private var selection: Tab = .tournaments

    enum Tab: Hashable {
        case tournaments, upcoming, teams, changes, settings
    }

    var body: some View {
        TabView(selection: $selection) {
            TournamentsTabView()
                .tabItem { Label("Tournaments", systemImage: "calendar") }
                .tag(Tab.tournaments)

            UpcomingView()
                .tabItem { Label("Upcoming", systemImage: "calendar.badge.checkmark") }
                .tag(Tab.upcoming)

            TeamStatsView()
                .tabItem { Label("Teams", systemImage: "person.3") }
                .tag(Tab.teams)

            ChangeLogView()
                .tabItem { Label("Changes", systemImage: "clock.arrow.circlepath") }
                .tag(Tab.changes)

            SettingsView()
                .tabItem { Label("Settings", systemImage: "gearshape") }
                .tag(Tab.settings)
        }
        .tint(deps.theme.primary)
        .task { await deps.bootstrapTheme() }
    }
}
