import SwiftUI

struct RootView: View {
    @Environment(AppDependencies.self) private var deps

    var body: some View {
        switch deps.authSession.state {
        case .loading:
            ProgressView()
                .controlSize(.large)
        case .signedOut:
            LoginView()
        case .signedIn:
            MainTabView()
        }
    }
}
