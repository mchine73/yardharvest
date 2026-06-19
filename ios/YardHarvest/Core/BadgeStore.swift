import Foundation
import Observation

/// Polls the backend for unread message + notification counts so the More
/// tab can show badges, and emits in-app toast alerts when those counts
/// increase. Cheap calls (single-int payloads), polled every 60s.
@MainActor
@Observable
final class BadgeStore {
    private(set) var unreadMessages: Int = 0
    private(set) var unreadNotifications: Int = 0
    private var pollTask: Task<Void, Never>?
    private var hasLoadedOnce = false

    /// Optional sink for in-app alerts. Injected by `HomeTabView`.
    var alertCenter: AppAlertCenter?

    var totalUnread: Int { unreadMessages + unreadNotifications }

    func startPolling() {
        guard pollTask == nil else { return }
        pollTask = Task { [weak self] in
            while !Task.isCancelled {
                await self?.refresh()
                try? await Task.sleep(nanoseconds: 60 * 1_000_000_000)
            }
        }
    }

    func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    func refresh() async {
        async let msgs = (try? APIClient.shared.messagesUnreadCount()) ?? 0
        async let notifs = (try? APIClient.shared.notificationsUnreadCount()) ?? 0
        let (m, n) = await (msgs, notifs)

        let prevMessages = unreadMessages
        let prevNotifications = unreadNotifications

        unreadMessages = m
        unreadNotifications = n

        // First refresh just establishes a baseline; don't pop a toast for
        // the items the user already had unread before the app opened.
        guard hasLoadedOnce else {
            hasLoadedOnce = true
            return
        }

        // New messages → "New message" / "N new messages" toast.
        if m > prevMessages, let center = alertCenter {
            let delta = m - prevMessages
            center.enqueue(AppAlert(
                kind: .message,
                title: delta == 1 ? "New message" : "\(delta) new messages",
                body: nil
            ))
        }

        // New notifications → fetch the latest unread item so the toast can
        // surface a real title + body, not just a count. If the fetch fails
        // (network, etc.) we fall back to a generic toast so the user still
        // gets the heads-up.
        if n > prevNotifications, let center = alertCenter {
            let delta = n - prevNotifications
            if let latest = await fetchLatestNotification() {
                center.enqueue(AppAlert(
                    kind: kind(for: latest.type),
                    title: latest.title,
                    body: latest.body
                ))
            } else {
                center.enqueue(AppAlert(
                    kind: .generic,
                    title: delta == 1 ? "New notification"
                                      : "\(delta) new notifications",
                    body: nil
                ))
            }
        }
    }

    private func fetchLatestNotification() async -> YHNotification? {
        do {
            let payload = try await APIClient.shared.listNotifications(
                page: 1, perPage: 1, unreadOnly: true)
            return payload.notifications.first
        } catch {
            return nil
        }
    }

    /// Map the backend's notification `type` string to the right toast kind.
    private func kind(for type: String?) -> AppAlert.Kind {
        switch type {
        case "announcement":           return .announcement
        case "weather_alert", "alert": return .alert
        case "message":                return .message
        default:                       return .generic
        }
    }

    func notificationWasRead() { unreadNotifications = max(0, unreadNotifications - 1) }
    func allNotificationsRead() { unreadNotifications = 0 }
    func threadWasRead(unread: Int) { unreadMessages = max(0, unreadMessages - unread) }
}
