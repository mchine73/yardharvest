import UIKit

/// Centralized haptic feedback. Wraps UIFeedbackGenerator so callers don't
/// have to manage generator lifecycles. Pair with `.sensoryFeedback` on
/// iOS 17+ for the views that already model state changes.
enum Haptics {
    /// Light tap for taps + selections.
    static func tap() {
        let generator = UIImpactFeedbackGenerator(style: .light)
        generator.impactOccurred()
    }

    /// Medium tap for confirmation actions.
    static func confirm() {
        let generator = UIImpactFeedbackGenerator(style: .medium)
        generator.impactOccurred()
    }

    /// Soft success notification (e.g. checkout succeeded, harvest logged).
    static func success() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.success)
    }

    /// Warning notification (e.g. overdue confirmation).
    static func warning() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.warning)
    }

    /// Error notification (e.g. wrong password, server error).
    static func error() {
        let generator = UINotificationFeedbackGenerator()
        generator.notificationOccurred(.error)
    }

    /// Light selection click (segmented picker, swipe).
    static func selection() {
        let generator = UISelectionFeedbackGenerator()
        generator.selectionChanged()
    }
}
