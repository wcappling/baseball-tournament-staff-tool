import SwiftUI

struct ShortlistEditorView: View {
    @Environment(AppDependencies.self) private var deps
    @Environment(\.dismiss) private var dismiss

    let tournament: Tournament
    let onCommit: (ShortlistResponse?) async -> Void

    @State private var status: ShortlistStatus
    @State private var priority: Int
    @State private var notes: String
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    init(tournament: Tournament, onCommit: @escaping (ShortlistResponse?) async -> Void) {
        self.tournament = tournament
        self.onCommit = onCommit
        _status = State(initialValue: tournament.shortlistStatus.flatMap(ShortlistStatus.init) ?? .watch)
        _priority = State(initialValue: tournament.shortlistPriority ?? 3)
        _notes = State(initialValue: tournament.shortlistNotes ?? "")
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Status") {
                    Picker("Status", selection: $status) {
                        ForEach(ShortlistStatus.allCases) { option in
                            Text(option.displayName).tag(option)
                        }
                    }
                    .pickerStyle(.segmented)
                }

                Section {
                    Stepper(value: $priority, in: 1...10) {
                        HStack {
                            Text("Priority")
                            Spacer()
                            Text("\(priority)").foregroundStyle(.secondary)
                        }
                    }
                } header: {
                    Text("Priority")
                } footer: {
                    Text("Lower numbers come first in your shortlist.")
                }

                Section("Notes") {
                    TextField("Notes", text: $notes, axis: .vertical)
                        .lineLimit(3...8)
                }

                if let errorMessage {
                    Section { Text(errorMessage).foregroundStyle(.red) }
                }
            }
            .navigationTitle(tournament.name)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    if isSubmitting {
                        ProgressView()
                    } else {
                        Button("Save", action: save)
                    }
                }
            }
        }
    }

    private func save() {
        isSubmitting = true
        errorMessage = nil
        Task {
            defer { isSubmitting = false }
            do {
                let endpoints = ShortlistEndpoints(client: deps.apiClient)
                let response = try await endpoints.update(
                    tournamentId: tournament.id,
                    update: ShortlistUpdate(status: status, priority: priority, notes: notes)
                )
                await onCommit(response)
                dismiss()
            } catch {
                errorMessage = error.localizedDescription
            }
        }
    }
}
