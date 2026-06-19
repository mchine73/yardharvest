import SwiftUI

struct DashboardTab: View {
    @Environment(GardenStore.self) private var store
    @Environment(BadgeStore.self) private var badges
    @State private var showingPicker = false
    @State private var showingNotifications = false

    var body: some View {
        NavigationStack {
            Group {
                if let garden = store.selectedGarden {
                    if store.hasAdminAccess {
                        ManagerDashboardView(garden: garden)
                    } else {
                        MemberDashboardView(garden: garden)
                    }
                } else if store.isLoading {
                    YHSkeletonBento().padding()
                } else {
                    NoGardenWelcome()
                }
            }
            .background(YH.canvas)
            .navigationTitle(store.selectedGarden == nil ? "Garden" : "")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        Haptics.tap()
                        showingNotifications = true
                    } label: {
                        Image(systemName: badges.unreadNotifications > 0 ? "bell.badge.fill" : "bell")
                            .font(.system(size: 17, weight: .medium))
                            .symbolEffect(.bounce, value: badges.unreadNotifications)
                            .foregroundStyle(badges.unreadNotifications > 0 ? YH.ink : YH.muted)
                    }
                    .accessibilityLabel("Notifications")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Haptics.tap()
                        showingPicker = true
                    } label: {
                        Image(systemName: "arrow.up.arrow.down")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(YH.muted)
                    }
                    .accessibilityLabel("Switch garden")
                }
            }
            .sheet(isPresented: $showingPicker) { GardenPickerSheet().environment(store) }
            .sheet(isPresented: $showingNotifications) {
                NavigationStack {
                    NotificationsView()
                        .toolbar { ToolbarItem(placement: .topBarTrailing) { Button("Done") { showingNotifications = false } } }
                }
                .environment(badges)
            }
        }
    }
}
