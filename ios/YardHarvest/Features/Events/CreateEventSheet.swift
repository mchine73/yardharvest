import SwiftUI

/// Create a garden event from the phone — the web's event form,
/// field-for-field. Reached from the Events screen's "+" for anyone whose
/// role carries the EVENTS capability (organizer, co-organizer, volunteer
/// lead); the backend enforces the same map.
struct CreateEventSheet: View {
    let garden: Garden
    let onCreated: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var description = ""
    @State private var eventType = "workday"
    @State private var eventDate = Calendar.current.nextDate(
        after: .now, matching: DateComponents(hour: 9, minute: 0),
        matchingPolicy: .nextTime) ?? .now
    @State private var durationHours = 2.0
    @State private var hasCap = false
    @State private var maxVolunteers = 10
    @State private var recurring = "none"
    @State private var isSaving = false
    @State private var errorMessage: String?

    /// The web form's exact type list.
    private static let types: [(id: String, label: String)] = [
        ("workday", "Workday"), ("workshop", "Workshop"), ("social", "Social"),
        ("meeting", "Meeting"), ("harvest_day", "Harvest Day"),
    ]
    private static let repeats: [(id: String, label: String)] = [
        ("none", "One-time"), ("weekly", "Weekly"),
        ("biweekly", "Every 2 weeks"), ("monthly", "Monthly"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section("What") {
                    TextField("Title (e.g. Spring planting day)", text: $title)
                    Picker("Type", selection: $eventType) {
                        ForEach(Self.types, id: \.id) { Text($0.label).tag($0.id) }
                    }
                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                }
                Section("When") {
                    DatePicker("Starts", selection: $eventDate)
                    Stepper(value: $durationHours, in: 0.5...12, step: 0.5) {
                        HStack {
                            Text("Duration")
                            Spacer()
                            Text(durationLabel).foregroundStyle(.secondary)
                        }
                    }
                    Picker("Repeats", selection: $recurring) {
                        ForEach(Self.repeats, id: \.id) { Text($0.label).tag($0.id) }
                    }
                    if recurring != "none" {
                        Text("Creates this event plus the next 8 occurrences.")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
                Section("Volunteers") {
                    Toggle("Limit spots", isOn: $hasCap.animation())
                    if hasCap {
                        Stepper("Max \(maxVolunteers) people",
                                value: $maxVolunteers, in: 1...500)
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(YH.danger)
                }
            }
            .navigationTitle("New Event")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(YH.muted)
                        .disabled(isSaving)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if isSaving {
                        ProgressView()
                    } else {
                        Button("Create") { Task { await save() } }
                            .fontWeight(.semibold)
                            .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty)
                    }
                }
            }
            .interactiveDismissDisabled(isSaving)
        }
    }

    private var durationLabel: String {
        durationHours == durationHours.rounded()
            ? "\(Int(durationHours))h"
            : String(format: "%.1fh", durationHours)
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        // Naive local datetime — the backend stores garden-local time.
        let formatter = DateFormatter()
        formatter.dateFormat = "yyyy-MM-dd'T'HH:mm:ss"
        do {
            _ = try await APIClient.shared.createEvent(
                gardenID: garden.id,
                body: .init(title: title.trimmingCharacters(in: .whitespaces),
                            description: description.trimmingCharacters(in: .whitespacesAndNewlines),
                            event_type: eventType,
                            event_date: formatter.string(from: eventDate),
                            duration_hours: durationHours,
                            max_volunteers: hasCap ? maxVolunteers : nil,
                            recurring: recurring))
            Haptics.success()
            onCreated()
            dismiss()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
