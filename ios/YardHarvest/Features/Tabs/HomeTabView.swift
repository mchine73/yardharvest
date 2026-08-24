import SwiftUI

/// Top-level tab shell shown after sign-in. Garden / Tools / Announcements /
/// More — same four-tab IA as the web's primary nav.
///
/// Owns the `BadgeStore` poll and the `AppAlertCenter` toast bus. New
/// messages and announcement-style notifications surface as a top-of-screen
/// `YHToast` that floats above the active tab.
struct HomeTabView: View {
    let user: AuthUser
    @State private var gardenStore = GardenStore()
    @State private var badges = BadgeStore()
    @State private var alerts = AppAlertCenter()
    @Environment(\.scenePhase) private var scenePhase
    @State private var push = PushManager.shared

    /// Selected tab — driven by both user taps and toast deep-links.
    @State private var selection: Tab = .garden

    enum Tab: Int, Hashable {
        case garden, tools, announcements, more
    }

    var body: some View {
        TabView(selection: $selection) {
            DashboardTab()
                .tabItem { Label("Garden", systemImage: "house.fill") }
                .tag(Tab.garden)

            ToolsTab()
                .tabItem { Label("Tools", systemImage: "wrench.and.screwdriver.fill") }
                .tag(Tab.tools)

            AnnouncementsTab()
                .tabItem { Label("Announcements", systemImage: "megaphone.fill") }
                .tag(Tab.announcements)

            MoreTab()
                .tabItem { Label("More", systemImage: "ellipsis.circle.fill") }
                .badge(badges.totalUnread)
                .tag(Tab.more)
        }
        .environment(gardenStore)
        .environment(badges)
        .environment(alerts)
        .yhToastBanner(alerts) { alert in
            // Tapping a toast jumps to the most relevant tab. (The More
            // tab houses Messages, Notifications, and a per-garden
            // announcements view, so it's a sensible landing pad for all
            // three flavors of toast.)
            switch alert.kind {
            case .message, .generic, .alert: selection = .more
            case .announcement:              selection = .announcements
            }
        }
        .task {
            // Wire the badge poll → toast bus before kicking off polling
            // so the very first delta has somewhere to land.
            badges.alertCenter = alerts
            await gardenStore.bootstrapIfNeeded()
            badges.startPolling()
            // Signed in and home — the moment to ask about notifications.
            await push.requestAuthorizationAndRegister()
        }
        .onChange(of: push.pendingRoute) { _, route in
            guard let route else { return }
            push.pendingRoute = nil
            // Same coarse routing as the toast bus: land the user on the tab
            // that owns the content; the tab's own badge/list finishes the job.
            switch route.type {
            case "announcement":      selection = .announcements
            case "comment_flagged":   selection = .garden   // moderation lives off the wall
            default:                  selection = .more
            }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task { await badges.refresh() }
                push.clearBadge()
            }
        }
        .tint(YH.ink)
    }
}
