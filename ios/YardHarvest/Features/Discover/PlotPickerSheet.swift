import SwiftUI

/// Pick an available plot to reserve. Reservations are pending organizer
/// confirmation — that flow is owned by the website / Manager dashboard.
struct PlotPickerSheet: View {
    let gardenID: Int
    let plots: [Plot]
    let onReserved: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var reservingID: Int?
    @State private var errorMessage: String?

    private var available: [Plot] { plots.filter { $0.status == "available" } }

    var body: some View {
        NavigationStack {
            Group {
                if available.isEmpty {
                    YHEmpty(systemImage: "leaf",
                            title: "No available plots",
                            message: "Try joining the waitlist instead.")
                } else {
                    ScrollView {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("Choose a plot to reserve. The organizer will confirm shortly.")
                                .font(.yhSubheadline).foregroundStyle(YH.muted)
                                .padding(.horizontal, YH.Space.md)
                            ForEach(available) { plot in
                                Button {
                                    Task { await reserve(plot) }
                                } label: {
                                    plotRow(plot)
                                }
                                .buttonStyle(.plain)
                                .disabled(reservingID != nil)
                                .padding(.horizontal, YH.Space.md)
                            }
                            if let errorMessage {
                                Text(errorMessage)
                                    .font(.yhSubheadline).foregroundStyle(YH.danger)
                                    .padding(.horizontal, YH.Space.md)
                            }
                        }
                        .padding(.vertical, YH.Space.md)
                    }
                }
            }
            .background(YH.canvas)
            .navigationTitle("Take a Plot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } } }
        }
    }

    private func plotRow(_ plot: Plot) -> some View {
        YHCard {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10).fill(YH.lime)
                    Image(systemName: "leaf.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(plot.displayLabel)
                        .font(.yhBodyMedium).foregroundStyle(YH.ink)
                    HStack(spacing: 6) {
                        if let size = plot.size, !size.isEmpty {
                            Text(size).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                        if let sun = plot.sunExposure, !sun.isEmpty {
                            Text("· \(sun.capitalized) sun")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                }
                Spacer()
                if reservingID == plot.id {
                    ProgressView().tint(YH.ink)
                } else {
                    Image(systemName: "arrow.right")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
            }
        }
    }

    private func reserve(_ plot: Plot) async {
        reservingID = plot.id
        errorMessage = nil
        defer { reservingID = nil }
        do {
            _ = try await APIClient.shared.reservePlot(gardenID: gardenID, plotID: plot.id)
            Haptics.success()
            onReserved()
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

/// Lightweight waitlist join sheet — optional size preference and notes.
struct WaitlistJoinSheet: View {
    let gardenID: Int
    let onJoined: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var sizePref = ""
    @State private var notes = ""
    @State private var isSubmitting = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("Tell the organizer what you're looking for. Both fields are optional.")
                                .font(.yhSubheadline)
                                .foregroundStyle(YH.muted)
                            field("Plot size preference", text: $sizePref,
                                  placeholder: "e.g. 4×8 ft or larger")
                            field("Notes for the organizer", text: $notes,
                                  placeholder: "Anything they should know?", multiline: true)
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
                    }
                    YHButton(title: "Join Waitlist",
                             systemImage: "person.crop.circle.badge.plus",
                             style: .dark, isLoading: isSubmitting) {
                        Task { await submit() }
                    }
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("Join Waitlist")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar { ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } } }
        }
    }

    @ViewBuilder
    private func field(_ label: String, text: Binding<String>,
                       placeholder: String, multiline: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.yhCaptionMed).foregroundStyle(YH.muted)
            Group {
                if multiline {
                    TextEditor(text: text)
                        .scrollContentBackground(.hidden)
                        .frame(minHeight: 100, alignment: .topLeading)
                } else {
                    TextField(placeholder, text: text)
                }
            }
            .font(.system(size: 16, weight: .regular))
            .foregroundStyle(YH.ink)
            .padding(12)
            .background(YH.surface)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
    }

    private func submit() async {
        isSubmitting = true
        errorMessage = nil
        defer { isSubmitting = false }
        do {
            _ = try await APIClient.shared.joinWaitlist(
                gardenID: gardenID,
                sizePref: sizePref.trimmingCharacters(in: .whitespacesAndNewlines),
                notes: notes.trimmingCharacters(in: .whitespacesAndNewlines))
            Haptics.success()
            onJoined()
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
