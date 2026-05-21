import Foundation
import Observation
import os

@MainActor
@Observable
final class AuthSession {
    enum State: Equatable {
        case loading
        case signedOut
        case signedIn(TeamIdentity)
    }

    private(set) var state: State = .loading
    private(set) var token: String?

    private let keychain: KeychainStoring
    private let log = Logger(subsystem: "com.tournamentiq.ios", category: "auth")

    init(keychain: KeychainStoring) {
        self.keychain = keychain
    }

    nonisolated func currentToken() async -> String? {
        await MainActor.run { token }
    }

    func bootstrap(using auth: AuthEndpoints) async {
        do {
            guard let stored = try keychain.loadSession() else {
                state = .signedOut
                return
            }
            token = stored.token
            do {
                let me = try await auth.me()
                state = .signedIn(me.team)
            } catch APIError.unauthorized {
                try? keychain.clear()
                token = nil
                state = .signedOut
            } catch {
                log.error("Bootstrap /me failed: \(String(describing: error), privacy: .public)")
                state = .signedOut
            }
        } catch {
            log.error("Keychain load failed: \(String(describing: error), privacy: .public)")
            state = .signedOut
        }
    }

    func signIn(response: LoginResponse) {
        do {
            try keychain.saveSession(response.session, teamSlug: response.team.slug)
        } catch {
            log.error("Keychain save failed: \(String(describing: error), privacy: .public)")
        }
        token = response.session.token
        state = .signedIn(response.team)
    }

    func handleUnauthorized() {
        try? keychain.clear()
        token = nil
        state = .signedOut
    }

    func signOut(using auth: AuthEndpoints) async {
        try? await auth.logout()
        handleUnauthorized()
    }
}
