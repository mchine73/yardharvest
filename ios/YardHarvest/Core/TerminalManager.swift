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
/// 2. The signed-in user must have completed Stripe Connect onboarding and
///    have the `card_present_payments` capability enabled. The backend's
///    `terminal/connection_token` endpoint returns 409 with
///    `reason: manager_payout_not_ready` otherwise.
/// 3. Tap to Pay connection requires a Stripe Terminal **Location ID** that
///    the reader is registered to. In production the backend should return
///    one; for now `defaultLocationID` is a placeholder that an organizer can
///    override via Settings.
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

    /// Set this from your Stripe dashboard / backend before connecting.
    /// Tap to Pay requires the reader to be associated with a Location.
    var defaultLocationID: String = "tml_simulated"

    func configureIfNeeded() {
        guard !hasConfigured else { return }
        Terminal.setTokenProvider(self)
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

        phase = .discovering
        let reader = try await discoverFirstTapToPayReader()

        phase = .connecting
        let connected = try await connect(reader: reader)
        connectedReader = connected
        phase = .ready
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

    private func connect(reader: Reader) async throws -> Reader {
        let delegate = TapToPayReaderBridge()
        readerDelegate = delegate

        let config: ConnectionConfiguration
        do {
            config = try TapToPayConnectionConfigurationBuilder(
                delegate: delegate,
                locationId: defaultLocationID
            ).build()
        } catch {
            throw error
        }

        return try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Reader, Error>) in
            Terminal.shared.connectReader(reader, connectionConfig: config) { connected, error in
                if let error { cont.resume(throwing: error); return }
                guard let connected else {
                    cont.resume(throwing: NSError(domain: "TerminalManager", code: -1,
                                                  userInfo: [NSLocalizedDescriptionKey: "Reader connect returned no reader"]))
                    return
                }
                cont.resume(returning: connected)
            }
        }
    }

    private func retrievePaymentIntent(clientSecret: String) async throws -> PaymentIntent {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<PaymentIntent, Error>) in
            Terminal.shared.retrievePaymentIntent(clientSecret: clientSecret) { intent, error in
                if let error { cont.resume(throwing: error); return }
                guard let intent else {
                    cont.resume(throwing: NSError(domain: "TerminalManager", code: -2,
                                                  userInfo: [NSLocalizedDescriptionKey: "No payment intent returned"]))
                    return
                }
                cont.resume(returning: intent)
            }
        }
    }

    private func collectPaymentMethod(_ intent: PaymentIntent) async throws -> PaymentIntent {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<PaymentIntent, Error>) in
            self.activeCancelable = Terminal.shared.collectPaymentMethod(intent) { collected, error in
                if let error { cont.resume(throwing: error); return }
                guard let collected else {
                    cont.resume(throwing: NSError(domain: "TerminalManager", code: -3,
                                                  userInfo: [NSLocalizedDescriptionKey: "No payment method collected"]))
                    return
                }
                cont.resume(returning: collected)
            }
        }
    }

    private func confirmPayment(_ intent: PaymentIntent) async throws -> PaymentIntent {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<PaymentIntent, Error>) in
            Terminal.shared.confirmPaymentIntent(intent) { confirmed, error in
                if let error { cont.resume(throwing: error); return }
                guard let confirmed else {
                    cont.resume(throwing: NSError(domain: "TerminalManager", code: -4,
                                                  userInfo: [NSLocalizedDescriptionKey: "No confirmed payment intent"]))
                    return
                }
                cont.resume(returning: confirmed)
            }
        }
    }
}

// MARK: - ConnectionTokenProvider

extension TerminalManager: ConnectionTokenProvider {
    nonisolated func fetchConnectionToken(_ completion: @escaping ConnectionTokenCompletionBlock) {
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
