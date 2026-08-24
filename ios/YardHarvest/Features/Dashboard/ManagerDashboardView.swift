import SwiftUI

/// Manager dashboard — bento grid layout with the garden card hero, then a
/// 2×2 stat grid, a hero "Today" band, then drillable sections.
struct ManagerDashboardView: View {
    let garden: Garden

    @State private var payload: DashboardPayload?
    @State private var isLoading = false
    @State private var errorMessage: String?

    enum Route: Hashable { case events, announcements, waitlist, harvest, plots, shifts, payments, reviews, community }

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                GardenCard(garden: garden)

                if let payload {
                    statBento(payload)
                    todayBand(payload)
                    paymentsBand
                    if !payload.upcomingEvents.isEmpty {
                        NavigationLink(value: Route.events) { eventsSection(payload.upcomingEvents) }
                            .buttonStyle(.plain)
                    }
                    if !payload.recentAnnouncements.isEmpty {
                        NavigationLink(value: Route.announcements) {
                            announcementsSection(payload.recentAnnouncements)
                        }
                        .buttonStyle(.plain)
                    }
                    if !payload.recentPhotos.isEmpty {
                        photosSection(payload.recentPhotos)
                    }
                } else if isLoading {
                    YHSkeletonBento()
                } else if let errorMessage {
                    YHErrorState(message: errorMessage) { Task { await load() } }
                        .frame(minHeight: 240)
                }
            }
            .padding(.horizontal, YH.Space.md)
            .padding(.bottom, YH.Space.xl)
        }
        .background(YH.canvas)
        .navigationDestination(for: Route.self) { route in
            switch route {
            case .events: EventsView(garden: garden)
            case .announcements: AnnouncementsView(garden: garden)
            case .waitlist: AdminWaitlistView(garden: garden)
            case .harvest: HarvestLogView(garden: garden)
            case .plots: PlotsView(garden: garden)
            case .shifts: ShiftsView(garden: garden)
            case .payments: PaymentHubView(garden: garden)
            case .community: CommunityView(garden: garden)
            case .reviews: AdminReviewsView(garden: garden)
            }
        }
        .task(id: garden.id) { await load() }
        .refreshable { await load(showSpinner: false) }
    }

    // MARK: - Sections

    private func statBento(_ p: DashboardPayload) -> some View {
        VStack(spacing: YH.Space.sm) {
            HStack(spacing: YH.Space.sm) {
                NavigationLink(value: Route.plots) {
                    YHStatTile(label: "Occupancy",
                               value: "\(Int(p.plots.occupancyPct.rounded()))%",
                               detail: "\(p.plots.assigned) of \(p.plots.total) plots",
                               systemImage: "chart.pie.fill")
                }
                .buttonStyle(.plain)

                // Community replaces the Waitlist tile — the waitlist count
                // still loads with the dashboard, but day-to-day it's a
                // niche admin task; the wall is where members actually are.
                // Waitlist management moved to the Plots screen's toolbar.
                NavigationLink(value: Route.community) {
                    YHStatTile(label: "Community",
                               value: "Wall",
                               detail: p.waitlistCount > 0
                                   ? "\(p.waitlistCount) on the waitlist too"
                                   : "posts from your members",
                               systemImage: "bubble.left.and.bubble.right.fill")
                }
                .buttonStyle(.plain)
            }
            HStack(spacing: YH.Space.sm) {
                NavigationLink(value: Route.harvest) {
                    YHStatTile(label: "Harvest",
                               value: "\(formatted(p.totalHarvestLbs)) lb",
                               detail: "this season",
                               systemImage: "basket.fill")
                }
                .buttonStyle(.plain)

                // "Reviews" replaces the old "Expiring" tile so the
                // dashboard surfaces actionable admin work (plot
                // reservations awaiting approval) instead of a passive
                // count of renewals. Accents when there's something to
                // do so a busy organizer can spot it at a glance.
                NavigationLink(value: Route.reviews) {
                    // One number for everything awaiting a human decision:
                    // plot reservations plus wall posts the moderator held.
                    let pending = p.plots.reserved + (p.wallFlaggedCount ?? 0)
                    YHStatTile(label: "Reviews",
                               value: "\(pending)",
                               detail: reviewsDetail(reservations: p.plots.reserved,
                                                     flags: p.wallFlaggedCount ?? 0),
                               systemImage: "list.bullet.clipboard.fill")
                }
                .buttonStyle(.plain)
            }
        }
    }

    /// Tap-to-Pay entry point — sits with the bento KPIs so it's the first
    /// thing a manager sees when they want to take money.
    private var paymentsBand: some View {
        NavigationLink(value: Route.payments) {
            HStack(spacing: 14) {
                ZStack {
                    RoundedRectangle(cornerRadius: 14).fill(YH.ink)
                    Image(systemName: "wave.3.right")
                        .font(.system(size: 22, weight: .semibold))
                        .foregroundStyle(YH.lime)
                }
                .frame(width: 56, height: 56)
                VStack(alignment: .leading, spacing: 2) {
                    Text("Payments")
                        .font(.yhTitle3).foregroundStyle(YH.ink)
                    Text("Collect dues or run a Tap-to-Pay sale.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
                Spacer()
                Image(systemName: "chevron.right")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(YH.muted)
            }
            .padding(YH.Space.md)
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.lg)
                        .strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func todayBand(_ p: DashboardPayload) -> some View {
        let now = Date()
        let endOfDay = Calendar.current.date(byAdding: .day, value: 1, to: Calendar.current.startOfDay(for: now)) ?? now
        let today = Array(p.upcomingEvents.filter { ($0.eventDate ?? .distantPast) < endOfDay }.prefix(2))
        if !today.isEmpty {
            YHBand(tint: .lime) {
                VStack(alignment: .leading, spacing: 6) {
                    Text("TODAY")
                        .font(.yhCaptionMed).tracking(0.8)
                    Text(today.first?.title ?? "")
                        .font(.yhTitle3)
                    if today.count > 1 {
                        Text("+ \(today.count - 1) more")
                            .font(.yhCaption)
                            .foregroundStyle(YH.ink.opacity(0.7))
                    }
                }
            }
        }
    }

    private func eventsSection(_ events: [DashboardEvent]) -> some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: "Upcoming Events",
                                trailing: "\(events.count)",
                                showsChevron: true)
                ForEach(events.prefix(3)) { e in
                    HStack(alignment: .top, spacing: 12) {
                        dateChip(for: e.eventDate)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(e.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                            if let d = e.eventDate {
                                Text(d.formatted(date: .omitted, time: .shortened))
                                    .font(.yhCaption).foregroundStyle(YH.muted)
                            }
                        }
                        Spacer()
                        if let going = e.rsvpGoing, going > 0 {
                            YHPill(text: "\(going) going", tint: YH.ink, background: YH.lime)
                        }
                    }
                    if e.id != events.prefix(3).last?.id { Divider().overlay(YH.border) }
                }
            }
        }
    }

    private func announcementsSection(_ items: [Announcement]) -> some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: "Recent Announcements", showsChevron: true)
                ForEach(items.prefix(3)) { a in
                    VStack(alignment: .leading, spacing: 4) {
                        HStack {
                            if a.pinned == true {
                                Image(systemName: "pin.fill")
                                    .font(.caption).foregroundStyle(YH.ink)
                            }
                            Text(a.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        }
                        Text(a.body)
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.muted)
                            .lineLimit(2)
                        if let when = a.createdAt {
                            Text(when.formatted(.relative(presentation: .named)))
                                .font(.yhCaption)
                                .foregroundStyle(.tertiary)
                        }
                    }
                    if a.id != items.prefix(3).last?.id { Divider().overlay(YH.border) }
                }
            }
        }
    }

    private func photosSection(_ photos: [DashboardPhoto]) -> some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: "Photo Wall", showsChevron: true)
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(photos) { p in
                            AsyncImage(url: AppEnvironment.mediaURL(p.photoUrl)) { phase in
                                switch phase {
                                case .success(let img): img.resizable().scaledToFill()
                                case .empty: YH.surface
                                default: YH.surface.overlay(Image(systemName: "photo").foregroundStyle(YH.muted))
                                }
                            }
                            .frame(width: 110, height: 110)
                            .clipShape(RoundedRectangle(cornerRadius: 12))
                        }
                    }
                }
            }
        }
    }

    // MARK: - Helpers

    @ViewBuilder
    private func dateChip(for date: Date?) -> some View {
        if let date {
            YHDateChip(date: date, emphasis: .lime, size: 44)
        }
    }

private func formatted(_ v: Double) -> String {
        let f = NumberFormatter()
        f.maximumFractionDigits = v < 10 ? 1 : 0
        return f.string(from: NSNumber(value: v)) ?? "0"
    }

    private func reviewsDetail(reservations: Int, flags: Int) -> String {
        switch (reservations, flags) {
        case (0, 0): return "all caught up"
        case (_, 0): return reservations == 1 ? "reservation to review" : "reservations to review"
        case (0, _): return flags == 1 ? "flagged wall post" : "flagged wall posts"
        default:     return "\(reservations) reservations · \(flags) wall"
        }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { payload = try await APIClient.shared.dashboard(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

/// Lightweight placeholder for routes we haven't implemented yet — keeps the
/// dashboard tappable without dragging in every sub-feature.
struct PlaceholderScreen: View {
    let title: String
    var body: some View {
        VStack {
            YHEmpty(systemImage: "hammer", title: title,
                    message: "This screen is coming soon to YardHarvest for iOS.")
        }
        .navigationTitle(title)
        .navigationBarTitleDisplayMode(.inline)
        .background(YH.canvas)
    }
}
