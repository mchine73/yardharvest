package app.yardharvest.manager.core

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import app.yardharvest.manager.api.login
import app.yardharvest.manager.api.logout
import app.yardharvest.manager.api.me
import app.yardharvest.manager.api.register
import app.yardharvest.manager.model.AuthUser
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.withTimeout

sealed interface AuthState {
    data object Unknown : AuthState
    data object SignedOut : AuthState
    data class SignedIn(val user: AuthUser) : AuthState
}

/**
 * Owns sign-in state. The root composable observes [state] and switches
 * between the splash, the login screen and the signed-in shell.
 */
object AuthManager {
    var state: AuthState by mutableStateOf(AuthState.Unknown)
        private set
    var lastError: String? by mutableStateOf(null)
        private set

    val currentUser: AuthUser? get() = (state as? AuthState.SignedIn)?.user

    /**
     * Check stored tokens on launch. If they exist, try /me; on failure fall
     * back to signed-out so the login screen shows cleanly.
     */
    suspend fun bootstrap() {
        if (TokenStore.get(TokenStore.Key.AccessToken) == null) {
            state = AuthState.SignedOut
            return
        }
        try {
            // Hard deadline: Unknown renders the splash, and one stalled
            // request must not mean the app never launches.
            val user = withTimeout(15_000) { ApiClient.me() }
            state = AuthState.SignedIn(user)
        } catch (e: ApiError.Unauthorized) {
            TokenStore.clear()
            state = AuthState.SignedOut
        } catch (e: TimeoutCancellationException) {
            // Keep the tokens — this is a network problem, not a bad session.
            state = AuthState.SignedOut
            lastError = "Couldn't reach YardHarvest. Check your connection and sign in again."
        } catch (e: Exception) {
            state = AuthState.SignedOut
            lastError = e.userMessage
        }
    }

    suspend fun signIn(email: String, password: String) {
        val response = ApiClient.login(email, password)
        state = AuthState.SignedIn(response.user)
        lastError = null
        Haptics.success()
    }

    /** Mobile registration is gardener-only; managers register on the website. */
    suspend fun signUp(
        email: String, password: String, displayName: String, username: String,
        address: String, city: String, state: String, zipCode: String,
    ) {
        val response = ApiClient.register(email, password, displayName, username, address, city, state, zipCode)
        this.state = AuthState.SignedIn(response.user)
        lastError = null
        Haptics.success()
    }

    suspend fun signOut() {
        // Before credentials go: a connected Tap to Pay reader belongs to this
        // manager's Stripe account, and the next person to sign in on this
        // phone must not inherit it.
        TerminalManager.teardownForSignOut()
        try { ApiClient.logout() } catch (_: Exception) {}
        TokenStore.clear()
        // The lock guards this session, not the phone.
        AppLock.resetOnSignOut()
        state = AuthState.SignedOut
    }

    suspend fun refreshMe() {
        if (state !is AuthState.SignedIn) return
        try { state = AuthState.SignedIn(ApiClient.me()) } catch (_: Exception) {}
    }
}
