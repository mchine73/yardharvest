import SwiftUI

/// Create a volunteer shift from the phone. Reached from the Shifts screen's
/// "+" for roles carrying the SHIFTS capability (organizer, co-organizer,
/// volunteer lead). Garden Pro server-side, like the rest of shifts.
struct CreateShiftSheet: View {
    let garden: Garden
    let onCreated: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var description = ""
    @State private var shiftDate = Calendar.current.date(
        byAdding: .day, value: 1, to: .now) ?? .now
    @State private var startTime = Calendar.current.date(
        bySettingHour: 9, minute: 0, second: 0, of: .now) ?? .now
    @State private var endTime = Calendar.current.date(
        bySettingHour: 11, minute: 0, second: 0, of: .now) ?? .now
    @State private var hasCap = true
    @State private var maxVolunteers = 6
    @State private var recurring = "none"
    @State private var isSaving = false
    @State private var errorMessage: String?

    private static let repeats: [(id: String, label: String)] = [
        ("none", "One-time"), ("weekly", "Weekly"),
        ("biweekly", "Every 2 weeks"), ("monthly", "Monthly"),
    ]

    private var timesValid: Bool {
        let cal = Calendar.current
        let s = cal.dateComponents([.hour, .minute], from: startTime)
        let e = cal.dateComponents([.hour, .minute], from: endTime)
        return (e.hour!, e.minute!) > (s.hour!, s.minute!)
    }

    var body: some View {
        NavigationStack {
            Form {
                Section("What") {
                    TextField("Title (e.g. Watering & weeding)", text: $title)
                    TextField("Description (optional)", text: $description, axis: .vertical)
                        .lineLimit(2...4)
                }
                Section("When") {
                    DatePicker("Date", selection: $shiftDate, displayedComponents: .date)
                    DatePicker("Starts", selection: $startTime, displayedComponents: .hourAndMinute)
                    DatePicker("Ends", selection: $endTime, displayedComponents: .hourAndMinute)
                    if !timesValid {
                        Text("The shift has to end after it starts.")
                            .font(.yhCaption).foregroundStyle(YH.danger)
                    }
                    Picker("Repeats", selection: $recurring) {
                        ForEach(Self.repeats, id: \.id) { Text($0.label).tag($0.id) }
                    }
                    if recurring != "none" {
                        Text("Creates this shift plus the next 8 occurrences.")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
                Section("Volunteers") {
                    Toggle("Limit spots", isOn: $hasCap.animation())
                    if hasCap {
                        Stepper("Max \(maxVolunteers) people",
                                value: $maxVolunteers, in: 1...100)
                    }
                }
                if let errorMessage {
                    Text(errorMessage).foregroundStyle(YH.danger)
                }
            }
            .navigationTitle("New Shift")
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
                            .disabled(title.trimmingCharacters(in: .whitespaces).isEmpty
                                      || !timesValid)
                    }
                }
            }
            .interactiveDismissDisabled(isSaving)
        }
    }

    private func save() async {
        isSaving = true
        errorMessage = nil
        defer { isSaving = false }
        let day = DateFormatter()
        day.dateFormat = "yyyy-MM-dd"
        let clock = DateFormatter()
        clock.dateFormat = "HH:mm"
        do {
            _ = try await APIClient.shared.createShift(
                gardenID: garden.id,
                body: .init(title: title.trimmingCharacters(in: .whitespaces),
                            description: description.trimmingCharacters(in: .whitespacesAndNewlines),
                            shift_date: day.string(from: shiftDate),
                            start_time: clock.string(from: startTime),
                            end_time: clock.string(from: endTime),
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
