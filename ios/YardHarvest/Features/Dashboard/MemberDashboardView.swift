import SwiftUI

/// Activity-feed style dashboard for plot-holding members. No admin KPIs —
/// just what's relevant to a member: today's volunteer opportunities, what's
/// coming up, what they have checked out, and new knowledge articles.
struct MemberDashboardView: View {
    let garden: Garden

    enum Route: Hashable { case events, shifts, harvest, dues }

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                GardenCard(garden: garden, height: 168)

                MyDuesSummaryCard(garden: garden)

                NavigationLink(value: Route.shifts) {
                    VolunteerOpportunitiesCard(garden: garden)
                }
                .buttonStyle(.plain)

                NavigationLink(value: Route.events) {
                    UpcomingEventsCard(garden: garden)
                }
                .buttonStyle(.plain)

                CheckedOutToolsCard(garden: garden, onlyMine: true)
            }
            .padding(.horizontal, YH.Space.md)
            .padding(.bottom, YH.Space.xl)
        }
        .background(YH.canvas)
        .navigationDestination(for: Route.self) { route in
            switch route {
            case .events: EventsView(garden: garden)
            case .shifts: ShiftsView(garden: garden)
            case .harvest: HarvestLogView(garden: garden)
            case .dues: MyDuesView(garden: garden)
            }
        }
    }
}

/// Compact card summarizing the signed-in user's outstanding dues for the
/// active garden. Tapping drills into the full `MyDuesView`. Self-loads.
private struct MyDuesSummaryCard: View {
    let garden: Garden
    @State private var dues: [DuesRecord] = []
    @State private var loaded = false

    private var outstanding: Double { dues.reduce(0) { $0 + $1.balance } }
    private var unpaidRecords: [DuesRecord] { dues.filter { !$0.isPaid && $0.balance > 0 } }

    var body: some View {
        if loaded && unpaidRecords.isEmpty {
            EmptyView()
        } else {
            NavigationLink(value: MemberDashboardView.Route.dues) {
                YHCard {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            Image(systemName: "dollarsign.circle.fill")
                                .font(.system(size: 14, weight: .semibold))
                                .foregroundStyle(YH.ink)
                                .frame(width: 28, height: 28)
                                .background(YH.lime)
                                .clipShape(RoundedRectangle(cornerRadius: 8))
                            Text("My Dues").font(.yhHeadline).foregroundStyle(YH.ink)
                            Spacer()
                            Image(systemName: "chevron.right")
                                .font(.system(size: 13, weight: .semibold))
                                .foregroundStyle(YH.muted)
                        }
                        if loaded {
                            HStack(alignment: .firstTextBaseline) {
                                Text("$\(String(format: "%.2f", outstanding))")
                                    .font(.system(size: 26, weight: .bold))
                                    .tracking(-0.4)
                                    .foregroundStyle(YH.ink)
                                Text("outstanding").font(.yhSubheadline).foregroundStyle(YH.muted)
                                Spacer()
                                YHPill(text: "Pay Now", tint: YH.ink, background: YH.lime)
                            }
                        } else {
                            YHSkeletonBlock(height: 22)
                        }
                    }
                }
            }
            .buttonStyle(.plain)
            .task(id: garden.id) {
                dues = (try? await APIClient.shared.myDues(gardenID: garden.id)) ?? []
                loaded = true
            }
        }
    }
}
