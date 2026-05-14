import SwiftUI

@main
struct TournamentIQApp: App {
    var body: some Scene {
        WindowGroup {
            RootView()
        }
    }
}

struct RootView: View {
    var body: some View {
        VStack(spacing: 12) {
            Text("Tournament IQ")
                .font(.largeTitle.bold())
            Text("Scaffold build")
                .font(.subheadline)
                .foregroundStyle(.secondary)
        }
        .padding()
    }
}

#Preview {
    RootView()
}
