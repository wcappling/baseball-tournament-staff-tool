import SwiftUI

@main
struct TournamentIQApp: App {
    @State private var deps = AppDependencies()

    var body: some Scene {
        WindowGroup {
            RootView()
                .environment(deps)
                .task { await deps.authSession.bootstrap(using: deps.authEndpoints) }
        }
    }
}
