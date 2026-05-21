import Foundation
import Observation

@MainActor
@Observable
final class AppDependencies {
    private(set) var apiClient: APIClientProtocol
    private(set) var authEndpoints: AuthEndpoints
    let authSession: AuthSession
    let environment: EnvironmentResolver
    let keychain: KeychainStoring
    let theme: Theme

    init(environment: EnvironmentResolver = EnvironmentResolver(), keychain: KeychainStoring = KeychainStore()) {
        self.environment = environment
        self.keychain = keychain
        self.theme = Theme()
        let session = AuthSession(keychain: keychain)
        self.authSession = session

        let baseURL = environment.resolveBaseURL() ?? AppEnvironment.devURL
        let client = APIClient(
            baseURL: baseURL,
            tokenProvider: { [weak session] in await session?.currentToken() },
            onUnauthorized: { [weak session] in
                await MainActor.run { session?.handleUnauthorized() }
            }
        )
        self.apiClient = client
        self.authEndpoints = AuthEndpoints(client: client)
    }

    func rebuildAPIClient() {
        let baseURL = environment.resolveBaseURL() ?? AppEnvironment.devURL
        let client = APIClient(
            baseURL: baseURL,
            tokenProvider: { [weak authSession] in await authSession?.currentToken() },
            onUnauthorized: { [weak authSession] in
                await MainActor.run { authSession?.handleUnauthorized() }
            }
        )
        apiClient = client
        authEndpoints = AuthEndpoints(client: client)
    }

    func bootstrapTheme() async {
        guard case .signedIn = authSession.state else { return }
        do {
            let response = try await SettingsEndpoints(client: apiClient).get()
            theme.apply(response.settings)
        } catch {
            // Theme stays at defaults; not worth surfacing.
        }
    }
}
