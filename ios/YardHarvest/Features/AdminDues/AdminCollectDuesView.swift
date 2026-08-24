import SwiftUI

/// The Tap-to-Pay flow for a single dues record.
///
/// The reader connects in the background as soon as the screen appears, so
/// the manager sees one Charge button and then Apple's card sheet. Discovery
/// and connection are plumbing — the operator's phone *is* the reader, and
/// narrating that just makes a payment feel like hardware setup.
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
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle("Tap to Pay")
        .navigationBarTitleDisplayMode(.inline)
        .task { await terminal.prepare(gardenID: garden.id) }
    }

    // MARK: - Sections

    private var summaryCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Text("MEMBER").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(spacing: 12) {
                    YHAvatar(name: record.userName, size: 48)
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
        } else if !TerminalManager.deviceSupportsTapToPay {
            YHCard {
                VStack(alignment: .leading, spacing: 6) {
                    Label("Tap to Pay isn't available",
                          systemImage: "iphone.slash")
                        .font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Text(TerminalManager.tapToPayUnavailableReason ?? "")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                    Text("Record the payment manually on the website instead.")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                        .padding(.top, 2)
                }
            }
        } else {
            switch terminal.phase {
            case .idle, .canceled, .failed, .discovering, .connecting, .ready:
                YHButton(title: "Charge $\(String(format: "%.2f", record.balance))",
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
        case .idle, .discovering, .connecting, .ready:
            return "Ready to charge"
        case .collecting:  return "Tap card here"
        case .processing:  return "Processing…"
        case .succeeded:   return "Payment received"
        case .canceled:    return "Canceled"
        case .failed:      return "Couldn't collect"
        }
    }

    private var statusBody: String {
        switch terminal.phase {
        case .idle, .discovering, .connecting, .ready:
            return "They can pay with a card, Apple Pay, or Google Pay."
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
        case .idle, .discovering, .connecting, .ready:
            return "wave.3.right"
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

}
