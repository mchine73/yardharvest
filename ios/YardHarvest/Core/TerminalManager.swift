import Foundation
import Observation
import StripeTerminal

/// SwiftUI-facing wrapper around the Stripe Terminal SDK for Tap-to-Pay on
/// iPhone. State changes flip the published `phase` property, which
/// `AdminCollectDuesView` observes to render the right UI.
///
/// Caveats (also documented in `AdminCollectDuesView`):
/// 1. Tap to Pay on iPhone requires the `proximity-reader.payment.acceptance`
///    Apple entitlement (granted after a review request to Apple). In Debug
///    builds the SDK uses a simulated reader so the flow works end-to-end
///    without the entitlement and without real hardware.
/// 2. The signed-in user must have completed Stripe Connect onboarding, with
///    the `card_payments` capability active — card-present acceptance rides on
///    that one; Stripe has no separate card_present capability. The backend's
///    `terminal/connection_token` endpoint returns 409 with
///    `reason: manager_payout_not_ready` or `card_present_not_active`.
/// 3. Tap to Pay connection requires a Stripe Terminal **Location ID** that
///    the reader is registered to. The backend's `terminal/connection_token`
///    endpoint returns one (`location_id`) from the manager's own Connect
///    account, created on demand from their onboarding address. It returns 409
///    with `reason: terminal_location_unavailable` if it can't.
@MainActor
@Observable
final class TerminalManager: NSObject {

    enum Phase: Equatable {
        case idle
        case discovering
        case connecting
        case ready                // Reader connected; PI is being created server-side
        case collecting           // Waiting for the customer to tap their card
        case processing           // Stripe is settling the payment
        case succeeded(message: String)
        case canceled
        case failed(String)
    }

    private(set) var phase: Phase = .idle
    private(set) var connectedReader: Reader?
    private var hasConfigured = false
    private var activeCancelable: Cancelable?
    /// Retained delegate refs — the SDK requires these live for the duration
    /// of the connection.
    private var discoveryDelegate: OneShotDiscoveryDelegate?
    private var readerDelegate: TapToPayReaderBridge?

    /// Stripe Terminal Location the reader registers to. Tap to Pay requires
    /// one, and it must belong to the manager's own Connect account — so it's
    /// resolved from the backend at connect time rather than hardcoded. The
    /// simulated reader accepts the well-known simulator Location.
    private(set) var resolvedLocationID: String?

    /// Location used for the in-process simulated reader, which never talks to
    /// a real Stripe Location.
    private static let simulatedLocationID = "tml_simulated"

    /// Cached for the life of the process. The manager's Location doesn't
    /// change between charges, and each charge screen builds its own
    /// TerminalManager — without this, every single tap paid for another
    /// round-trip (and burned a connection token) to learn the same id.
    private static var cachedLocationID: String?

    /// Process-wide ConnectionTokenProvider. Stripe Terminal requires
    /// `Terminal.setTokenProvider(_:)` to be called before ANY access to
    /// `Terminal.shared` — including the static `supportsReaders` capability
    /// check used by `deviceSupportsTapToPay`. Touching `Terminal.shared`
    /// first raises a hard `fatalError` on real devices (the simulator is
    /// more lenient). Because the capability check is static and runs from
    /// `PaymentHubView.body` before any `TerminalManager` instance exists,
    /// we register a singleton provider here at the type level.
    private static let sharedTokenProvider = SharedConnectionTokenProvider()
    private static var hasInitializedSDK = false

    /// Idempotently registers the shared token provider with the Stripe
    /// Terminal SDK. Call this before any code path that touches
    /// `Terminal.shared`. Safe to call multiple times — only the first
    /// invocation actually does work. 
    static func ensureSDKInitialized() {
        guard !hasInitializedSDK else { return }
        Terminal.setTokenProvider(sharedTokenProvider)
        hasInitializedSDK = true
    }

    /// Runtime check that gates the entire Tap-to-Pay code path. Returns
    /// true only when the SDK can actually be exercised without crashing.
    ///
    /// On a real device this requires:
    ///   1. iOS 16.4+ (the SDK and Apple's ProximityReader both require it).
    ///   2. Hardware support (iPhone XS or later — checked via the SDK).
    ///   3. The `com.apple.developer.proximity-reader.payment.acceptance`
    ///      Apple entitlement (granted only after a separate review).
    ///      Without it, Stripe's Tap-to-Pay path eventually calls into
    ///      Apple's ProximityReader framework which throws an NSException
    ///      that Swift can't catch — a hard, immediate crash.
    ///
    /// Because iOS has no public API to read the running app's
    /// entitlements at runtime (`SecTaskCopyValueForEntitlement` is
    /// macOS-only), we gate Tap-to-Pay on a compile-time flag:
    /// `YH_TAP_TO_PAY_ENABLED`. Flip it on in `project.yml`'s
    /// `SWIFT_ACTIVE_COMPILATION_CONDITIONS` once Apple has granted the
    /// entitlement, the .entitlements file has the key, and you've added
    /// a real Stripe Terminal Location ID. Until then, real-device builds
    /// report "unavailable" in the UI, the Charge button stays disabled,
    /// and the app never touches the crash-inducing SDK path.
    ///
    /// The simulator uses an in-process simulated reader that doesn't go
    /// through ProximityReader at all, so the entitlement is moot there
    /// and we always return true. That lets the whole flow be walked
    /// end-to-end during development.
    static var deviceSupportsTapToPay: Bool {
        #if targetEnvironment(simulator)
        return true
        #else
        #if YH_TAP_TO_PAY_ENABLED
        if #available(iOS 16.4, *) {
            ensureSDKInitialized()
            // NS_REFINED_FOR_SWIFT bridges this to `Result<Void, Error>`.
            let result = Terminal.shared.supportsReaders(
                of: .tapToPay,
                discoveryMethod: .tapToPay,
                simulated: false
            )
            if case .success = result { return true }
            return false
        }
        return false
        #else
        return false
        #endif
        #endif
    }

    /// Human-readable reason Tap to Pay isn't usable on this device — used
    /// by the UI to explain what's missing. Returns nil when supported.
    /// Order matters: report the most actionable reason first.
    static var tapToPayUnavailableReason: String? {
        if deviceSupportsTapToPay { return nil }
        #if !targetEnvironment(simulator) && !YH_TAP_TO_PAY_ENABLED
        return "Tap to Pay is disabled in this build. It needs Apple's proximity-reader.payment.acceptance entitlement (request it at developer.apple.com/contact/request/tap-to-pay-on-iphone), the entitlement key in the .entitlements file, and the YH_TAP_TO_PAY_ENABLED build flag turned on. Until then you can walk the full flow in the iOS simulator."
        #else
        if #available(iOS 16.4, *) {
            return "Your device's hardware doesn't support Tap to Pay. iPhone XS or later is required."
        }
        return "Tap to Pay requires iOS 16.4 or later."
        #endif
    }

    func configureIfNeeded() {
        guard !hasConfigured else { return }
        Self.ensureSDKInitialized()
        hasConfigured = true
    }

    /// Discover + connect to the local Tap-to-Pay reader.
    func connectLocalReader() async throws {
        configureIfNeeded()

        if Terminal.shared.connectionStatus == .connected,
           let reader = Terminal.shared.connectedReader {
            connectedReader = reader
            phase = .ready
            return
        }

        // Resolve the Location before discovery so a misconfigured account
        // fails with the backend's actionable message rather than an opaque
        // SDK error midway through connecting.
        let locationID = try await resolveLocationID()

        phase = .discovering
        let reader = try await discoverFirstTapToPayReader()

        phase = .connecting
        let connected = try await connect(reader: reader, locationID: locationID)
        connectedReader = connected
        phase = .ready
    }

    /// Connect the reader ahead of the first charge so that tapping Charge
    /// goes straight to Apple's card sheet instead of narrating discovery and
    /// connection at the operator. Speculative work: failures are swallowed,
    /// and the real charge path will surface them properly if it hits them.
    func prepare() async {
        guard Self.deviceSupportsTapToPay else { return }
        guard phase == .idle else { return }
        do { try await connectLocalReader() } catch { phase = .idle }
    }

    /// Collect a single Tap-to-Pay payment for an already-created PaymentIntent.
    @discardableResult
    func collect(clientSecret: String) async throws -> String {
        configureIfNeeded()
        do {
            phase = .collecting
            let intent = try await retrievePaymentIntent(clientSecret: clientSecret)
            let withMethod = try await collectPaymentMethod(intent)
            phase = .processing
            let confirmed = try await confirmPayment(withMethod)
            let id = confirmed.stripeId ?? ""
            phase = .succeeded(message: "Payment received.")
            return id
        } catch {
            phase = .failed(error.localizedDescription)
            throw error
        }
    }

    func cancelInFlight() {
        activeCancelable?.cancel { _ in }
        activeCancelable = nil
        phase = .canceled
    }

    func reset() { phase = .idle }

    // MARK: - Callback → async bridges

    private func discoverFirstTapToPayReader() async throws -> Reader {
        // Belt-and-braces: even though the UI hard-blocks the Charge button
        // when `deviceSupportsTapToPay` is false, throw early if we somehow
        // get here without the prerequisites. Better an in-app error than
        // a hard crash from ProximityReader.
        guard Self.deviceSupportsTapToPay else {
            throw NSError(
                domain: "TerminalManager",
                code: -2,
                userInfo: [NSLocalizedDescriptionKey:
                    Self.tapToPayUnavailableReason
                    ?? "Tap to Pay isn't available on this device."])
        }
        let config: DiscoveryConfiguration
        do {
            #if targetEnvironment(simulator)
            config = try TapToPayDiscoveryConfigurationBuilder().setSimulated(true).build()
            #else
            config = try TapToPayDiscoveryConfigurationBuilder().build()
            #endif
        } catch {
            throw error
        }

        let delegate = OneShotDiscoveryDelegate()
        discoveryDelegate = delegate

        return try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Reader, Error>) in
            delegate.onFirst = { result in
                cont.resume(with: result)
            }
            self.activeCancelable = Terminal.shared.discoverReaders(
                config, delegate: delegate
            ) { error in
                if let error { cont.resume(throwing: error) }
                // On success the delegate's `didUpdateDiscoveredReaders` fires.
            }
        }
    }

    /// Fetch the manager's Terminal Location from the backend. On the
    /// simulator the reader is in-process, so the simulated Location is used
    /// and no network call is required.
    private func resolveLocationID() async throws -> String {
        #if targetEnvironment(simulator)
        resolvedLocationID = Self.simulatedLocationID
        return Self.simulatedLocationID
        #else
        if let cached = Self.cachedLocationID {
            resolvedLocationID = cached
            return cached
        }
        let session = try await APIClient.shared.terminalSession()
        guard let id = session.locationID, !id.isEmpty else {
            throw NSError(
                domain: "TerminalManager",
                code: -3,
                userInfo: [NSLocalizedDescriptionKey:
                    "This garden's Stripe account has no payment location set "
                    + "up yet. Add a business address in Stripe, then try again."])
        }
        Self.cachedLocationID = id
        resolvedLocationID = id
        return id
        #endif
    }

    private func connect(reader: Reader, locationID: String) async throws -> Reader {
        let delegate = TapToPayReaderBridge()
        readerDelegate = delegate

        let config: ConnectionConfiguration
        do {
            config = try TapToPayConnectionConfigurationBuilder(
                delegate: delegate,
                locationId: locationID
            ).build()
        } catch {
            throw error
        }

        return try await Self.awaitSDK("connect reader") { completion in
            Terminal.shared.connectReader(reader, connectionConfig: config,
                                          completion: completion)
        }
    }

    private func retrievePaymentIntent(clientSecret: String) async throws -> PaymentIntent {
        try await Self.awaitSDK("retrieve payment intent") { completion in
            Terminal.shared.retrievePaymentIntent(clientSecret: clientSecret,
                                                  completion: completion)
        }
    }

    private func collectPaymentMethod(_ intent: PaymentIntent) async throws -> PaymentIntent {
        try await Self.awaitSDK("collect payment method") { completion in
            self.activeCancelable = Terminal.shared.collectPaymentMethod(intent,
                                                                          completion: completion)
        }
    }

    private func confirmPayment(_ intent: PaymentIntent) async throws -> PaymentIntent {
        try await Self.awaitSDK("confirm payment") { completion in
            Terminal.shared.confirmPaymentIntent(intent, completion: completion)
        }
    }

    /// Single bridge for the SDK's `(Result?, Error?) -> Void` callbacks →
    /// `async throws`. Folds the same "if let error / guard let result"
    /// pattern that was duplicated across four call sites.
    private static func awaitSDK<R>(_ label: String,
                                    _ work: @escaping (@escaping (R?, Error?) -> Void) -> Void)
                                    async throws -> R {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<R, Error>) in
            work { value, error in
                if let error { cont.resume(throwing: error); return }
                guard let value else {
                    cont.resume(throwing: NSError(
                        domain: "TerminalManager",
                        code: -1,
                        userInfo: [NSLocalizedDescriptionKey: "Stripe SDK returned no result for: \(label)"]
                    ))
                    return
                }
                cont.resume(returning: value)
            }
        }
    }
}

// MARK: - Shared ConnectionTokenProvider

/// Process-wide ConnectionTokenProvider used to satisfy Stripe Terminal's
/// "setTokenProvider before Terminal.shared" requirement at any call site —
/// including the static capability check. Fetches a fresh connection token
/// from the backend whenever the SDK asks. Lifetime is the whole process,
/// matching the SDK's own singleton.
private final class SharedConnectionTokenProvider: NSObject, ConnectionTokenProvider {
    func fetchConnectionToken(_ completion: @escaping ConnectionTokenCompletionBlock) {
        Task {
            do {
                let token = try await APIClient.shared.terminalConnectionToken()
                completion(token, nil)
            } catch {
                completion(nil, error)
            }
        }
    }
}

// MARK: - One-shot discovery delegate

/// Tap-to-Pay discovery emits the local device as a single reader once.
/// This delegate forwards the first reader to the awaiting continuation.
private final class OneShotDiscoveryDelegate: NSObject, DiscoveryDelegate {
    var onFirst: ((Result<Reader, Error>) -> Void)?
    private var fired = false

    func terminal(_ terminal: Terminal, didUpdateDiscoveredReaders readers: [Reader]) {
        guard !fired, let reader = readers.first else { return }
        fired = true
        onFirst?(.success(reader))
    }
}

// MARK: - Tap to Pay reader delegate

/// Required by the SDK for the lifetime of the reader connection. We don't
/// need to react to software-update events for the v1 flow, but the protocol
/// requires every method to be implemented.
private final class TapToPayReaderBridge: NSObject, TapToPayReaderDelegate {
    func tapToPayReader(_ reader: Reader,
                        didStartInstallingUpdate update: ReaderSoftwareUpdate,
                        cancelable: Cancelable?) { /* no-op */ }

    func tapToPayReader(_ reader: Reader,
                        didReportReaderSoftwareUpdateProgress progress: Float) { /* no-op */ }

    func tapToPayReader(_ reader: Reader,
                        didFinishInstallingUpdate update: ReaderSoftwareUpdate?,
                        error: Error?) { /* no-op */ }

    func tapToPayReader(_ reader: Reader,
                        didRequestReaderInput inputOptions: ReaderInputOptions = []) { /* no-op */ }

    func tapToPayReader(_ reader: Reader,
                        didRequestReaderDisplayMessage displayMessage: ReaderDisplayMessage) { /* no-op */ }
}
