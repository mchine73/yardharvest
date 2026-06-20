import SwiftUI

struct ShiftsView: View {
    let garden: Garden

    @State private var shifts: [VolunteerShift] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: shifts.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 3) {
            YHEmpty(systemImage: "person.2.fill",
                    title: "No shifts scheduled",
                    message: "Check back when shifts are posted.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    ForEach(shifts) { s in
                        ShiftCard(shift: s) {
                            Task { await signup(s) }
                        } onCancel: {
                            Task { await cancelSignup(s) }
                        }
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Volunteer Shifts")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { shifts = try await APIClient.shared.listShifts(gardenID: garden.id, show: "upcoming") }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func signup(_ s: VolunteerShift) async {
        do {
            try await APIClient.shared.signUpForShift(gardenID: garden.id, shiftID: s.id)
            await load(showSpinner: false)
            Haptics.success()
        } catch let e as APIError { errorMessage = e.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }

    private func cancelSignup(_ s: VolunteerShift) async {
        do {
            try await APIClient.shared.cancelShiftSignup(gardenID: garden.id, shiftID: s.id)
            await load(showSpinner: false)
        } catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct ShiftCard: View {
    let shift: VolunteerShift
    let onSignup: () -> Void
    let onCancel: () -> Void

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .top, spacing: 12) {
                    if let date = shift.shiftDate {
                        YHDateChip(date: date, emphasis: .neutral, size: 50)
                    }
                    VStack(alignment: .leading, spacing: 2) {
                        Text(shift.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let range = shift.timeRange {
                            Text(range).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                    Spacer()
                }
                if let desc = shift.description, !desc.isEmpty {
                    Text(desc).font(.yhSubheadline).foregroundStyle(YH.muted).lineLimit(2)
                }
                HStack {
                    Label("\(shift.signupCount)\(shift.maxVolunteers.map { "/\($0)" } ?? "") signed up",
                          systemImage: "person.2.fill")
                        .font(.yhCaption).foregroundStyle(YH.ink)
                    Spacer()
                    if shift.userSignedUp == true {
                        Button {
                            Haptics.tap()
                            onCancel()
                        } label: {
                            Label("Cancel", systemImage: "xmark")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(YH.muted)
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .background(YH.surface)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                    } else {
                        Button {
                            Haptics.confirm()
                            onSignup()
                        } label: {
                            Label("Sign Up", systemImage: "checkmark")
                                .font(.system(size: 12, weight: .semibold))
                                .foregroundStyle(YH.ink)
                                .padding(.horizontal, 12).padding(.vertical, 6)
                                .background(YH.lime)
                                .clipShape(Capsule())
                        }
                        .buttonStyle(.plain)
                        .disabled(shift.isFull)
                    }
                }
            }
        }
    }
}
