import SwiftUI

struct MoreTab: View {
    @Environment(AuthManager.self) private var auth
    @Environment(GardenStore.self) private var store
    @Environment(BadgeStore.self) private var badges

    @State private var showingPicker = false
    @State private var lock = AppLock.shared
    @State private var lockOn = AppLock.shared.isEnabled
    @State private var lockError: String?

    private var isAdmin: Bool { store.hasAdminAccess }

    private func canDo(_ capability: String, in garden: Garden) -> Bool {
        garden.userCapabilities.map { $0.contains(capability) } ?? isAdmin
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.md) {
                    profileCard
                    activitySection
                    if let garden = store.selectedGarden {
                        manageSection(garden: garden)
                    }
                    settingsSection
                    signOutButton
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("More")
            .navigationBarTitleDisplayMode(.inline)
            .sheet(isPresented: $showingPicker) { GardenPickerSheet().environment(store) }
        }
    }

    private var profileCard: some View {
        Group {
            if case .signedIn(let user) = auth.state {
                YHCard {
                    HStack(spacing: 14) {
                        YHAvatar(name: user.bestName, size: 52)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(user.bestName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                            Text(user.email).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                        Spacer()
                    }
                }
            }
        }
    }

    private var activitySection: some View {
        section(title: "Activity") {
            row("Messages", systemImage: "bubble.left.and.bubble.right.fill",
                badge: badges.unreadMessages) {
                InboxView()
            }
            row("Notifications", systemImage: "bell.fill", badge: badges.unreadNotifications) {
                NotificationsView()
            }
            row("Find a Garden", systemImage: "magnifyingglass") {
                BrowseGardensView()
            }
        }
    }

    @ViewBuilder
    private func manageSection(garden: Garden) -> some View {
        section(title: "Garden") {
            HStack {
                VStack(alignment: .leading) {
                    Text(garden.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text([garden.city, garden.state].compactMap { $0 }.joined(separator: ", "))
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                Spacer()
                Button("Switch") {
                    Haptics.tap()
                    showingPicker = true
                }
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(YH.ink)
                .padding(.horizontal, 12).padding(.vertical, 6)
                .background(YH.surface)
                .clipShape(Capsule())
                .buttonStyle(.plain)
            }
            .padding(YH.Space.md)
            .yhRowCard()

            row("My Dues", systemImage: "dollarsign.circle.fill") { MyDuesView(garden: garden) }
            // Admin rows gate on role capabilities, so a treasurer sees
            // Payments without the rest and a volunteer lead sees neither.
            // A payload without capabilities (older cache) falls back to the
            // blanket admin check. The backend enforces the map regardless.
            if canDo("money", in: garden) {
                row("Payments — Tap to Pay",
                    systemImage: "wave.3.right") {
                    PaymentHubView(garden: garden)
                }
            }
            if canDo("resources", in: garden) {
                row("Manage Tools", systemImage: "qrcode") {
                    AdminToolsView(garden: garden)
                }
            }
            if store.can("roles") {
                row("Roles", systemImage: "person.badge.key.fill") {
                    RolesView(garden: garden)
                }
            }
            row("Events", systemImage: "calendar") { EventsView(garden: garden) }
            row("Volunteer Shifts", systemImage: "person.2.fill") { ShiftsView(garden: garden) }
            row("Harvest Log", systemImage: "basket.fill") { HarvestLogView(garden: garden) }
            row("Announcements", systemImage: "megaphone.fill") { AnnouncementsView(garden: garden) }
        }
    }

    private var settingsSection: some View {
        section(title: "App") {
            biometricLockRow
            // Blocking is undone here and nowhere else, so the row shows
            // whether or not anyone is currently blocked.
            row("Blocked Members", systemImage: "hand.raised.fill") {
                BlockedMembersView()
            }
            // The website's Help Center (product how-tos, /help/:slug per
            // article) — distinct from /about/guide's gardening advice.
            // Opens in the browser; the content is the web app's to render.
            Link(destination: URL(string: "https://www.yardharvest.app/help")!) {
                HStack {
                    rowLabel("Help Center", systemImage: "questionmark.circle.fill")
                    Spacer()
                    // Points out of the app rather than deeper into it, so
                    // this is the one row that isn't a chevron.
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 12, weight: .semibold))
                        .foregroundStyle(YH.muted)
                        .padding(.trailing, YH.Space.md)
                }
                .padding(.vertical, 14)
                .padding(.leading, YH.Space.md)
                .yhRowCard()
            }
            .buttonStyle(.plain)
            HStack {
                rowLabel("Version", systemImage: "info.circle")
                Spacer()
                Text("\(AppEnvironment.appVersion) (\(AppEnvironment.buildNumber))")
                    .font(.yhCaption).foregroundStyle(YH.muted)
                    .padding(.trailing, YH.Space.md)
            }
            .padding(.vertical, 14)
            .padding(.leading, YH.Space.md)
            .yhRowCard()
        }
    }

    private var signOutButton: some View {
        Button {
            Haptics.warning()
            Task { await auth.signOut() }
        } label: {
            HStack {
                Image(systemName: "rectangle.portrait.and.arrow.right")
                Text("Sign Out")
            }
            .font(.yhBodyMedium)
            .foregroundStyle(YH.danger)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .yhRowCard()
        }
        .buttonStyle(.plain)
    }

    /// Opt-in biometric lock. Shown only where the device can actually do it,
    /// because a permanently-off toggle explains nothing; the reason is shown
    /// instead so the person knows what to fix.
    @ViewBuilder
    private var biometricLockRow: some View {
        let name = AppLock.biometryName
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                rowLabel("Require \(name ?? "Face ID")", systemImage: "faceid")
                Spacer()
                if name != nil {
                    Toggle("", isOn: $lockOn)
                        .labelsHidden()
                        .padding(.trailing, YH.Space.md)
                }
            }
            .padding(.vertical, 14)
            .padding(.leading, YH.Space.md)

            if let reason = AppLock.unavailableReason {
                Text(reason)
                    .font(.yhCaption).foregroundStyle(YH.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, YH.Space.md)
                    .padding(.bottom, 14)
            } else if let lockError {
                Text(lockError)
                    .font(.yhCaption).foregroundStyle(YH.danger)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, YH.Space.md)
                    .padding(.bottom, 14)
            } else {
                Text("Ask for \(name ?? "Face ID") when you come back to "
                     + "YardHarvest after a minute away.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.horizontal, YH.Space.md)
                    .padding(.bottom, 14)
            }
        }
        .yhRowCard()
        .onChange(of: lockOn) { was, now in
            guard now != lock.isEnabled else { return }   // not a user action
            Task {
                let ok = now ? await lock.enable() : await lock.disable()
                if !ok {
                    // Both directions require passing the check, so a cancel
                    // or a failure puts the switch back where it was.
                    lockError = lock.lastError
                    lockOn = lock.isEnabled
                } else {
                    lockError = nil
                    Haptics.success()
                }
            }
        }
    }

    @ViewBuilder
    private func section<Content: View>(title: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title.uppercased())
                .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                .padding(.horizontal, 4)
            content()
        }
    }

    @ViewBuilder
    private func row<Destination: View>(_ title: String, systemImage: String,
                                         badge: Int = 0,
                                         @ViewBuilder destination: @escaping () -> Destination)
                                         -> some View {
        NavigationLink {
            destination()
        } label: {
            HStack {
                rowLabel(title, systemImage: systemImage)
                Spacer()
                if badge > 0 {
                    Text("\(badge)")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(YH.ink)
                        .padding(.horizontal, 8).padding(.vertical, 2)
                        .background(YH.lime)
                        .clipShape(Capsule())
                }
                Image(systemName: "chevron.right")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(YH.muted)
                    .padding(.trailing, YH.Space.md)
            }
            .padding(.vertical, 14)
            .padding(.leading, YH.Space.md)
            .yhRowCard()
        }
        .buttonStyle(.plain)
    }

    private func rowLabel(_ title: String, systemImage: String) -> some View {
        HStack(spacing: 10) {
            YHIconTile(systemImage: systemImage)
            Text(title).font(.yhBodyMedium).foregroundStyle(YH.ink)
        }
    }

}

/// The card chrome every row on this screen wears: canvas fill, hairline
/// border, matching corner radius. Factored out because the same three
/// lines were repeated at every call site, and one of them — Help Center —
/// had quietly missed it, leaving it borderless among bordered neighbors.
private extension View {
    func yhRowCard() -> some View {
        background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                .strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
    }
}
