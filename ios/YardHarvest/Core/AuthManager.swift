import Foundation
import Observation

/// Owns sign-in state. ContentView observes `state` and switches between
/// the login screen and the authenticated stack.
@MainActor
@Observable
final class AuthManager {
    enum State: Equatable {
        case unknown
        case signedOut
        case signedIn(AuthUser)
    }

    private(set) var state: State = .unknown
    private(set) var lastError: String?

    /// Inspect Keychain on launch. If tokens exist, try /me; on failure,
    /// fall back to signed-out so the user sees the login screen cleanly.
    func bootstrap() async {
        guard KeychainStore.get(.accessToken) != nil else {
            state = .signedOut
            return
        }
        do {
            // Hard deadline: `state` stays `.unknown` until this resolves, and
            // `.unknown` renders the splash. Without a bound, one stalled
            // request means the app never launches. Falling through to the
            // login screen is always better than an infinite splash.
            let user = try await withTimeout(seconds: 15) {
                try await APIClient.shared.me()
            }
            state = .signedIn(user)
        } catch APIError.unauthorized {
            KeychainStore.clear()
            state = .signedOut
        } catch is TimeoutError {
            // Keep the tokens — this is a network problem, not a bad session.
            state = .signedOut
            lastError = "Couldn't reach YardHarvest. Check your connection and sign in again."
        } catch {
            state = .signedOut
            lastError = error.localizedDescription
        }
    }

    func signIn(email: String, password: String) async throws {
        let response = try await APIClient.shared.login(email: email, password: password)
        state = .signedIn(response.user)
        lastError = nil
        Haptics.success()
    }

    /// Mobile registration — gardener-only from iOS. Garden managers register
    /// their garden at yardharvest.app.
    func signUp(email: String, password: String, displayName: String,
                username: String, address: String, city: String,
                state: String, zipCode: String) async throws {
        let response = try await APIClient.shared.register(
            email: email, password: password, displayName: displayName,
            username: username, address: address, city: city,
            state: state, zipCode: zipCode)
        self.state = .signedIn(response.user)
        lastError = nil
        Haptics.success()
    }

    func signOut() async {
        // Before credentials go: a still-connected Tap-to-Pay reader belongs
        // to this manager's Stripe account, and the next person to sign in on
        // this phone must not inherit it.
        await TerminalManager.teardownForSignOut()
        do { try await APIClient.shared.logout() } catch { /* ignore */ }
        KeychainStore.clear()
        state = .signedOut
    }

    func refreshMe() async {
        guard case .signedIn = state else { return }
        do {
            let user = try await APIClient.shared.me()
            state = .signedIn(user)
        } catch { /* non-fatal */ }
    }
}
