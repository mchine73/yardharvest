import SwiftUI

/// Activity-feed style dashboard for plot-holding members. No admin KPIs —
/// just what's relevant to a member: today's volunteer opportunities, what's
/// coming up, what they have checked out, and new knowledge articles.
struct MemberDashboardView: View {
    let garden: Garden

    enum Route: Hashable { case events, shifts, harvest, dues, community }

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

                NavigationLink(value: Route.community) {
                    CommunityWallCard(garden: garden)
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
            case .community: CommunityView(garden: garden)
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

/// Preview of the garden's community wall — the latest few posts, inline on
/// the member's main page so the wall is discovered, not hunted for. Tapping
/// anywhere opens the full wall (composer, replies, likes). Self-loads,
/// like the other member-dashboard cards.
private struct CommunityWallCard: View {
    let garden: Garden
    @State private var posts: [WallComment] = []
    @State private var loaded = false

    /// Latest top-level posts only — replies belong on the full wall.
    private var preview: [WallComment] { Array(posts.filter { $0.parentId == nil }.prefix(3)) }

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                HStack(spacing: 8) {
                    Image(systemName: "bubble.left.and.bubble.right.fill")
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(YH.ink)
                        .frame(width: 28, height: 28)
                        .background(YH.lime)
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                    Text("Community").font(.yhHeadline).foregroundStyle(YH.ink)
                    Spacer()
                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
                if !loaded {
                    YHSkeletonBlock(height: 44)
                } else if preview.isEmpty {
                    Text("Nothing on the wall yet — be the first to say hello.")
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.muted)
                } else {
                    ForEach(preview) { post in
                        HStack(alignment: .top, spacing: 8) {
                            YHAvatar(name: post.authorName, size: 28)
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text(post.authorName)
                                        .font(.yhCaptionMed).foregroundStyle(YH.ink)
                                    if let at = post.createdAt {
                                        Text(at.formatted(.relative(presentation: .named)))
                                            .font(.yhCaption).foregroundStyle(YH.muted)
                                    }
                                }
                                Text(post.body)
                                    .font(.yhSubheadline)
                                    .foregroundStyle(YH.ink)
                                    .lineLimit(2)
                            }
                            Spacer(minLength: 0)
                        }
                        if post.id != preview.last?.id {
                            Divider().overlay(YH.border)
                        }
                    }
                }
            }
        }
        .task(id: garden.id) {
            posts = (try? await APIClient.shared.listWallComments(gardenID: garden.id)) ?? []
            loaded = true
        }
    }
}
