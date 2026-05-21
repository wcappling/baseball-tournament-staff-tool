import SwiftUI

struct EnvironmentSwitcherView: View {
    @Environment(AppDependencies.self) private var deps
    @Environment(\.dismiss) private var dismiss

    @State private var selected: AppEnvironment
    @State private var customURL: String
    @State private var error: String?

    init() {
        let resolver = EnvironmentResolver()
        _selected = State(initialValue: resolver.selected)
        _customURL = State(initialValue: resolver.customURLString)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Backend") {
                    Picker("Environment", selection: $selected) {
                        ForEach(AppEnvironment.allCases) { env in
                            Text(env.displayName).tag(env)
                        }
                    }
                    .pickerStyle(.inline)
                    .labelsHidden()
                }

                if selected == .custom {
                    Section("Custom URL") {
                        TextField("https://...", text: $customURL)
                            .textInputAutocapitalization(.never)
                            .autocorrectionDisabled()
                            .keyboardType(.URL)
                        Text("HTTPS only.")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                if let error {
                    Section { Text(error).foregroundStyle(.red) }
                }
            }
            .navigationTitle("Debug")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save", action: save)
                }
            }
        }
    }

    private func save() {
        deps.environment.selected = selected
        deps.environment.customURLString = customURL
        guard deps.environment.resolveBaseURL() != nil else {
            error = "Custom URL must be a valid HTTPS URL."
            return
        }
        deps.rebuildAPIClient()
        dismiss()
    }
}
