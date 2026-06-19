import SwiftUI

struct NotificationsView: View {
    @Environment(BadgeStore.self) private var badges

    @State private var notifications: [YHNotification] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    var body: some View {
        Group {
            if notifications.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<4, id: \.self) { _ in YHSkeletonCard() }
                    }.padding()
                }
            } else if notifications.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if notifications.isEmpty {
                YHEmpty(systemImage: "bell.slash",
                        title: "You're all caught up",
                        message: "Notifications about your gardens show up here.")
            } else {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(notifications) { n in
                            Button {
                                Task { await markRead(n) }
                            } label: {
                                NotificationRow(notification: n)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(YH.Space.md)
                }
                .refreshable { await load(showSpinner: false) }
            }
        }
        .background(YH.canvas)
        .navigationTitle("Notifications")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if notifications.contains(where: { !$0.isRead }) {
                ToolbarItem(placement: .topBarTrailing) {
                    Button("Mark all read") { Task { await markAllRead() } }
                        .font(.system(size: 14, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
            }
        }
        .task { await load() }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do {
            let payload = try await APIClient.shared.listNotifications(perPage: 50)
            notifications = payload.notifications
        } catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func markRead(_ n: YHNotification) async {
        guard !n.isRead else { return }
        do {
            try await APIClient.shared.markNotificationRead(notificationID: n.id)
            if let i = notifications.firstIndex(where: { $0.id == n.id }) {
                notifications[i] = n.markingRead()
            }
            badges.notificationWasRead()
            Haptics.selection()
        } catch { /* silent */ }
    }

    private func markAllRead() async {
        do {
            try await APIClient.shared.markAllNotificationsRead()
            notifications = notifications.map { $0.markingRead() }
            badges.allNotificationsRead()
            Haptics.success()
        } catch { /* silent */ }
    }
}

private extension YHNotification {
    func markingRead() -> YHNotification {
        YHNotification(id: id, type: type, title: title, body: body,
                       link: link, gardenId: gardenId, isRead: true, createdAt: createdAt)
    }
}

private struct NotificationRow: View {
    let notification: YHNotification

    var body: some View {
        YHCard {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: iconName)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(YH.ink)
                    .frame(width: 32, height: 32)
                    .background(notification.isRead ? YH.surface : YH.lime)
                    .clipShape(RoundedRectangle(cornerRadius: 9))
                VStack(alignment: .leading, spacing: 4) {
                    Text(notification.title)
                        .font(notification.isRead ? .yhBody : .yhBodyMedium)
                        .foregroundStyle(YH.ink)
                    if let body = notification.body {
                        Text(body)
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.muted)
                            .lineLimit(2)
                    }
                    if let when = notification.createdAt {
                        Text(when.formatted(.relative(presentation: .named)))
                            .font(.yhCaption)
                            .foregroundStyle(.tertiary)
                    }
                }
                Spacer()
                if !notification.isRead {
                    Circle().fill(YH.ink).frame(width: 8, height: 8)
                }
            }
        }
    }

    private var iconName: String {
        switch notification.type {
        case "announcement": return "megaphone.fill"
        case "event": return "calendar"
        case "message": return "bubble.left.fill"
        case "harvest": return "basket.fill"
        case "waitlist": return "person.crop.circle.badge.clock"
        case "plot_assigned", "plot_confirmed": return "checkmark.seal.fill"
        case "shift_reminder", "shift_signup": return "person.2.fill"
        default: return "bell.fill"
        }
    }
}
