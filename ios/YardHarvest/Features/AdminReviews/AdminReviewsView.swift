import SwiftUI

/// Manager-only "Reviews" inbox — the list of plot reservations that
/// members have submitted and need the admin to approve or decline.
/// Reached from the dashboard's Reviews stat tile. Today this covers
/// reserved plots; future iterations can layer in other admin queues
/// (event approvals, deposit refunds, etc.) using the same list shell.
struct AdminReviewsView: View {
    let garden: Garden

    @State private var plots: [Plot] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    /// Plot IDs currently mid-action so we can disable the row + show
    /// a spinner without re-rendering the whole list.
    @State private var workingPlotIDs: Set<Int> = []
    @State private var actionToast: String?

    private var reservedPlots: [Plot] {
        plots.filter { $0.status == "reserved" }
            .sorted { ($0.reservedAt ?? .distantPast) < ($1.reservedAt ?? .distantPast) }
    }

    var body: some View {
        VStack(spacing: 0) {
        // Above the loadable, not inside it: the Reviews tile's count now
        // includes wall moderation, and a manager arriving with zero
        // reservations but flagged posts must not land on "All caught up"
        // with the real work invisible.
        NavigationLink {
            ModerationView(garden: garden)
        } label: {
            YHCard {
                HStack(spacing: 12) {
                    Image(systemName: "checkmark.shield.fill")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(YH.ink)
                        .frame(width: 36, height: 36)
                        .background(YH.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Community wall").font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text("Flagged and auto-denied posts")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
            }
        }
        .buttonStyle(.plain)
        .padding(.horizontal, YH.Space.md)
        .padding(.top, YH.Space.sm)

        YHLoadable(isLoading: isLoading,
                   isEmpty: reservedPlots.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 3) {
            YHEmpty(systemImage: "checkmark.seal.fill",
                    title: "All caught up",
                    message: "No plot reservations are waiting on your approval.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    heroBand
                    ForEach(reservedPlots) { plot in
                        reservationRow(plot)
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        }
        .background(YH.canvas)
        .navigationTitle("Reviews")
        .navigationBarTitleDisplayMode(.inline)
        .overlay(alignment: .top) {
            if let toast = actionToast {
                Text(toast)
                    .font(.yhCaptionMed)
                    .foregroundStyle(YH.ink)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(YH.lime)
                    .clipShape(Capsule())
                    .padding(.top, 8)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .task(id: garden.id) { await load() }
    }

    private var heroBand: some View {
        YHBand(tint: .lime) {
            HStack(spacing: 12) {
                YHIconTile(systemImage: "list.bullet.clipboard.fill",
                           size: 48, background: YH.ink, foreground: YH.lime)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(reservedPlots.count) reservation\(reservedPlots.count == 1 ? "" : "s")")
                        .font(.yhTitle3).foregroundStyle(YH.ink)
                    Text("Each is a member waiting for your approval to take the plot.")
                        .font(.yhCaption).foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    private func reservationRow(_ plot: Plot) -> some View {
        let working = workingPlotIDs.contains(plot.id)
        return YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                HStack(spacing: 12) {
                    YHAvatar(name: plot.reservedByName ?? "—", size: 44)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(plot.reservedByName ?? "Unknown member")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        HStack(spacing: 6) {
                            Text(plot.displayLabel)
                                .font(.yhCaption).foregroundStyle(YH.muted)
                            if let when = plot.reservedAt {
                                Text("·").font(.yhCaption).foregroundStyle(YH.muted)
                                Text(when.formatted(.relative(presentation: .named)))
                                    .font(.yhCaption).foregroundStyle(YH.muted)
                            }
                        }
                    }
                    Spacer()
                    YHPill(text: "Pending", tint: YH.ink, background: YH.surface)
                }
                if let size = plot.size, !size.isEmpty {
                    Label(size.capitalized, systemImage: "ruler")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                HStack(spacing: YH.Space.sm) {
                    YHButton(title: "Decline",
                             systemImage: "xmark.circle",
                             style: .ghost,
                             isLoading: false) {
                        Task { await decline(plot) }
                    }
                    .disabled(working)
                    YHButton(title: "Approve",
                             systemImage: "checkmark.seal.fill",
                             style: .lime,
                             isLoading: working) {
                        Task { await approve(plot) }
                    }
                    .disabled(working)
                }
            }
        }
    }

    // MARK: - Actions

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { plots = try await APIClient.shared.adminListPlots(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func approve(_ plot: Plot) async {
        workingPlotIDs.insert(plot.id)
        defer { workingPlotIDs.remove(plot.id) }
        do {
            let updated = try await APIClient.shared.confirmReservation(
                gardenID: garden.id, plotID: plot.id)
            replace(updated)
            Haptics.success()
            showToast("Approved \(plot.displayLabel).")
        } catch let e as APIError {
            errorMessage = e.errorDescription; Haptics.error()
        } catch {
            errorMessage = error.localizedDescription; Haptics.error()
        }
    }

    private func decline(_ plot: Plot) async {
        workingPlotIDs.insert(plot.id)
        defer { workingPlotIDs.remove(plot.id) }
        do {
            let updated = try await APIClient.shared.declineReservation(
                gardenID: garden.id, plotID: plot.id)
            replace(updated)
            Haptics.warning()
            showToast("Released \(plot.displayLabel).")
        } catch let e as APIError {
            errorMessage = e.errorDescription; Haptics.error()
        } catch {
            errorMessage = error.localizedDescription; Haptics.error()
        }
    }

    private func replace(_ updated: Plot) {
        if let i = plots.firstIndex(where: { $0.id == updated.id }) {
            plots[i] = updated
        } else {
            plots.append(updated)
        }
    }

    private func showToast(_ text: String) {
        withAnimation(YH.Motion.snappy) { actionToast = text }
        Task {
            try? await Task.sleep(nanoseconds: 1_800_000_000)
            withAnimation(YH.Motion.snappy) { actionToast = nil }
        }
    }
}
