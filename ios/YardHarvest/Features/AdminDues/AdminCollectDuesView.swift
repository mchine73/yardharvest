import SwiftUI

/// The Tap-to-Pay flow for a single dues record. Walks the manager through
/// reader connect → create PI → tap → process → finalize, with a clear
/// status card at each step.
struct AdminCollectDuesView: View {
    let garden: Garden
    let record: AdminDuesRecord
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var terminal = TerminalManager()
    @State private var pendingIntent: InPersonPaymentIntent?
    @State private var errorMessage: String?
    @State private var infoMessage: String?
    @State private var isLaunching = false

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                summaryCard
                statusCard
                actionButtons
                disclosureCard
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle("Tap to Pay")
        .navigationBarTitleDisplayMode(.inline)
    }

    // MARK: - Sections

    private var summaryCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("MEMBER").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(spacing: 12) {
                    ZStack {
                        Circle().fill(YH.lime)
                        Text(initials(record.userName))
                            .font(.system(size: 16, weight: .bold))
                            .foregroundStyle(YH.ink)
                    }
                    .frame(width: 48, height: 48)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(record.userName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text("\(String(record.seasonYear)) season")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                    Spacer()
                }
                Divider().overlay(YH.border)
                HStack(alignment: .firstTextBaseline) {
                    Text("AMOUNT").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                    Spacer()
                    Text("$\(String(format: "%.2f", record.balance))")
                        .font(.system(size: 32, weight: .bold))
                        .tracking(-0.5)
                        .foregroundStyle(YH.ink)
                }
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
                    Text(statusTitle)
                        .font(.yhTitle3)
                        .foregroundStyle(YH.ink)
                    Text(statusBody)
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    @ViewBuilder
    private var actionButtons: some View {
        if record.isSettled {
            YHCard {
                Label("This record is already settled.",
                      systemImage: "checkmark.seal.fill")
                    .font(.yhBodyMedium).foregroundStyle(YH.ink)
            }
        } else {
            switch terminal.phase {
            case .idle, .canceled, .failed:
                YHButton(title: "Start Tap to Pay",
                         systemImage: "wave.3.right",
                         style: .lime,
                         isLoading: isLaunching) {
                    Task { await begin() }
                }
            case .succeeded:
                YHButton(title: "Done", systemImage: "checkmark", style: .dark) {
                    onChange()
                    dismiss()
                }
            default:
                YHButton(title: "Cancel",
                         systemImage: "xmark",
                         style: .ghost) {
                    terminal.cancelInFlight()
                }
            }
        }
        if let infoMessage {
            Text(infoMessage).font(.yhSubheadline).foregroundStyle(YH.ink)
        }
        if let errorMessage {
            Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
        }
    }

    private var disclosureCard: some View {
        YHCard(padding: YH.Space.md) {
            VStack(alignment: .leading, spacing: 6) {
                Label("Heads-up", systemImage: "info.circle")
                    .font(.yhCaptionMed).foregroundStyle(YH.muted)
                Text("Tap to Pay on iPhone requires an Apple-approved entitlement and the manager's Stripe Connect account must have the card_present capability. In Debug builds the SDK uses a simulated reader so you can walk the flow without real hardware.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }

    // MARK: - Status copy

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
        case .idle:        return "Ready to collect"
        case .discovering: return "Finding reader…"
        case .connecting:  return "Connecting…"
        case .ready:       return "Reader connected"
        case .collecting:  return "Tap card here"
        case .processing:  return "Processing…"
        case .succeeded:   return "Payment received"
        case .canceled:    return "Canceled"
        case .failed:      return "Couldn't collect"
        }
    }

    private var statusBody: String {
        switch terminal.phase {
        case .idle:
            return "Tap Start to walk the customer through paying with their card or Apple Pay phone."
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
            return "Tap Start to try again."
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
        isLaunching = true
        errorMessage = nil
        infoMessage = nil
        defer { isLaunching = false }

        do {
            // 1. Connect the local Tap-to-Pay reader (the iPhone itself, or a
            //    simulated reader in Debug builds).
            try await terminal.connectLocalReader()

            // 2. Ask the backend for an in-person PaymentIntent.
            let intent = try await APIClient.shared.createInPersonDuesPaymentIntent(
                gardenID: garden.id, duesID: record.id)
            pendingIntent = intent

            // 3. Hand the client secret to the SDK → collect → process.
            let pid = try await terminal.collect(clientSecret: intent.clientSecret)

            // 4. Tell the backend to mark the dues record paid.
            let message = try await APIClient.shared.finalizeInPersonDues(
                gardenID: garden.id, duesID: record.id, paymentIntentID: pid)
            infoMessage = message
            Haptics.success()
            onChange()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func initials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.map { String($0.first ?? " ") }.joined().uppercased()
    }
}
