import SwiftUI

struct MoreTab: View {
    @Environment(AuthManager.self) private var auth
    @Environment(GardenStore.self) private var store
    @Environment(BadgeStore.self) private var badges

    @State private var showingPicker = false
    @State private var showingConnection = false

    private var isAdmin: Bool { store.hasAdminAccess }

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
            .sheet(isPresented: $showingConnection) { APIBaseURLEditorView() }
        }
    }

    private var profileCard: some View {
        Group {
            if case .signedIn(let user) = auth.state {
                YHCard {
                    HStack(spacing: 14) {
                        ZStack {
                            Circle().fill(YH.lime)
                            Text(initials(user.bestName))
                                .font(.system(size: 18, weight: .bold))
                                .foregroundStyle(YH.ink)
                        }
                        .frame(width: 52, height: 52)
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
                AnyView(InboxView())
            }
            row("Notifications", systemImage: "bell.fill", badge: badges.unreadNotifications) {
                AnyView(NotificationsView())
            }
            row("Find a Garden", systemImage: "magnifyingglass") {
                AnyView(BrowseGardensView())
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
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))

            row("My Dues", systemImage: "dollarsign.circle.fill") { AnyView(MyDuesView(garden: garden)) }
            if isAdmin {
                row("Collect Dues — Tap to Pay",
                    systemImage: "wave.3.right") {
                    AnyView(AdminDuesListView(garden: garden))
                }
            }
            row("Events", systemImage: "calendar") { AnyView(EventsView(garden: garden)) }
            row("Volunteer Shifts", systemImage: "person.2.fill") { AnyView(ShiftsView(garden: garden)) }
            row("Harvest Log", systemImage: "basket.fill") { AnyView(HarvestLogView(garden: garden)) }
            row("Announcements", systemImage: "megaphone.fill") { AnyView(AnnouncementsView(garden: garden)) }
        }
    }

    private var settingsSection: some View {
        section(title: "App") {
            Button {
                Haptics.tap()
                showingConnection = true
            } label: {
                rowLabel("Connection Settings", systemImage: "antenna.radiowaves.left.and.right")
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
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
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
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
        .buttonStyle(.plain)
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
    private func row(_ title: String, systemImage: String, badge: Int = 0,
                     @ViewBuilder destination: @escaping () -> AnyView) -> some View {
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
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
        .buttonStyle(.plain)
    }

    private func rowLabel(_ title: String, systemImage: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: systemImage)
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(YH.ink)
                .frame(width: 28, height: 28)
                .background(YH.surface)
                .clipShape(RoundedRectangle(cornerRadius: 8))
            Text(title).font(.yhBodyMedium).foregroundStyle(YH.ink)
        }
    }

    private func initials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.map { String($0.first ?? " ") }.joined().uppercased()
    }
}
