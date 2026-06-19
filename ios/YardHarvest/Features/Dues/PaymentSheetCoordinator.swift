import SwiftUI
@preconcurrency import StripePaymentSheet

/// SwiftUI bridge for Stripe's `PaymentSheet`. The sheet is configured at
/// `present()` time using a server-issued PaymentIntent client secret and the
/// backend's publishable key (so live vs test mode is decided server-side).
///
/// Use:
/// ```
/// .modifier(PaymentSheetCoordinator(
///     isPresented: $present,
///     intent: pi,
///     payeeName: "Far West Omaha Garden",
///     onResult: { ... }
/// ))
/// ```
@MainActor
struct PaymentSheetCoordinator: ViewModifier {
    @Binding var isPresented: Bool
    let intent: DuesPaymentIntent
    let payeeName: String
    let onResult: (PaymentResult) -> Void

    enum PaymentResult {
        case completed
        case canceled
        case failed(String)
    }

    func body(content: Content) -> some View {
        content
            .onChange(of: isPresented) { _, newValue in
                guard newValue else { return }
                isPresented = false
                present()
            }
    }

    private func present() {
        // Wire the publishable key the backend issued — supports test vs live
        // without recompiling the app.
        if let pk = intent.publishableKey {
            STPAPIClient.shared.publishableKey = pk
        }

        guard let clientSecret = intent.clientSecret else {
            // Dev-mode response — Stripe isn't configured on the backend.
            onResult(.failed("Payments aren't configured for this garden yet."))
            return
        }

        var config = PaymentSheet.Configuration()
        config.merchantDisplayName = "YardHarvest · \(payeeName)"
        config.allowsDelayedPaymentMethods = true
        config.appearance = makeAppearance()
        // Apple Pay can be wired here once a merchant identifier is added to
        // the entitlements; leaving it off keeps the v1 PaymentSheet card-first.

        let sheet = PaymentSheet(paymentIntentClientSecret: clientSecret, configuration: config)

        guard let presenter = topPresenter() else {
            onResult(.failed("Couldn't present the payment sheet."))
            return
        }
        sheet.present(from: presenter) { result in
            DispatchQueue.main.async {
                switch result {
                case .completed: onResult(.completed)
                case .canceled:  onResult(.canceled)
                case .failed(let err): onResult(.failed(err.localizedDescription))
                }
            }
        }
    }

    /// Match the brand language in the Stripe-rendered sheet.
    private func makeAppearance() -> PaymentSheet.Appearance {
        var a = PaymentSheet.Appearance()
        a.cornerRadius = 14
        a.colors.background = UIColor(named: "Canvas") ?? .white
        a.colors.primary = UIColor(named: "Ink") ?? .black
        a.colors.componentBackground = UIColor(named: "Surface") ?? .systemGray6
        a.colors.componentBorder = UIColor(named: "Border") ?? .systemGray4
        a.colors.text = UIColor(named: "Ink") ?? .label
        a.colors.textSecondary = UIColor(named: "Muted") ?? .secondaryLabel
        a.primaryButton.cornerRadius = 14
        return a
    }

    private func topPresenter() -> UIViewController? {
        guard let scene = UIApplication.shared.connectedScenes
                .first(where: { $0.activationState == .foregroundActive }) as? UIWindowScene,
              let root = scene.keyWindow?.rootViewController else { return nil }
        var top = root
        while let presented = top.presentedViewController { top = presented }
        return top
    }
}
