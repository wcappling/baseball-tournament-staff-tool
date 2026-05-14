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
        case .signedIn(let team):
            SignedInPlaceholderView(team: team)
        }
    }
}

private struct SignedInPlaceholderView: View {
    @Environment(AppDependencies.self) private var deps
    let team: TeamIdentity

    var body: some View {
        NavigationStack {
            VStack(spacing: 16) {
                Text("Signed in as")
                    .foregroundStyle(.secondary)
                Text(team.displayName)
                    .font(.title2.bold())
                Text(team.slug)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                Spacer()
                Button("Sign out") {
                    Task { await deps.authSession.signOut(using: deps.authEndpoints) }
                }
            }
            .padding()
            .navigationTitle("Tournament IQ")
        }
    }
}
