import Foundation
import LocalAuthentication
import Observation

/// Opt-in biometric lock over an already-signed-in session.
///
/// This protects a session that is already on the device; it is not a second
/// factor for signing in. The refresh token sits in the keychain either way —
/// what the lock adds is that someone holding an unlocked phone still cannot
/// read the garden's member list or take a payment.
///
/// Two deliberate choices:
///
/// * The policy is `.deviceOwnerAuthentication`, not the biometrics-only
///   variant, so a failed or unavailable Face ID falls through to the device
///   passcode. An app lock that can strand its owner is worse than none.
/// * Locking is armed only by a real `.background` transition, and only after
///   `graceSeconds`. `.inactive` fires for Control Center, the notification
///   shade and system sheets — including Apple's Tap to Pay sheet, which
///   would otherwise throw a Face ID prompt into the middle of taking money.
@MainActor
@Observable
final class AppLock {
    static let shared = AppLock()

    private static let enabledKey = "yh.applock.enabled"

    /// Where the preference lives. Overridable so tests get a clean store
    /// instead of scribbling on the real one.
    var defaults: UserDefaults = .standard

    /// The biometric check itself. Injectable because `LAContext` cannot be
    /// driven from a unit test — the real implementation is `realAuthenticate`
    /// and nothing but tests should replace it.
    var authenticator: (String) async -> Result<Bool, Error> = { _ in .success(true) }
    /// Brief excursions shouldn't cost a Face ID prompt — answering a text
    /// and coming straight back is not a threat model.
    private static let graceSeconds: TimeInterval = 60

    /// True when the lock screen should be covering the app.
    private(set) var isLocked = false
    /// Set when an unlock attempt fails for a reason worth showing.
    private(set) var lastError: String?

    private var backgroundedAt: Date?
    /// Held for the lifetime of a prompt. `LAContext` dismisses its own sheet
    /// when it deallocates, and a context that only exists as a local inside
    /// an `async` function can be released the moment the continuation
    /// suspends — the prompt flashes up and cancels itself. Keeping the
    /// reference here is what makes the prompt stay on screen.
    private var activeContext: LAContext?

    private init() {
        authenticator = { [weak self] reason in
            await self?.realAuthenticate(reason: reason) ?? .success(false)
        }
        // A cold launch with the lock on starts locked; there is no grace
        // period to apply because there was no prior foreground session.
        isLocked = isEnabled
    }

    /// Test seam: a lock with its own store and a stubbed biometric result.
    init(defaults: UserDefaults,
         authenticator: @escaping (String) async -> Result<Bool, Error>) {
        self.defaults = defaults
        self.authenticator = authenticator
        self.isLocked = defaults.bool(forKey: Self.enabledKey)
    }

    // MARK: - Preference

    var isEnabled: Bool {
        defaults.bool(forKey: Self.enabledKey)
    }

    /// What this device actually offers, for labelling the setting. Returns
    /// nil when there is no enrolled biometry to offer.
    static var biometryName: String? {
        let ctx = LAContext()
        var error: NSError?
        guard ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                                    error: &error) else { return nil }
        switch ctx.biometryType {
        case .faceID: return "Face ID"
        case .touchID: return "Touch ID"
        case .opticID: return "Optic ID"
        default: return nil
        }
    }

    /// Why the setting can't be switched on, phrased for the person reading
    /// it rather than for a developer. Nil when it can.
    static var unavailableReason: String? {
        let ctx = LAContext()
        var error: NSError?
        if ctx.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics,
                                 error: &error) { return nil }
        switch LAError.Code(rawValue: (error as NSError?)?.code ?? -1) {
        case .biometryNotEnrolled:
            return "No face or fingerprint is set up on this iPhone yet. "
                 + "Add one in Settings to use this."
        case .biometryNotAvailable:
            return "This iPhone doesn't support Face ID or Touch ID."
        case .biometryLockout:
            return "Face ID is locked. Unlock your iPhone with its passcode "
                 + "once, then try again."
        default:
            return "Face ID isn't available on this iPhone right now."
        }
    }

    /// Turn the lock on, but only after proving it works — enabling a lock
    /// you cannot pass is a trap, so the prompt comes first.
    /// Returns whether it ended up on.
    @discardableResult
    func enable() async -> Bool {
        let ok = await authenticate(reason: "Confirm it's you before turning on "
                                          + "\(Self.biometryName ?? "biometric") unlock.")
        if ok {
            defaults.set(true, forKey: Self.enabledKey)
            isLocked = false
        }
        return ok
    }

    /// Turn the lock off. Also requires passing it, so someone who picks up an
    /// unlocked phone can't simply switch the protection off.
    @discardableResult
    func disable() async -> Bool {
        let ok = await authenticate(reason: "Confirm it's you before turning off "
                                          + "\(Self.biometryName ?? "biometric") unlock.")
        if ok {
            defaults.set(false, forKey: Self.enabledKey)
            isLocked = false
        }
        return ok
    }

    /// Signing out drops the preference with the session — the next person to
    /// sign in on this phone is a different account and should make their own
    /// choice rather than inherit a lock they can't pass.
    func resetOnSignOut() {
        defaults.set(false, forKey: Self.enabledKey)
        isLocked = false
        backgroundedAt = nil
    }

    // MARK: - Lifecycle

    /// Call on a real `.background` transition only.
    func didEnterBackground() {
        guard isEnabled else { return }
        backgroundedAt = Date()
    }

    /// Call on return to `.active`. Locks only if the app was genuinely
    /// backgrounded for longer than the grace period.
    func didBecomeActive() {
        guard isEnabled, let since = backgroundedAt else { return }
        backgroundedAt = nil
        if Date().timeIntervalSince(since) >= Self.graceSeconds {
            isLocked = true
        }
    }

    // MARK: - Unlocking

    /// Prompt to unlock. Safe to call repeatedly; the lock screen's button
    /// calls it again after a cancel.
    func unlock() async {
        let name = Self.biometryName ?? "biometrics"
        let ok = await authenticate(reason: "Unlock YardHarvest with \(name).")
        if ok {
            lastError = nil
            isLocked = false
        }
    }

    private func authenticate(reason: String) async -> Bool {
        switch await authenticator(reason) {
        case .success(let ok):
            if ok { lastError = nil }
            return ok
        case .failure(let error):
            lastError = Self.message(for: error)
            return false
        }
    }

    private func realAuthenticate(reason: String) async -> Result<Bool, Error> {
        // Retire any context still standing from a previous attempt. The lock
        // screen's unlock runs in a SwiftUI `.task`, which is cancelled the
        // moment the screen dismisses — the continuation may never resume, so
        // its `defer` never runs. Refusing while one lingered would have made
        // every later prompt fail silently; invalidating is the safe order.
        activeContext?.invalidate()
        activeContext = nil

        let ctx = LAContext()
        // The passcode fallback is the point of .deviceOwnerAuthentication,
        // so don't relabel or suppress it.
        ctx.localizedCancelTitle = "Cancel"
        activeContext = ctx
        defer { activeContext = nil }
        do {
            let ok = try await ctx.evaluatePolicy(.deviceOwnerAuthentication,
                                                  localizedReason: reason)
            return .success(ok)
        } catch {
            return .failure(error)
        }
    }

    private static func message(for error: Error) -> String? {
        switch LAError.Code(rawValue: (error as NSError).code) {
        case .userCancel, .appCancel, .systemCancel:
            return nil                      // the person meant to; say nothing
        case .userFallback:
            return nil                      // iOS is showing the passcode sheet
        case .biometryLockout:
            return "Too many attempts. Unlock your iPhone with its passcode, "
                 + "then try again."
        case .passcodeNotSet:
            return "Set a passcode on this iPhone to use the lock."
        default:
            return "Couldn't verify it's you. Try again."
        }
    }
}
