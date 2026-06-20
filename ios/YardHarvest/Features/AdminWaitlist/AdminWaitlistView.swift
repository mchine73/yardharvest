import SwiftUI

/// Manager-only waitlist screen. Lists everyone currently in the queue,
/// in request order, with two actions per row: **Decline** (immediate)
/// and **Offer Plot** which pops a sheet of available plots to assign
/// the member onto. Reached from the dashboard's Waitlist stat tile.
struct AdminWaitlistView: View {
    let garden: Garden

    @State private var entries: [WaitlistEntry] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var workingEntryIDs: Set<Int> = []
    @State private var actionToast: String?
    @State private var offerTarget: WaitlistEntry?

    private var waitingEntries: [WaitlistEntry] {
        entries.filter { $0.status == "waiting" }
            .sorted { ($0.requestedAt ?? .distantPast) < ($1.requestedAt ?? .distantPast) }
    }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: waitingEntries.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 3) {
            YHEmpty(systemImage: "person.2.slash",
                    title: "No one on the waitlist",
                    message: "Members who join the waitlist will show up here.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    heroBand
                    ForEach(Array(waitingEntries.enumerated()), id: \.element.id) { pair in
                        waitlistRow(pair.element, position: pair.offset + 1)
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Waitlist")
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
        .sheet(item: $offerTarget) { entry in
            OfferPlotSheet(garden: garden, entry: entry) { result in
                offerTarget = nil
                if let result {
                    replace(result.waitlistEntry)
                    Haptics.success()
                    showToast("Assigned \(entry.userName) to \(result.plot.displayLabel).")
                }
            }
        }
        .task(id: garden.id) { await load() }
    }

    private var heroBand: some View {
        YHBand(tint: .lime) {
            HStack(spacing: 12) {
                YHIconTile(systemImage: "person.2.fill",
                           size: 48, background: YH.ink, foreground: YH.lime)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(waitingEntries.count) waiting")
                        .font(.yhTitle3).foregroundStyle(YH.ink)
                    Text("Listed in the order they signed up. Offer a plot when one frees up.")
                        .font(.yhCaption).foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    private func waitlistRow(_ entry: WaitlistEntry, position: Int) -> some View {
        let working = workingEntryIDs.contains(entry.id)
        return YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                HStack(spacing: 12) {
                    YHAvatar(name: entry.userName, size: 44)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(entry.userName)
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        HStack(spacing: 6) {
                            Text("#\(position)")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                            if let when = entry.requestedAt {
                                Text("·").font(.yhCaption).foregroundStyle(YH.muted)
                                Text(when.formatted(.relative(presentation: .named)))
                                    .font(.yhCaption).foregroundStyle(YH.muted)
                            }
                        }
                    }
                    Spacer()
                    if let pref = entry.plotSizePref, !pref.isEmpty {
                        YHPill(text: pref.capitalized, tint: YH.ink, background: YH.surface)
                    }
                }
                if let note = entry.notes, !note.isEmpty {
                    Text(note)
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.muted)
                        .lineLimit(3)
                }
                HStack(spacing: YH.Space.sm) {
                    YHButton(title: "Decline",
                             systemImage: "xmark.circle",
                             style: .ghost,
                             isLoading: false) {
                        Task { await decline(entry) }
                    }
                    .disabled(working)
                    YHButton(title: "Offer Plot",
                             systemImage: "checkmark.seal.fill",
                             style: .lime,
                             isLoading: working) {
                        offerTarget = entry
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
        do { entries = try await APIClient.shared.adminListWaitlist(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func decline(_ entry: WaitlistEntry) async {
        workingEntryIDs.insert(entry.id)
        defer { workingEntryIDs.remove(entry.id) }
        do {
            let updated = try await APIClient.shared.declineWaitlistEntry(
                gardenID: garden.id, entryID: entry.id)
            replace(updated)
            Haptics.warning()
            showToast("Declined \(entry.userName).")
        } catch let e as APIError {
            errorMessage = e.errorDescription; Haptics.error()
        } catch {
            errorMessage = error.localizedDescription; Haptics.error()
        }
    }

    private func replace(_ updated: WaitlistEntry) {
        if let i = entries.firstIndex(where: { $0.id == updated.id }) {
            entries[i] = updated
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

/// Sheet that asks the admin which currently-available plot to assign
/// the waitlisted member to. Backend rejects approval without a plot
/// id, so we collect it here. Filters the plot list to `available` to
/// avoid attempts to assign to already-taken plots.
private struct OfferPlotSheet: View {
    let garden: Garden
    let entry: WaitlistEntry
    let onFinish: (APIClient.WaitlistApproveResponse?) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var plots: [Plot] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var assigningPlotID: Int?

    private var availablePlots: [Plot] {
        plots.filter { $0.status == "available" }
            .sorted { $0.plotNumber.localizedStandardCompare($1.plotNumber) == .orderedAscending }
    }

    var body: some View {
        NavigationStack {
            YHLoadable(isLoading: isLoading,
                       isEmpty: availablePlots.isEmpty,
                       errorMessage: errorMessage,
                       onRetry: { await load() },
                       skeletonCards: 4) {
                YHEmpty(systemImage: "tray.fill",
                        title: "No available plots",
                        message: "There's no open plot to offer right now. Free one up first, then come back.")
            } content: {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        header
                        ForEach(availablePlots) { plot in
                            plotRow(plot)
                        }
                    }
                    .padding(YH.Space.md)
                }
            }
            .background(YH.canvas)
            .navigationTitle("Offer Plot")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { onFinish(nil); dismiss() }
                }
            }
            .task { await load() }
        }
    }

    private var header: some View {
        YHCard {
            HStack(spacing: 12) {
                YHAvatar(name: entry.userName, size: 40)
                VStack(alignment: .leading, spacing: 2) {
                    Text(entry.userName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text("Pick a plot to assign them onto.")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                Spacer()
            }
        }
    }

    private func plotRow(_ plot: Plot) -> some View {
        let assigning = assigningPlotID == plot.id
        return Button {
            Haptics.tap()
            Task { await approve(plot) }
        } label: {
            HStack(spacing: 12) {
                YHIconTile(systemImage: "square.grid.3x3.fill",
                           background: YH.lime, foreground: YH.ink)
                VStack(alignment: .leading, spacing: 2) {
                    Text(plot.displayLabel).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    if let size = plot.size, !size.isEmpty {
                        Text(size.capitalized).font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
                Spacer()
                if assigning {
                    ProgressView()
                } else {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
            }
            .padding(YH.Space.md)
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
        .buttonStyle(.plain)
        .disabled(assigningPlotID != nil)
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do { plots = try await APIClient.shared.adminListPlots(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func approve(_ plot: Plot) async {
        assigningPlotID = plot.id
        defer { assigningPlotID = nil }
        do {
            let response = try await APIClient.shared.approveWaitlistEntry(
                gardenID: garden.id, entryID: entry.id, plotID: plot.id)
            onFinish(response)
            dismiss()
        } catch let e as APIError {
            errorMessage = e.errorDescription; Haptics.error()
        } catch {
            errorMessage = error.localizedDescription; Haptics.error()
        }
    }
}
