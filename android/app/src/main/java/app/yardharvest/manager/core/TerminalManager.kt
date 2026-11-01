package app.yardharvest.manager.core

import android.Manifest
import android.content.Context
import android.content.pm.PackageManager
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import app.yardharvest.manager.BuildConfig
import app.yardharvest.manager.api.terminalConnectionToken
import app.yardharvest.manager.api.terminalSession
import com.stripe.stripeterminal.Terminal
import com.stripe.stripeterminal.external.callable.Callback
import com.stripe.stripeterminal.external.callable.Cancelable
import com.stripe.stripeterminal.external.callable.ConnectionTokenCallback
import com.stripe.stripeterminal.external.callable.ConnectionTokenProvider
import com.stripe.stripeterminal.external.callable.DiscoveryListener
import com.stripe.stripeterminal.external.callable.PaymentIntentCallback
import com.stripe.stripeterminal.external.callable.ReaderCallback
import com.stripe.stripeterminal.external.callable.TapToPayReaderListener
import com.stripe.stripeterminal.external.callable.TerminalListener
import com.stripe.stripeterminal.external.models.ConnectionConfiguration
import com.stripe.stripeterminal.external.models.ConnectionStatus
import com.stripe.stripeterminal.external.models.ConnectionTokenException
import com.stripe.stripeterminal.external.models.DeviceType
import com.stripe.stripeterminal.external.models.DiscoveryConfiguration
import com.stripe.stripeterminal.external.models.PaymentIntent
import com.stripe.stripeterminal.external.models.Reader
import com.stripe.stripeterminal.external.models.TerminalException
import com.stripe.stripeterminal.log.LogLevel
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Deferred
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.async
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/**
 * Compose-facing wrapper around Stripe Terminal for Tap to Pay on Android —
 * the counterpart of the iOS TerminalManager. Each payments screen builds its
 * own instance to observe [phase]; the SDK connection itself is process-wide.
 *
 * Caveats, as on iOS:
 * 1. The garden's Connect account needs `card_payments` active. The backend's
 *    connection-token endpoint answers 409 with a reason when it isn't.
 * 2. A reader registers to a Stripe Terminal Location on the manager's own
 *    Connect account; the backend returns it with the token.
 * 3. Android-specific: Stripe refuses real Tap to Pay in debuggable builds, so
 *    debug builds use the simulated reader and release builds the real one.
 */
class TerminalManager {

    sealed interface Phase {
        data object Idle : Phase
        data object Discovering : Phase
        data object Connecting : Phase
        /** Reader connected; the PaymentIntent is being created server-side. */
        data object Ready : Phase
        /** Waiting for the customer to tap. */
        data object Collecting : Phase
        /** Stripe is settling the payment. */
        data object Processing : Phase
        data class Succeeded(val message: String) : Phase
        data object Canceled : Phase
        data class Failed(val message: String) : Phase
    }

    var phase: Phase by mutableStateOf(Phase.Idle)
        private set

    private var activeCancelable: Cancelable? = null

    /**
     * Discover + connect the phone's own Tap to Pay reader. Concurrent callers
     * share one attempt — [prepare] starts a connect in the background, and a
     * manager who taps Charge immediately must not start a second one.
     */
    suspend fun connectLocalReader() {
        val existing = connectTask
        if (existing != null && existing.isActive) {
            existing.await()
            adoptIfConnected()
            return
        }
        val task = processScope.async { performConnect() }
        connectTask = task
        try { task.await() } finally { if (connectTask === task) connectTask = null }
    }

    private fun adoptIfConnected(): Boolean {
        val t = Terminal.getInstance()
        if (t.connectionStatus == ConnectionStatus.CONNECTED && t.connectedReader != null) {
            phase = Phase.Ready
            return true
        }
        return false
    }

    private suspend fun performConnect() {
        ensureSdkInitialized()
        // Already connected — adopt it. The SDK permits one reader per process.
        if (adoptIfConnected()) return

        // Resolve the Location first so a misconfigured account fails with the
        // backend's actionable message rather than an opaque SDK error.
        val locationId = resolveLocationId()

        phase = Phase.Discovering
        val reader = discoverFirstTapToPayReader()

        phase = Phase.Connecting
        try {
            connect(reader, locationId)
        } catch (e: Exception) {
            // A connect that lost the race still leaves a usable reader.
            if (adoptIfConnected()) return
            throw e
        }
        phase = Phase.Ready
    }

    /**
     * Connect ahead of the first charge so tapping Charge goes straight to the
     * card prompt. Speculative: failures are swallowed and resurface on the
     * real charge path.
     */
    suspend fun prepare(context: Context, gardenId: Int? = null) {
        if (gardenId != null) currentGardenId = gardenId
        if (!deviceSupportsTapToPay(context) || !hasLocationPermission(context)) return
        if (phase != Phase.Idle) return
        try { connectLocalReader() } catch (_: Exception) { phase = Phase.Idle }
    }

    /** Collect a single Tap to Pay payment for an already-created PaymentIntent. Returns its id. */
    suspend fun collect(clientSecret: String): String {
        ensureSdkInitialized()
        try {
            phase = Phase.Collecting
            val intent = retrievePaymentIntent(clientSecret)
            val withMethod = collectPaymentMethod(intent)
            phase = Phase.Processing
            val confirmed = confirmPayment(withMethod)
            phase = Phase.Succeeded("Payment received.")
            return confirmed.id ?: ""
        } catch (e: Exception) {
            phase = Phase.Failed(describe(e))
            throw e
        }
    }

    fun cancelInFlight() {
        activeCancelable?.cancel(object : Callback {
            override fun onSuccess() {}
            override fun onFailure(e: TerminalException) {}
        })
        activeCancelable = null
        phase = Phase.Canceled
    }

    fun reset() { phase = Phase.Idle }

    // ---- Callback → suspend bridges -------------------------------------------------

    private suspend fun discoverFirstTapToPayReader(): Reader {
        if (!isSimulated && !Terminal.getInstance()
                .supportsReadersOfType(DeviceType.TAP_TO_PAY_DEVICE, discoveryConfig).isSupported
        ) throw IllegalStateException("Tap to Pay isn't available on this phone.")
        // Stripe needs location to discover the phone's own reader; prepare()
        // checks first, but a charge can arrive here after the user revoked it.
        if (ContextCompat.checkSelfPermission(appContext, Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            throw IllegalStateException("Allow location access so Tap to Pay can start.")
        }

        return suspendCancellableCoroutine { cont ->
            // One-shot latch: the listener resumes when the reader appears, and
            // the completion may also fire later (with an error, or success once
            // connected). Resuming twice would crash.
            var resumed = false
            fun resumeOnce(result: Result<Reader>) {
                if (resumed) return
                resumed = true
                result.fold({ cont.resume(it) }, { cont.resumeWithException(it) })
            }
            activeCancelable = Terminal.getInstance().discoverReaders(
                discoveryConfig,
                object : DiscoveryListener {
                    override fun onUpdateDiscoveredReaders(readers: List<Reader>) {
                        readers.firstOrNull()?.let { resumeOnce(Result.success(it)) }
                    }
                },
                object : Callback {
                    override fun onSuccess() {}
                    override fun onFailure(e: TerminalException) { resumeOnce(Result.failure(e)) }
                },
            )
        }
    }

    private suspend fun resolveLocationId(): String {
        if (isSimulated) return SIMULATED_LOCATION_ID
        cachedLocationId?.let { return it }
        val session = ApiClient.terminalSession(currentGardenId)
        val id = session.locationId?.takeIf { it.isNotEmpty() }
            ?: throw IllegalStateException(
                "This garden's Stripe account has no payment location set up yet. " +
                    "Add a business address in Stripe, then try again.",
            )
        cachedLocationId = id
        return id
    }

    private suspend fun connect(reader: Reader, locationId: String): Reader = suspendCancellableCoroutine { cont ->
        val config = ConnectionConfiguration.TapToPayConnectionConfiguration(locationId, true, readerBridge)
        Terminal.getInstance().connectReader(reader, config, object : ReaderCallback {
            override fun onSuccess(reader: Reader) { if (cont.isActive) cont.resume(reader) }
            override fun onFailure(e: TerminalException) { if (cont.isActive) cont.resumeWithException(e) }
        })
    }

    private suspend fun retrievePaymentIntent(clientSecret: String): PaymentIntent = suspendCancellableCoroutine { cont ->
        Terminal.getInstance().retrievePaymentIntent(clientSecret, intentCallback(cont))
    }

    private suspend fun collectPaymentMethod(intent: PaymentIntent): PaymentIntent = suspendCancellableCoroutine { cont ->
        activeCancelable = Terminal.getInstance().collectPaymentMethod(intent, intentCallback(cont))
    }

    private suspend fun confirmPayment(intent: PaymentIntent): PaymentIntent = suspendCancellableCoroutine { cont ->
        activeCancelable = Terminal.getInstance().confirmPaymentIntent(intent, intentCallback(cont))
    }

    private fun intentCallback(cont: kotlinx.coroutines.CancellableContinuation<PaymentIntent>) =
        object : PaymentIntentCallback {
            override fun onSuccess(paymentIntent: PaymentIntent) { if (cont.isActive) cont.resume(paymentIntent) }
            override fun onFailure(e: TerminalException) { if (cont.isActive) cont.resumeWithException(e) }
        }

    companion object {
        /** Stripe refuses real Tap to Pay in debuggable builds. */
        val isSimulated: Boolean get() = BuildConfig.DEBUG
        private const val SIMULATED_LOCATION_ID = "tml_simulated"

        private val discoveryConfig get() = DiscoveryConfiguration.TapToPayDiscoveryConfiguration(isSimulated)

        /**
         * The garden whose payout account the reader session belongs to. The
         * payments screens set it before connecting; the token provider reads
         * it so every connection token is scoped to that garden's account —
         * which is what lets a treasurer charge, not just the organizer.
         */
        @Volatile var currentGardenId: Int? = null

        /** The manager's Location doesn't change between charges; cache it for the process. */
        @Volatile private var cachedLocationId: String? = null

        private val processScope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
        private var connectTask: Deferred<Unit>? = null
        private lateinit var appContext: Context

        fun init(context: Context) { appContext = context.applicationContext }

        /** Fetches a fresh connection token from the backend whenever the SDK asks. */
        private val tokenProvider = object : ConnectionTokenProvider {
            override fun fetchConnectionToken(callback: ConnectionTokenCallback) {
                processScope.launch {
                    try {
                        callback.onSuccess(ApiClient.terminalConnectionToken(currentGardenId))
                    } catch (e: Exception) {
                        callback.onFailure(ConnectionTokenException(e.userMessage, e))
                    }
                }
            }
        }

        /** Required for the life of the connection; v1 doesn't react to its events. */
        private val readerBridge = object : TapToPayReaderListener {}

        fun ensureSdkInitialized() {
            if (Terminal.isInitialized()) return
            Terminal.initTerminal(appContext, LogLevel.NONE, tokenProvider, object : TerminalListener {})
        }

        fun hasLocationPermission(context: Context): Boolean =
            ContextCompat.checkSelfPermission(context, Manifest.permission.ACCESS_FINE_LOCATION) == PackageManager.PERMISSION_GRANTED

        /** Gates the whole Tap to Pay path: NFC hardware plus Stripe's own device check. */
        fun deviceSupportsTapToPay(context: Context): Boolean {
            if (!context.packageManager.hasSystemFeature(PackageManager.FEATURE_NFC)) return isSimulated
            return try {
                ensureSdkInitialized()
                Terminal.getInstance().supportsReadersOfType(DeviceType.TAP_TO_PAY_DEVICE, discoveryConfig).isSupported
            } catch (_: Exception) {
                false
            }
        }

        /** Why Tap to Pay isn't usable here, for the UI. Null when supported. */
        fun tapToPayUnavailableReason(context: Context): String? {
            if (deviceSupportsTapToPay(context)) return null
            if (!context.packageManager.hasSystemFeature(PackageManager.FEATURE_NFC)) {
                return "This phone doesn't have NFC, which Tap to Pay needs."
            }
            val err = try {
                Terminal.getInstance().supportsReadersOfType(DeviceType.TAP_TO_PAY_DEVICE, discoveryConfig).error?.message
            } catch (e: Exception) {
                e.message
            }
            return err ?: "This phone doesn't support Tap to Pay. It needs Android 11 or later, NFC, and Google Play services."
        }

        /**
         * Tear down any Tap to Pay session on sign-out. The connected reader is
         * registered to the departing manager's Connect account, and the cached
         * Location is process-wide — two organizers sharing a phone at a sign-up
         * table is an ordinary day, and this is money routing.
         */
        suspend fun teardownForSignOut() {
            cachedLocationId = null
            if (!Terminal.isInitialized()) return
            val t = Terminal.getInstance()
            if (t.connectionStatus != ConnectionStatus.CONNECTED) return
            suspendCancellableCoroutine { cont ->
                t.disconnectReader(object : Callback {
                    override fun onSuccess() { if (cont.isActive) cont.resume(Unit) }
                    override fun onFailure(e: TerminalException) { if (cont.isActive) cont.resume(Unit) }
                })
            }
        }

        fun describe(e: Throwable): String =
            (e as? TerminalException)?.errorMessage ?: e.userMessage
    }
}
