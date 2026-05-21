import SwiftUI

struct TournamentFiltersView: View {
    @Environment(\.dismiss) private var dismiss

    @State private var working: TournamentFilters
    @State private var sortKey: TournamentSort
    @State private var startDate: Date
    @State private var endDate: Date
    @State private var useStart: Bool
    @State private var useEnd: Bool

    let availableDivisions: [String]
    let knownSources: [String]
    let onApply: (TournamentFilters, TournamentSort) -> Void
    let onReset: () -> Void

    init(
        filters: TournamentFilters,
        sort: TournamentSort,
        availableDivisions: [String],
        knownSources: [String] = ["ncs", "usssa", "perfect_game"],
        onApply: @escaping (TournamentFilters, TournamentSort) -> Void,
        onReset: @escaping () -> Void
    ) {
        _working = State(initialValue: filters)
        _sortKey = State(initialValue: sort)
        _startDate = State(initialValue: filters.startOnOrAfter ?? Date())
        _endDate = State(initialValue: filters.endOnOrBefore ?? Date())
        _useStart = State(initialValue: filters.startOnOrAfter != nil)
        _useEnd = State(initialValue: filters.endOnOrBefore != nil)
        self.availableDivisions = availableDivisions
        self.knownSources = knownSources
        self.onApply = onApply
        self.onReset = onReset
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("Search") {
                    TextField("Tournament name", text: Binding(
                        get: { working.query ?? "" },
                        set: { working.query = $0.isEmpty ? nil : $0 }
                    ))
                    .textInputAutocapitalization(.never)
                }

                Section("Sources") {
                    ForEach(knownSources, id: \.self) { source in
                        Toggle(source.uppercased(), isOn: Binding(
                            get: { working.sources.contains(source) },
                            set: { isOn in
                                if isOn { working.sources.insert(source) } else { working.sources.remove(source) }
                            }
                        ))
                    }
                }

                Section("Age Division") {
                    TextField("e.g. 8U", text: Binding(
                        get: { working.age ?? "" },
                        set: { working.age = $0.isEmpty ? nil : $0.uppercased() }
                    ))
                    .textInputAutocapitalization(.characters)
                    .autocorrectionDisabled()
                }

                if !availableDivisions.isEmpty {
                    Section("Specific Divisions") {
                        ForEach(availableDivisions, id: \.self) { division in
                            Toggle(division, isOn: Binding(
                                get: { working.divisions.contains(division) },
                                set: { isOn in
                                    if isOn { working.divisions.insert(division) } else { working.divisions.remove(division) }
                                }
                            ))
                        }
                    }
                }

                Section("Thresholds") {
                    Stepper(value: Binding(
                        get: { working.teamCountThreshold ?? 0 },
                        set: { working.teamCountThreshold = $0 == 0 ? nil : $0 }
                    ), in: 0...64) {
                        HStack {
                            Text("Min teams")
                            Spacer()
                            Text(working.teamCountThreshold.map(String.init) ?? "Any")
                                .foregroundStyle(.secondary)
                        }
                    }

                    Stepper(value: Binding(
                        get: { working.radiusMiles ?? 0 },
                        set: { working.radiusMiles = $0 == 0 ? nil : $0 }
                    ), in: 0...1000, step: 25) {
                        HStack {
                            Text("Max distance")
                            Spacer()
                            Text(working.radiusMiles.map { "\($0) mi" } ?? "Any")
                                .foregroundStyle(.secondary)
                        }
                    }
                }

                Section("Dates") {
                    Toggle("Start on or after", isOn: $useStart)
                    if useStart {
                        DatePicker("", selection: $startDate, displayedComponents: .date).labelsHidden()
                    }
                    Toggle("End on or before", isOn: $useEnd)
                    if useEnd {
                        DatePicker("", selection: $endDate, displayedComponents: .date).labelsHidden()
                    }
                    Toggle("Single-day only", isOn: Binding(
                        get: { working.singleDay ?? false },
                        set: { working.singleDay = $0 ? true : nil }
                    ))
                }

                Section("Sort") {
                    Picker("Sort by", selection: $sortKey) {
                        ForEach(TournamentSort.allCases) { option in
                            Text(option.displayName).tag(option)
                        }
                    }
                }

                Section {
                    Button("Reset all", role: .destructive) {
                        onReset()
                        dismiss()
                    }
                }
            }
            .navigationTitle("Filters")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Apply") {
                        working.startOnOrAfter = useStart ? startDate : nil
                        working.endOnOrBefore = useEnd ? endDate : nil
                        onApply(working, sortKey)
                        dismiss()
                    }
                }
            }
        }
    }
}
