import SwiftUI

struct ShiftsView: View {
    let garden: Garden

    @State private var shifts: [VolunteerShift] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if shifts.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<3, id: \.self) { _ in YHSkeletonCard(rows: 2) }
                    }.padding()
                }
            } else if shifts.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if shifts.isEmpty {
                YHEmpty(systemImage: "person.2.fill",
                        title: "No shifts scheduled",
                        message: "Check back when shifts are posted.")
            } else {
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
                        VStack(spacing: 0) {
                            Text(date.formatted(.dateTime.month(.abbreviated)).uppercased())
                                .font(.system(size: 10, weight: .bold))
                                .tracking(0.6).foregroundStyle(YH.muted)
                            Text(date.formatted(.dateTime.day()))
                                .font(.system(size: 20, weight: .bold))
                                .foregroundStyle(YH.ink)
                        }
                        .frame(width: 50, height: 50)
                        .background(YH.surface)
                        .clipShape(RoundedRectangle(cornerRadius: 10))
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
