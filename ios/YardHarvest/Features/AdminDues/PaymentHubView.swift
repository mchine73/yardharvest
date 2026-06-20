import SwiftUI

/// Hub for the manager-side payment processing flows. Two big cards:
///   • Collect Dues — pick a member and charge their dues record
///   • New Sale    — ad-hoc terminal for any amount + memo
///
/// Reachable from the Garden tab (manager dashboard) as well as the More tab.
struct PaymentHubView: View {
    let garden: Garden

    // Destination-driven NavigationLinks — each link owns its destination
    // directly rather than going through a shared `Route` value type. This
    // avoids the duplicate-push bug that happens when a pushed view
    // (PaymentHubView is itself a destination of the dashboard) registers
    // its own `.navigationDestination(for:)` on the same `NavigationStack`.

    private var isTapToPaySupported: Bool { TerminalManager.deviceSupportsTapToPay }

    var body: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                heroBand
                if !isTapToPaySupported, let reason = TerminalManager.tapToPayUnavailableReason {
                    unsupportedNotice(reason)
                }
                NavigationLink {
                    AdminDuesListView(garden: garden)
                } label: {
                    HubCard(
                        title: "Collect Dues",
                        subtitle: "Pick a member and charge their annual fee.",
                        icon: "person.crop.circle.badge.checkmark",
                        accent: .lime
                    )
                }
                .buttonStyle(.plain)

                NavigationLink {
                    AdHocChargeView(garden: garden)
                } label: {
                    HubCard(
                        title: "New Sale",
                        subtitle: "Tap-to-Pay for plant starts, deposits, or anything else.",
                        icon: "wave.3.right.circle.fill",
                        accent: .dark
                    )
                }
                .buttonStyle(.plain)

                infoCard
            }
            .padding(YH.Space.md)
        }
        .background(YH.canvas)
        .navigationTitle("Payments")
        .navigationBarTitleDisplayMode(.inline)
    }

    /// Inline notice — shown above the two action cards when the device
    /// can't do Tap to Pay. The cards themselves stay tappable because the
    /// dues view still has value (browsing the roster, marking paid
    /// manually) and so the user understands why Charge would fail later.
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

    private var heroBand: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: 6) {
                Text("TAP TO PAY").font(.yhCaptionMed).tracking(0.8)
                Text("Take payments without a card reader.")
                    .font(.system(size: 22, weight: .bold))
                    .tracking(-0.4)
                Text("Your iPhone becomes the reader. Funds land in your garden's Stripe Connect account, minus the platform fee.")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.ink.opacity(0.75))
                    .padding(.top, 2)
            }
        }
    }

    private var infoCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Label("Where the money goes", systemImage: "building.columns")
                    .font(.yhCaptionMed).foregroundStyle(YH.muted)
                Text("All in-person collections route to your garden's Stripe Connect account. Receipts are visible on the Stripe dashboard; the platform takes a small fee on each transaction.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }
}

/// One of the two big choices on the hub.
private struct HubCard: View {
    let title: String
    let subtitle: String
    let icon: String
    let accent: Accent

    enum Accent { case lime, dark }

    var body: some View {
        HStack(spacing: 14) {
            ZStack {
                RoundedRectangle(cornerRadius: 14)
                    .fill(accent == .lime ? YH.lime : YH.ink)
                Image(systemName: icon)
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundStyle(accent == .lime ? YH.ink : YH.lime)
            }
            .frame(width: 56, height: 56)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.yhTitle3).foregroundStyle(YH.ink)
                Text(subtitle).font(.yhSubheadline).foregroundStyle(YH.muted)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(YH.muted)
        }
        .padding(YH.Space.md)
        .background(YH.canvas)
        .overlay(RoundedRectangle(cornerRadius: YH.Radius.lg)
                    .strokeBorder(YH.border))
        .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg))
    }
}
