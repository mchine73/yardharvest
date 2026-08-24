import Foundation
import Observation
import UIKit
import UserNotifications

/// APNs on the client side: permission, registration, foreground
/// presentation, and tap routing.
///
/// The server half (`app/push_service.py`) fans out of `notify()`, so any
/// in-app notification the backend creates also lands on the lock screen.
/// Payloads carry `type`, `link`, and `garden_id`; a tap parks them in
/// `pendingRoute`, which `HomeTabView` consumes to switch tabs — the same
/// routing the in-app toast bus uses, deliberately no finer-grained than
/// that.
@MainActor
@Observable
final class PushManager: NSObject {
    static let shared = PushManager()

    struct PushRoute: Equatable {
        let type: String
        let link: String
        let gardenId: Int?
    }

    /// The tapped notification waiting to be routed. HomeTabView observes
    /// this, navigates, and clears it.
    var pendingRoute: PushRoute?

    /// Call once at launch, before anything can be tapped — a cold-start
    /// notification tap delivers to the delegate during app launch.
    func install() {
        UNUserNotificationCenter.current().delegate = self
    }

    /// Ask for permission and register with APNs. Safe to call every
    /// sign-in: the system prompt shows once; afterwards this is a no-op
    /// re-registration that keeps the token fresh.
    func requestAuthorizationAndRegister() async {
        let center = UNUserNotificationCenter.current()
        let settings = await center.notificationSettings()
        switch settings.authorizationStatus {
        case .notDetermined:
            let granted = (try? await center.requestAuthorization(
                options: [.alert, .badge, .sound])) ?? false
            guard granted else { return }
        case .denied:
            return
        default:
            break
        }
        UIApplication.shared.registerForRemoteNotifications()
    }

    /// The app is front and center — the number on the icon has been seen.
    func clearBadge() {
        UNUserNotificationCenter.current().setBadgeCount(0)
    }
}

extension PushManager: UNUserNotificationCenterDelegate {
    /// Foreground pushes still show as banners — the in-app toast bus covers
    /// polled updates, but a push can beat the poll and shouldn't vanish.
    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .badge, .sound]
    }

    nonisolated func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        let info = response.notification.request.content.userInfo
        let route = PushRoute(
            type: info["type"] as? String ?? "",
            link: info["link"] as? String ?? "",
            gardenId: info["garden_id"] as? Int
        )
        await MainActor.run {
            PushManager.shared.pendingRoute = route
        }
    }
}
