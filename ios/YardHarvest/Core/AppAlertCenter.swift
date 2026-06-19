import Foundation
import Observation

/// In-app alert payload — surfaces a fresh message, announcement, or other
/// notification as a top-of-screen toast. Carries everything the toast needs
/// to render and (optionally) deep-link.
struct AppAlert: Identifiable, Equatable {
    let id = UUID()
    let kind: Kind
    let title: String
    let body: String?

    enum Kind: String, Equatable {
        case message, announcement, alert, generic

        var systemImage: String {
            switch self {
            case .message:      return "bubble.left.fill"
            case .announcement: return "megaphone.fill"
            case .alert:        return "exclamationmark.triangle.fill"
            case .generic:      return "bell.fill"
            }
        }
    }
}

/// Lightweight pub-sub for in-app toast notifications. Owners (e.g. the
/// `BadgeStore` poll) call `enqueue` when a new item arrives; the
/// `HomeTabView` observes `current` to drive a top banner. Auto-dismisses
/// after a few seconds so it never blocks the UI.
@MainActor
@Observable
final class AppAlertCenter {
    private(set) var current: AppAlert?
    private var dismissTask: Task<Void, Never>?

    /// How long an alert stays on screen before fading.
    private let lifetime: UInt64 = 4_000_000_000 // 4.0s

    func enqueue(_ alert: AppAlert) {
        dismissTask?.cancel()
        current = alert
        Haptics.confirm()
        dismissTask = Task { [weak self] in
            try? await Task.sleep(nanoseconds: self?.lifetime ?? 4_000_000_000)
            guard !Task.isCancelled else { return }
            self?.current = nil
        }
    }

    func dismiss() {
        dismissTask?.cancel()
        current = nil
    }
}
