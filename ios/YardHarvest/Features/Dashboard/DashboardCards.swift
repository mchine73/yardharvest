import SwiftUI

// Reusable self-loading dashboard cards backed by member-accessible
// (public) endpoints. Used on both manager and member dashboards. Each card
// loads independently so a slow/failed call never blanks the whole screen.

/// Volunteer shifts in the next two weeks.
struct VolunteerOpportunitiesCard: View {
    let garden: Garden
    @State private var shifts: [VolunteerShift] = []
    @State private var loaded = false

    private var withinTwoWeeks: [VolunteerShift] {
        let cutoff = Calendar.current.date(byAdding: .day, value: 14, to: Date()) ?? Date()
        return shifts.filter { ($0.shiftDate ?? .distantFuture) <= cutoff }
    }

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: "Volunteer Opportunities",
                                systemImage: "person.2.fill",
                                trailing: "Next 2 weeks")
                if !loaded {
                    YHSkeletonBlock(height: 12)
                    YHSkeletonBlock(height: 12)
                } else if withinTwoWeeks.isEmpty {
                    Text("Nothing scheduled in the next two weeks.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                } else {
                    let items = Array(withinTwoWeeks.prefix(4))
                    ForEach(items) { s in
                        HStack(alignment: .top, spacing: 12) {
                            shiftDateChip(for: s.shiftDate)
                            VStack(alignment: .leading, spacing: 2) {
                                Text(s.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                                HStack(spacing: 6) {
                                    if let range = s.timeRange {
                                        Text(range).font(.yhCaption).foregroundStyle(YH.muted)
                                    }
                                    Text("· \(s.signupCount)\(s.maxVolunteers.map { "/\($0)" } ?? "") in")
                                        .font(.yhCaption)
                                        .foregroundStyle(s.isFull ? YH.warning : YH.muted)
                                }
                            }
                            Spacer()
                        }
                        if s.id != items.last?.id { Divider().overlay(YH.border) }
                    }
                }
            }
        }
        .task(id: garden.id) { await load() }
    }

    private func load() async {
        shifts = (try? await APIClient.shared.listShifts(gardenID: garden.id, show: "upcoming")) ?? []
        loaded = true
    }

    @ViewBuilder
    private func shiftDateChip(for date: Date?) -> some View {
        if let date {
            YHDateChip(date: date, emphasis: .neutral, size: 40)
        }
    }
}

/// Upcoming events list.
struct UpcomingEventsCard: View {
    let garden: Garden
    @State private var events: [GardenEvent] = []
    @State private var loaded = false

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: "Upcoming Events", systemImage: "calendar")
                if !loaded {
                    YHSkeletonBlock(height: 12)
                    YHSkeletonBlock(height: 12)
                } else if events.isEmpty {
                    Text("No upcoming events.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                } else {
                    let items = Array(events.prefix(4))
                    ForEach(items) { e in
                        VStack(alignment: .leading, spacing: 2) {
                            Text(e.title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                            HStack {
                                if let d = e.eventDate {
                                    Text(d.formatted(date: .abbreviated, time: .shortened))
                                        .font(.yhCaption).foregroundStyle(YH.muted)
                                }
                                Spacer()
                                if e.rsvpGoing > 0 {
                                    Text("\(e.rsvpGoing) going")
                                        .font(.yhCaptionMed).foregroundStyle(YH.ink)
                                }
                            }
                        }
                        if e.id != items.last?.id { Divider().overlay(YH.border) }
                    }
                }
            }
        }
        .task(id: garden.id) { await load() }
    }

    private func load() async {
        events = (try? await APIClient.shared.listEvents(gardenID: garden.id, show: "upcoming")) ?? []
        loaded = true
    }
}

/// Currently checked-out tools. `onlyMine` filters to the signed-in user's.
struct CheckedOutToolsCard: View {
    let garden: Garden
    var onlyMine: Bool

    @Environment(AuthManager.self) private var auth
    @State private var resources: [GardenResource] = []
    @State private var loaded = false

    private var currentUserID: Int? {
        if case .signedIn(let u) = auth.state { return u.id }
        return nil
    }

    private var checkedOut: [GardenResource] {
        resources.filter { r in
            guard r.isCheckedOut else { return false }
            return onlyMine ? (r.checkedOutToId == currentUserID) : true
        }
    }

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSectionHeader(title: onlyMine ? "My Checked-Out Tools" : "Checked-Out Tools",
                                systemImage: "wrench.and.screwdriver.fill")
                if !loaded {
                    YHSkeletonBlock(height: 12)
                } else if checkedOut.isEmpty {
                    Text(onlyMine ? "You have no tools checked out." : "No tools are out.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                } else {
                    let items = Array(checkedOut.prefix(5))
                    ForEach(items) { r in
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(r.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                                HStack(spacing: 6) {
                                    if !onlyMine, let who = r.checkedOutToName {
                                        Text(who).font(.yhCaption).foregroundStyle(YH.muted)
                                    }
                                    if let due = r.dueDate {
                                        Text("due \(due.formatted(date: .abbreviated, time: .omitted))")
                                            .font(.yhCaption).foregroundStyle(YH.muted)
                                    }
                                }
                            }
                            Spacer()
                            if r.isOverdue {
                                YHPill(text: "Overdue", tint: .white, background: YH.danger)
                            }
                        }
                        if r.id != items.last?.id { Divider().overlay(YH.border) }
                    }
                }
            }
        }
        .task(id: garden.id) { await load() }
    }

    private func load() async {
        resources = (try? await APIClient.shared.listResources(gardenID: garden.id)) ?? []
        loaded = true
    }
}

