import SwiftUI

/// Public garden detail with the photo banner hero, info card, plots
/// section, and a context-aware CTA (take a plot, view your plot, or join
/// the waitlist).
struct GardenDetailView: View {
    let gardenID: Int

    @Environment(GardenStore.self) private var gardenStore
    @State private var detail: GardenDetail?
    @State private var plots: [Plot] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var infoMessage: String?
    @State private var showingPlotPicker = false
    @State private var showingWaitlist = false
    @State private var showingMessageOrganizer = false

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                if let detail {
                    GardenCard(garden: detail.asGarden, height: 200)
                    statsCard(detail)
                    membershipCTA(detail)
                    if let orgID = detail.organizerId,
                       let orgName = detail.organizerName,
                       !detail.userIsOrganizer {
                        messageOrganizerButton(orgID: orgID, orgName: orgName)
                    }
                    if let info = infoMessage {
                        Text(info)
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.ink)
                            .padding(YH.Space.md)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(YH.limeSoft)
                            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                    }
                    if let desc = detail.description, !desc.isEmpty {
                        YHCard {
                            Text(desc)
                                .font(.yhBody)
                                .foregroundStyle(YH.ink.opacity(0.85))
                        }
                    }
                    if let rules = detail.rules, !rules.isEmpty {
                        YHCard {
                            VStack(alignment: .leading, spacing: 6) {
                                Text("Garden Rules").font(.yhHeadline).foregroundStyle(YH.ink)
                                Text(rules).font(.yhBody).foregroundStyle(YH.ink.opacity(0.85))
                            }
                        }
                    }
                } else if isLoading {
                    YHSkeletonBlock(height: 200, radius: YH.Radius.lg)
                    YHSkeletonCard(rows: 3)
                } else if let errorMessage {
                    YHErrorState(message: errorMessage) { Task { await load() } }
                        .frame(minHeight: 240)
                }
            }
            .padding(.horizontal, YH.Space.md)
            .padding(.vertical, YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle("")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: gardenID) { await load() }
        .refreshable { await load(showSpinner: false) }
        .sheet(isPresented: $showingPlotPicker) {
            PlotPickerSheet(gardenID: gardenID, plots: plots) {
                infoMessage = "Plot reserved! The organizer will confirm shortly."
                Task {
                    await load(showSpinner: false)
                    await gardenStore.reload()
                }
            }
        }
        .sheet(isPresented: $showingWaitlist) {
            WaitlistJoinSheet(gardenID: gardenID) {
                infoMessage = "You're on the waitlist — we'll let you know when a plot opens up."
                Task { await load(showSpinner: false) }
            }
        }
        .sheet(isPresented: $showingMessageOrganizer) {
            if let d = detail,
               let orgID = d.organizerId,
               let orgName = d.organizerName {
                ComposeMessageView(recipientID: orgID,
                                   recipientName: orgName,
                                   contextLabel: d.name) {
                    infoMessage = "Message sent to \(orgName)."
                }
            }
        }
    }

    // MARK: - Sections

    private func messageOrganizerButton(orgID: Int, orgName: String) -> some View {
        Button {
            Haptics.tap()
            showingMessageOrganizer = true
        } label: {
            HStack(spacing: 12) {
                ZStack {
                    Circle().fill(YH.lime)
                    Image(systemName: "bubble.left.fill")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
                .frame(width: 36, height: 36)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Message the organizer")
                        .font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text(orgName)
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(YH.muted)
            }
            .padding(YH.Space.md)
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.lg).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func statsCard(_ d: GardenDetail) -> some View {
        YHCard {
            HStack(spacing: 0) {
                stat("\(d.availablePlots ?? 0)", "Open plots")
                Divider().background(YH.border)
                stat("\(d.memberCount ?? 0)", "Members")
                Divider().background(YH.border)
                stat(d.plotFeeAnnual.map { "$\(Int($0))" } ?? "—",
                     "Plot fee /yr")
            }
        }
    }

    private func stat(_ value: String, _ label: String) -> some View {
        VStack(spacing: 2) {
            Text(value).font(.system(size: 22, weight: .bold)).tracking(-0.4)
                .foregroundStyle(YH.ink)
            Text(label.uppercased()).font(.yhCaption).tracking(0.6)
                .foregroundStyle(YH.muted)
        }
        .frame(maxWidth: .infinity)
    }

    @ViewBuilder
    private func membershipCTA(_ d: GardenDetail) -> some View {
        if d.userIsOrganizer {
            YHBand(tint: .lime) {
                Label("You organize this garden.", systemImage: "person.crop.circle.badge.checkmark")
                    .font(.yhBodyMedium)
            }
        } else if d.userHasPlot {
            YHBand(tint: .lime) {
                Label("You have a plot here.", systemImage: "checkmark.seal.fill")
                    .font(.yhBodyMedium)
            }
        } else if d.userHasReservation {
            YHCard {
                VStack(alignment: .leading, spacing: 6) {
                    Label("Reservation pending", systemImage: "clock.fill")
                        .font(.yhHeadline).foregroundStyle(YH.ink)
                    Text("The organizer will confirm your reservation soon.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
            }
        } else if d.userOnWaitlist {
            YHCard {
                VStack(alignment: .leading, spacing: 6) {
                    Label("You're on the waitlist", systemImage: "person.crop.circle.badge.clock")
                        .font(.yhHeadline).foregroundStyle(YH.ink)
                    Text("We'll notify you when a plot opens up.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
            }
        } else {
            VStack(spacing: YH.Space.sm) {
                if (d.availablePlots ?? 0) > 0 {
                    YHButton(title: "Take a Plot",
                             systemImage: "leaf.fill",
                             style: .lime) {
                        Task {
                            plots = (try? await APIClient.shared.publicPlots(gardenID: gardenID)) ?? []
                            showingPlotPicker = true
                        }
                    }
                } else {
                    YHCard {
                        Label("No plots open right now.", systemImage: "info.circle")
                            .font(.yhBody).foregroundStyle(YH.muted)
                    }
                }
                YHButton(title: d.userOnWaitlist ? "On the Waitlist" : "Join the Waitlist",
                         systemImage: "person.crop.circle.badge.plus",
                         style: .ghost) {
                    showingWaitlist = true
                }
                .disabled(d.userOnWaitlist)
            }
        }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do {
            async let detailReq = APIClient.shared.gardenDetail(gardenID: gardenID)
            async let plotsReq  = APIClient.shared.publicPlots(gardenID: gardenID)
            let d = try await detailReq
            let p = (try? await plotsReq) ?? []
            detail = d
            plots = p
        } catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}
