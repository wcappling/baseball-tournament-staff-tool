import SwiftUI

struct LoginView: View {
    @Environment(AppDependencies.self) private var deps

    @State private var teamSlug: String = ""
    @State private var password: String = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?
    @State private var logoTapCount = 0
    @State private var lastLogoTapAt: Date = .distantPast
    @State private var showEnvironmentSwitcher = false

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    HStack {
                        Spacer()
                        logo
                        Spacer()
                    }
                    .listRowBackground(Color.clear)
                }

                Section("Team") {
                    TextField("Team code", text: $teamSlug)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textContentType(.username)
                    SecureField("Password", text: $password)
                        .textContentType(.password)
                }

                if let errorMessage {
                    Section {
                        Text(errorMessage)
                            .foregroundStyle(.red)
                    }
                }

                Section {
                    Button(action: submit) {
                        if isSubmitting {
                            ProgressView()
                        } else {
                            Text("Sign In")
                                .frame(maxWidth: .infinity)
                        }
                    }
                    .disabled(!canSubmit)
                }
            }
            .navigationTitle("Tournament IQ")
            .sheet(isPresented: $showEnvironmentSwitcher) {
                EnvironmentSwitcherView()
                    .environment(deps)
            }
        }
    }

    private var logo: some View {
        Image(systemName: "baseball")
            .resizable()
            .aspectRatio(contentMode: .fit)
            .frame(width: 80, height: 80)
            .foregroundStyle(.tint)
            .padding(.vertical, 16)
            .accessibilityLabel("Tournament IQ logo")
            .onTapGesture {
                let now = Date()
                if now.timeIntervalSince(lastLogoTapAt) > 3 { logoTapCount = 0 }
                lastLogoTapAt = now
                logoTapCount += 1
                if logoTapCount >= 7 {
                    logoTapCount = 0
                    showEnvironmentSwitcher = true
                }
            }
    }

    private var canSubmit: Bool {
        !teamSlug.trimmingCharacters(in: .whitespaces).isEmpty &&
        !password.isEmpty &&
        !isSubmitting
    }

    private func submit() {
        guard canSubmit else { return }
        isSubmitting = true
        errorMessage = nil
        Task {
            defer { isSubmitting = false }
            do {
                let response = try await deps.authEndpoints.login(
                    teamSlug: teamSlug.trimmingCharacters(in: .whitespaces),
                    password: password
                )
                deps.authSession.signIn(response: response)
            } catch APIError.http(let status, _, let message) where status == 401 {
                errorMessage = message ?? "Invalid team code or password."
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
