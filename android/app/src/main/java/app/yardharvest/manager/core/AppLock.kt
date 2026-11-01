package app.yardharvest.manager.core

import android.content.Context
import android.content.SharedPreferences
import android.os.Build
import androidx.biometric.BiometricManager
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_STRONG
import androidx.biometric.BiometricManager.Authenticators.BIOMETRIC_WEAK
import androidx.biometric.BiometricManager.Authenticators.DEVICE_CREDENTIAL
import androidx.biometric.BiometricPrompt
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import androidx.fragment.app.FragmentActivity
import java.lang.ref.WeakReference
import kotlin.coroutines.resume
import kotlinx.coroutines.suspendCancellableCoroutine

/**
 * Opt-in biometric lock over an already-signed-in session.
 *
 * This protects a session already on the device; it is not a second factor
 * for signing in. Two deliberate choices, as on iOS:
 *
 * * The device PIN/pattern/password is accepted as a fallback, so a failed
 *   or unavailable fingerprint never strands the owner.
 * * Locking is armed only when the whole app goes to the background, and
 *   only after [GRACE_MS]. Stripe's Tap to Pay screen runs in its own process,
 *   and a brief trip to it must not throw a prompt into the middle of taking money.
 */
class AppLock(
    private val prefs: SharedPreferences,
    /** The check itself; injectable because BiometricPrompt can't run in a unit test. */
    var authenticator: suspend (String) -> Result<Boolean>,
    private val clock: () -> Long = System::currentTimeMillis,
) {
    var isLocked by mutableStateOf(prefs.getBoolean(ENABLED_KEY, false))
        private set
    var lastError: String? by mutableStateOf(null)
        private set

    private var backgroundedAt: Long? = null

    val isEnabled: Boolean get() = prefs.getBoolean(ENABLED_KEY, false)

    /** Turn the lock on, but only after proving it works. */
    suspend fun enable(): Boolean {
        val ok = authenticate("Confirm it's you before turning on the app lock.")
        if (ok) {
            prefs.edit { putBoolean(ENABLED_KEY, true) }
            isLocked = false
        }
        return ok
    }

    /** Turn the lock off — also requires passing it. */
    suspend fun disable(): Boolean {
        val ok = authenticate("Confirm it's you before turning off the app lock.")
        if (ok) {
            prefs.edit { putBoolean(ENABLED_KEY, false) }
            isLocked = false
        }
        return ok
    }

    /** The lock guards this session, not the phone; the next account chooses its own. */
    fun resetOnSignOut() {
        prefs.edit { putBoolean(ENABLED_KEY, false) }
        isLocked = false
        backgroundedAt = null
    }

    fun didEnterBackground() {
        if (!isEnabled) return
        backgroundedAt = clock()
    }

    fun didBecomeActive() {
        val since = backgroundedAt ?: return
        if (!isEnabled) return
        backgroundedAt = null
        if (clock() - since >= GRACE_MS) isLocked = true
    }

    suspend fun unlock() {
        if (authenticate("Unlock YardHarvest.")) {
            lastError = null
            isLocked = false
        }
    }

    private suspend fun authenticate(reason: String): Boolean =
        authenticator(reason).fold(
            onSuccess = { ok -> if (ok) lastError = null; ok },
            onFailure = { e -> lastError = (e as? LockError)?.message; false },
        )

    /** A failure worth showing; a plain cancel carries a null message. */
    class LockError(message: String?) : Exception(message)

    companion object {
        const val ENABLED_KEY = "yh.applock.enabled"
        /** Answering a text and coming straight back is not a threat model. */
        const val GRACE_MS = 60_000L

        lateinit var shared: AppLock
            private set

        private var activityRef = WeakReference<FragmentActivity>(null)

        fun init(context: Context) {
            shared = AppLock(AppEnvironment.prefs, authenticator = { reason -> realAuthenticate(reason) })
        }

        fun attach(activity: FragmentActivity) { activityRef = WeakReference(activity) }

        fun resetOnSignOut() = shared.resetOnSignOut()

        private val allowed: Int
            get() = if (Build.VERSION.SDK_INT >= 30) BIOMETRIC_STRONG or DEVICE_CREDENTIAL
            else BIOMETRIC_WEAK or DEVICE_CREDENTIAL

        /** "Fingerprint or face unlock" when enrolled, else null. Mirrors iOS biometryName. */
        fun biometryName(context: Context): String? =
            if (BiometricManager.from(context).canAuthenticate(BIOMETRIC_WEAK) == BiometricManager.BIOMETRIC_SUCCESS)
                "fingerprint or face unlock" else null

        /** Why the setting can't be switched on, phrased for the person. Null when it can. */
        fun unavailableReason(context: Context): String? =
            when (BiometricManager.from(context).canAuthenticate(BIOMETRIC_WEAK)) {
                BiometricManager.BIOMETRIC_SUCCESS -> null
                BiometricManager.BIOMETRIC_ERROR_NONE_ENROLLED ->
                    "No fingerprint or face is set up on this phone yet. Add one in Settings to use this."
                BiometricManager.BIOMETRIC_ERROR_NO_HARDWARE ->
                    "This phone doesn't have a fingerprint sensor or face unlock."
                else -> "Biometric unlock isn't available on this phone right now."
            }

        private suspend fun realAuthenticate(reason: String): Result<Boolean> {
            val activity = activityRef.get() ?: return Result.success(false)
            return suspendCancellableCoroutine { cont ->
                val prompt = BiometricPrompt(
                    activity,
                    ContextCompat.getMainExecutor(activity),
                    object : BiometricPrompt.AuthenticationCallback() {
                        override fun onAuthenticationSucceeded(result: BiometricPrompt.AuthenticationResult) {
                            if (cont.isActive) cont.resume(Result.success(true))
                        }

                        override fun onAuthenticationError(code: Int, msg: CharSequence) {
                            if (!cont.isActive) return
                            val text = when (code) {
                                // The person meant to; say nothing.
                                BiometricPrompt.ERROR_USER_CANCELED, BiometricPrompt.ERROR_CANCELED,
                                BiometricPrompt.ERROR_NEGATIVE_BUTTON -> null
                                BiometricPrompt.ERROR_LOCKOUT, BiometricPrompt.ERROR_LOCKOUT_PERMANENT ->
                                    "Too many attempts. Unlock your phone with its PIN, then try again."
                                BiometricPrompt.ERROR_NO_DEVICE_CREDENTIAL ->
                                    "Set a screen lock on this phone to use the app lock."
                                else -> "Couldn't verify it's you. Try again."
                            }
                            cont.resume(Result.failure(LockError(text)))
                        }
                        // onAuthenticationFailed = one bad read; the prompt stays up.
                    },
                )
                val info = BiometricPrompt.PromptInfo.Builder()
                    .setTitle("YardHarvest")
                    .setSubtitle(reason)
                    .setAllowedAuthenticators(allowed)
                    .build()
                prompt.authenticate(info)
                cont.invokeOnCancellation { prompt.cancelAuthentication() }
            }
        }
    }
}
