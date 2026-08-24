import SwiftUI

/// "Plain terminal" — accept an ad-hoc Tap-to-Pay payment for any amount
/// and memo (sales of plant starts, tool deposits, workshop fees, etc.).
/// Not tied to a dues record; the Stripe Connect dashboard is the receipt
/// trail.
struct AdHocChargeView: View {
    let garden: Garden

    @Environment(\.dismiss) private var dismiss
    @State private var terminal = TerminalManager()
    @State private var amountText: String = ""
    @State private var memo: String = ""
    @State private var errorMessage: String?
    @State private var infoMessage: String?
    @State private var isLaunching = false
    @State private var lastIntent: InPersonPaymentIntent?

    /// Cents the user typed in. We constrain to 50¢ minimum (Stripe rule) +
    /// $10,000 ceiling (the backend enforces both, this is for UX).
    private var amountCents: Int {
        let cleaned = amountText.replacingOccurrences(of: ",", with: "")
        guard let dollars = Double(cleaned) else { return 0 }
        return Int(round(dollars * 100))
    }

    private var canCharge: Bool {
        amountCents >= 50
            && amountCents <= 1_000_000
            && terminal.phase != .processing
            && TerminalManager.deviceSupportsTapToPay
    }

    private var hasSucceeded: Bool {
        if case .succeeded = terminal.phase { return true }
        return false
    }

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                if !TerminalManager.deviceSupportsTapToPay,
                   let reason = TerminalManager.tapToPayUnavailableReason {
                    unsupportedNotice(reason)
                }
                amountCard
                memoCard
                statusCard
                actionButton
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle("New Sale")
        .navigationBarTitleDisplayMode(.inline)
        .task { await terminal.prepare(gardenID: garden.id) }
    }

    // MARK: - Sections

    private var amountCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("AMOUNT").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(alignment: .firstTextBaseline, spacing: 4) {
                    Text("$")
                        .font(.system(size: 36, weight: .bold))
                        .tracking(-0.5)
                        .foregroundStyle(YH.muted)
                    TextField("0.00", text: $amountText)
                        .font(.system(size: 36, weight: .bold))
                        .tracking(-0.5)
                        .foregroundStyle(YH.ink)
                        .keyboardType(.decimalPad)
                }
                quickAmountRow
            }
        }
    }

    private var quickAmountRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach([5, 10, 20, 50, 100], id: \.self) { dollars in
                    Button {
                        Haptics.selection()
                        amountText = "\(dollars).00"
                    } label: {
                        Text("$\(dollars)")
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 12)
                            .padding(.vertical, 6)
                            .foregroundStyle(YH.ink)
                            .background(YH.surface)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    private var memoCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("MEMO").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                TextField("What's this for? (e.g. 4 tomato starts)",
                          text: $memo, axis: .vertical)
                    .lineLimit(1...3)
                    .font(.yhBody)
                    .foregroundStyle(YH.ink)
                    .padding(12)
                    .background(YH.surface)
                    .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                                .strokeBorder(YH.border))
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                Text("Shows up on the cardholder's receipt + your Stripe dashboard.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }

    private var statusCard: some View {
        YHBand(tint: bandTint) {
            HStack(spacing: 12) {
                Image(systemName: statusIcon)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(YH.ink)
                    .symbolEffect(.pulse, options: pulseOptions, value: phaseSignature)
                VStack(alignment: .leading, spacing: 2) {
                    Text(statusTitle).font(.yhTitle3).foregroundStyle(YH.ink)
                    Text(statusBody)
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    @ViewBuilder
    private var actionButton: some View {
        switch terminal.phase {
        case .idle, .canceled, .failed, .discovering, .connecting, .ready:
            YHButton(title: chargeLabel,
                     systemImage: "wave.3.right",
                     style: .lime,
                     isLoading: isLaunching) {
                Task { await begin() }
            }
            .disabled(!canCharge)
        case .succeeded:
            VStack(spacing: YH.Space.sm) {
                YHButton(title: "New Sale",
                         systemImage: "plus.circle.fill",
                         style: .lime) {
                    amountText = ""
                    memo = ""
                    lastIntent = nil
                    infoMessage = nil
                    terminal.reset()
                }
                YHButton(title: "Done", systemImage: "checkmark", style: .ghost) {
                    dismiss()
                }
            }
        default:
            YHButton(title: "Cancel",
                     systemImage: "xmark",
                     style: .ghost) {
                terminal.cancelInFlight()
            }
        }
        if let infoMessage {
            Text(infoMessage).font(.yhSubheadline).foregroundStyle(YH.ink)
        }
        if let errorMessage {
            Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
        }
    }

    private func unsupportedNotice(_ reason: String) -> some View {
        YHCard {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(YH.warning)
                    .frame(width: 32, height: 32)
                    .background(YH.warning.opacity(0.15))
                    .clipShape(RoundedRectangle(cornerRadius: 9))
                VStack(alignment: .leading, spacing: 4) {
                    Text("Tap to Pay unavailable")
                        .font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text(reason)
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                Spacer()
            }
        }
    }

    // MARK: - Copy

    private var chargeLabel: String {
        if amountCents < 50 { return "Enter an amount" }
        return "Charge $\(String(format: "%.2f", Double(amountCents) / 100))"
    }

    private var phaseSignature: String {
        switch terminal.phase {
        case .idle: return "idle"
        case .discovering: return "discovering"
        case .connecting: return "connecting"
        case .ready: return "ready"
        case .collecting: return "collecting"
        case .processing: return "processing"
        case .succeeded: return "succeeded"
        case .canceled: return "canceled"
        case .failed: return "failed"
        }
    }

    private var statusTitle: String {
        switch terminal.phase {
        case .idle:        return "Ready to charge"
        case .discovering: return "Finding reader…"
        case .connecting:  return "Connecting…"
        case .ready:       return "Reader connected"
        case .collecting:  return "Tap card here"
        case .processing:  return "Processing…"
        case .succeeded:   return "Payment received"
        case .canceled:    return "Canceled"
        case .failed:      return "Couldn't charge"
        }
    }

    private var statusBody: String {
        switch terminal.phase {
        case .idle:
            return "Enter an amount and tap Charge to start."
        case .discovering:
            return "Locating the Tap-to-Pay reader (your iPhone)."
        case .connecting:
            return "Establishing the secure session."
        case .ready:
            return "Setting up payment…"
        case .collecting:
            return "Hold the customer's card or contactless phone against the top of this iPhone."
        case .processing:
            return "Stripe is finalizing the charge — keep this screen open."
        case .succeeded:
            return "Funds will land in the garden's Connect account."
        case .canceled:
            return "Tap Charge to try again."
        case let .failed(message):
            return message
        }
    }

    private var statusIcon: String {
        switch terminal.phase {
        case .idle:        return "wave.3.right"
        case .discovering: return "antenna.radiowaves.left.and.right"
        case .connecting:  return "link"
        case .ready:       return "checkmark.circle"
        case .collecting:  return "wave.3.right"
        case .processing:  return "hourglass"
        case .succeeded:   return "checkmark.seal.fill"
        case .canceled:    return "xmark.circle"
        case .failed:      return "exclamationmark.triangle.fill"
        }
    }

    private var bandTint: YHBandTint {
        switch terminal.phase {
        case .failed, .canceled: return .dark
        default:                 return .lime
        }
    }

    private var pulseOptions: SymbolEffectOptions {
        switch terminal.phase {
        case .collecting, .processing, .discovering, .connecting:
            return .repeating
        default:
            return .nonRepeating
        }
    }

    // MARK: - Flow

    private func begin() async {
        // A second tap mid-charge would start an overlapping collect and wedge
        // the SDK — one charge at a time.
        guard !isLaunching else { return }
        isLaunching = true
        errorMessage = nil
        infoMessage = nil
        defer { isLaunching = false }
        do {
            try await terminal.connectLocalReader()
            let intent = try await APIClient.shared.createInPersonCharge(
                gardenID: garden.id,
                amountCents: amountCents,
                memo: memo.trimmingCharacters(in: .whitespacesAndNewlines))
            lastIntent = intent
            _ = try await terminal.collect(clientSecret: intent.clientSecret)
            infoMessage = "Charged $\(String(format: "%.2f", Double(amountCents) / 100))."
            Haptics.success()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
