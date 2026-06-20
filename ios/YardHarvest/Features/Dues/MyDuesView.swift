import SwiftUI

/// My dues — list of dues records for the active garden with a Pay button on
/// each unpaid record. Tap pay → backend creates a Stripe PaymentIntent →
/// Stripe `PaymentSheet` presents → on success we call confirm-payment.
struct MyDuesView: View {
    let garden: Garden

    @State private var dues: [DuesRecord] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var infoMessage: String?

    // Payment state
    @State private var paymentTarget: DuesRecord?
    @State private var pendingIntent: DuesPaymentIntent?
    @State private var presentSheet = false
    @State private var isCreatingIntent = false

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: dues.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 2,
                   skeletonRows: 3) {
            YHEmpty(systemImage: "dollarsign.circle",
                    title: "No dues yet",
                    message: "The garden organizer hasn't generated dues for you yet.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    if let infoMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(YH.ink)
                            Text(infoMessage)
                                .font(.yhSubheadline)
                                .foregroundStyle(YH.ink)
                        }
                        .padding(YH.Space.md)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(YH.lime)
                        .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                    }
                    ForEach(dues) { record in
                        DuesCard(record: record,
                                 isWorking: paymentTarget?.id == record.id && isCreatingIntent) {
                            Task { await beginPayment(for: record) }
                        }
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("My Dues")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
        .modifier(PaymentSheetCoordinator(
            isPresented: $presentSheet,
            intent: pendingIntent ?? .empty,
            payeeName: garden.name,
            onResult: handlePaymentResult
        ))
    }

    // MARK: - Actions

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { dues = try await APIClient.shared.myDues(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func beginPayment(for record: DuesRecord) async {
        paymentTarget = record
        isCreatingIntent = true
        defer { isCreatingIntent = false }
        do {
            let intent = try await APIClient.shared.payDues(
                gardenID: garden.id, duesID: record.id)

            if intent.isDevMode {
                errorMessage = "Payments aren't fully configured for this garden yet — try again once the organizer finishes payout onboarding."
                Haptics.warning()
                return
            }

            pendingIntent = intent
            // Trigger the modifier — the coordinator presents the Stripe
            // sheet in `onChange(of: isPresented)`.
            presentSheet = true
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func handlePaymentResult(_ result: PaymentSheetCoordinator.PaymentResult) {
        guard let target = paymentTarget, let intent = pendingIntent else { return }
        switch result {
        case .completed:
            Task { await confirm(target: target, intent: intent) }
        case .canceled:
            paymentTarget = nil
            pendingIntent = nil
        case .failed(let message):
            errorMessage = "Payment didn't go through — \(message)"
            paymentTarget = nil
            pendingIntent = nil
            Haptics.error()
        }
    }

    private func confirm(target: DuesRecord, intent: DuesPaymentIntent) async {
        guard let paymentIntentID = intent.paymentIntentId else { return }
        do {
            let message = try await APIClient.shared.confirmDuesPayment(
                gardenID: garden.id,
                duesID: target.id,
                paymentIntentID: paymentIntentID)
            infoMessage = message
            Haptics.success()
            await load(showSpinner: false)
        } catch {
            // Stripe payment succeeded but we couldn't confirm with the backend.
            // The webhook will reconcile; surface a friendly note.
            infoMessage = "Payment received — your record will update in a moment."
            Haptics.success()
        }
        paymentTarget = nil
        pendingIntent = nil
    }
}

private extension DuesPaymentIntent {
    /// Placeholder intent used while no payment is in flight, so the
    /// modifier always has a concrete value to render against.
    static var empty: DuesPaymentIntent {
        DuesPaymentIntent(
            clientSecret: nil, paymentIntentId: nil, publishableKey: nil,
            amount: 0, currency: "USD", duesId: 0,
            routedToManager: nil, devMode: true)
    }
}

private struct DuesCard: View {
    let record: DuesRecord
    var isWorking: Bool
    var onPay: () -> Void

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                HStack {
                    Text(String(record.seasonYear))
                        .font(.yhTitle2).tracking(-0.4).foregroundStyle(YH.ink)
                    Spacer()
                    statusPill
                }
                HStack(alignment: .firstTextBaseline) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("BALANCE").font(.yhCaptionMed).tracking(0.6)
                            .foregroundStyle(YH.muted)
                        Text(record.balance > 0
                             ? "$\(String(format: "%.2f", record.balance))"
                             : "Paid in full")
                            .font(.system(size: 26, weight: .bold))
                            .tracking(-0.4)
                            .foregroundStyle(YH.ink)
                    }
                    Spacer()
                    if record.amountPaid > 0 {
                        VStack(alignment: .trailing, spacing: 2) {
                            Text("PAID").font(.yhCaptionMed).tracking(0.6)
                                .foregroundStyle(YH.muted)
                            Text("$\(String(format: "%.2f", record.amountPaid))")
                                .font(.yhBodyMedium).foregroundStyle(YH.muted)
                        }
                    }
                }
                if record.balance > 0 {
                    YHButton(title: "Pay $\(String(format: "%.2f", record.balance))",
                             systemImage: "creditcard.fill",
                             style: .lime, isLoading: isWorking, action: onPay)
                }
                if let date = record.paymentDate {
                    Text("Paid \(date.formatted(date: .abbreviated, time: .omitted))")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
            }
        }
    }

    @ViewBuilder private var statusPill: some View {
        switch record.status {
        case "paid":    YHPill(text: "Paid", tint: YH.ink, background: YH.lime)
        case "partial": YHPill(text: "Partial", tint: YH.ink, background: YH.surface)
        case "waived":  YHPill(text: "Waived", tint: YH.muted, background: YH.surface)
        case "comp":    YHPill(text: "Comp", tint: YH.muted, background: YH.surface)
        default:        YHPill(text: "Unpaid", tint: .white, background: YH.danger)
        }
    }
}
