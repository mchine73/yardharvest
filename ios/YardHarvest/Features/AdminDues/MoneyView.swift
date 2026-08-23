import SwiftUI

/// "Money" — what Stripe actually did with this garden's payments.
///
/// The Payments hub could take money but never showed any of it back. A
/// Tap-to-Pay sale wrote nothing the app could read, a refund issued from the
/// Stripe dashboard never reached the roster, and the question managers
/// actually ask — *when does this hit my bank* — could only be answered by
/// logging into Stripe. Every row on this screen comes from a webhook, so it
/// reflects what happened to the money rather than what this phone last saw.
struct MoneyView: View {
    let garden: Garden

    @State private var feed: GardenMoneyFeed?
    @State private var payouts: GardenPayoutSummary?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: MoneyFilter = .all

    enum MoneyFilter: String, CaseIterable, Identifiable, Hashable {
        case all, collected, out, deposits

        var id: String { rawValue }
        var label: String {
            switch self {
            case .all:       return "All"
            case .collected: return "Collected"
            case .out:       return "Refunds & disputes"
            case .deposits:  return "Deposits"
            }
        }
        /// Server-side `kind` filter. `nil` means don't filter.
        var kinds: String? {
            switch self {
            case .all:       return nil
            case .collected: return "payment,payment_failed"
            case .out:       return "refund,dispute"
            case .deposits:  return "payout"
            }
        }
    }

    private var events: [GardenMoneyEvent] { feed?.events ?? [] }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: events.isEmpty && feed == nil,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 5, skeletonRows: 2) {
            emptyState
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.md) {
                    if let status = feed?.stripeStatus, status.needsAttention {
                        StripeStatusBanner(status: status)
                    }
                    if let totals = feed?.totals { moneyBento(totals) }
                    if let payouts { payoutCard(payouts) }

                    YHFilterChips(selection: $filter,
                                  options: MoneyFilter.allCases,
                                  label: { $0.label })

                    if events.isEmpty {
                        emptyState.frame(minHeight: 200)
                    } else {
                        YHCard {
                            VStack(spacing: 0) {
                                ForEach(events) { event in
                                    MoneyRow(event: event)
                                    if event.id != events.last?.id {
                                        Divider().overlay(YH.border).padding(.vertical, 10)
                                    }
                                }
                            }
                        }
                    }
                    windowNote
                }
                .padding(YH.Space.md)
                .padding(.bottom, YH.Space.xl)
            }
        }
        .background(YH.canvas)
        .navigationTitle("Money")
        .navigationBarTitleDisplayMode(.inline)
        // One task keyed on both inputs: two separate `.task(id:)` modifiers
        // would each fire on first appear and race to set `feed`.
        .task(id: FeedKey(garden: garden.id, filter: filter)) { await load() }
        .refreshable { await load(showSpinner: false, refreshPayouts: true) }
    }

    // MARK: - Pieces

    private var emptyState: some View {
        YHEmpty(systemImage: "creditcard",
                title: "No card activity yet",
                message: "Dues paid online and anything you collect with Tap "
                       + "to Pay will show up here, along with your bank deposits.")
    }

    private func moneyBento(_ totals: GardenMoneyTotals) -> some View {
        VStack(spacing: YH.Space.sm) {
            HStack(spacing: YH.Space.sm) {
                YHStatTile(label: "Collected",
                           value: money(totals.collected),
                           detail: countDetail(totals.paymentCount),
                           systemImage: "arrow.down.circle.fill")
                YHStatTile(label: "You keep",
                           value: money(totals.kept),
                           detail: keptDetail(totals),
                           systemImage: "leaf.fill")
            }
            if totals.refunded > 0 || totals.disputed > 0 {
                HStack(spacing: YH.Space.sm) {
                    YHStatTile(label: "Refunded",
                               value: money(totals.refunded),
                               detail: "returned to payers",
                               systemImage: "arrow.uturn.backward")
                    YHStatTile(label: "Disputed",
                               value: money(totals.disputed),
                               detail: "held by Stripe",
                               systemImage: "exclamationmark.shield")
                }
            }
        }
    }

    private func payoutCard(_ summary: GardenPayoutSummary) -> some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.xs) {
                YHSectionHeader(title: "To your bank",
                                systemImage: "building.columns",
                                trailing: money(summary.paidTotal))
                if let last = summary.lastPayoutAt {
                    Text("Last deposit \(money(summary.lastPayoutAmount)) "
                         + last.formatted(.relative(presentation: .named)))
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                } else {
                    Text("No deposits yet in this window. Stripe pays out on "
                         + "its own schedule once your account is verified.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
                if summary.failedCount > 0 {
                    YHPill(text: summary.failedCount == 1 ? "1 failed payout"
                                                          : "\(summary.failedCount) failed payouts",
                           systemImage: "exclamationmark.triangle.fill",
                           tint: YH.danger)
                }
                // Payouts belong to the Stripe account, not this garden. Say so
                // rather than letting a manager reconcile them against one
                // garden's collections and come up short.
                Text("Deposits cover everything on your Stripe account, which "
                     + "may include your other gardens.")
                    .font(.yhCaption).foregroundStyle(.tertiary)
            }
        }
    }

    private var windowNote: some View {
        Text("Showing the last \(feed?.windowDays ?? 90) days.")
            .font(.yhCaption)
            .foregroundStyle(.tertiary)
            .frame(maxWidth: .infinity)
    }

    // MARK: - Formatting

    private func money(_ value: Double) -> String {
        value.formatted(.currency(code: "USD")
            .precision(.fractionLength(value < 100 ? 2 : 0)))
    }

    private func countDetail(_ count: Int) -> String {
        count == 1 ? "1 payment" : "\(count) payments"
    }

    private func keptDetail(_ totals: GardenMoneyTotals) -> String {
        totals.fees > 0 ? "after \(money(totals.fees)) in fees" : "after fees"
    }

    // MARK: - Loading

    /// Identity for the feed task — changing either the garden or the filter
    /// re-runs it; nothing else does.
    private struct FeedKey: Equatable {
        let garden: Int
        let filter: MoneyFilter
    }

    private func load(showSpinner: Bool = true, refreshPayouts: Bool = false) async {
        await loadFeed(showSpinner: showSpinner)
        // Payouts are account-level and don't change with the filter, so they
        // are fetched once per screen rather than on every chip tap.
        if payouts == nil || refreshPayouts {
            payouts = try? await APIClient.shared.gardenPayouts(gardenID: garden.id)
        }
    }

    private func loadFeed(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do {
            feed = try await APIClient.shared.gardenMoneyFeed(gardenID: garden.id,
                                                              kind: filter.kinds)
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

// MARK: - Rows

/// One money event. The label is rendered by the server so the same wording
/// appears here, on the web finance tab, and in the push notification.
private struct MoneyRow: View {
    let event: GardenMoneyEvent

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 10)
                    .fill(tint.opacity(0.14))
                Image(systemName: event.systemImage)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(tint)
            }
            .frame(width: 34, height: 34)

            VStack(alignment: .leading, spacing: 2) {
                Text(event.label)
                    .font(.yhBodyMedium).foregroundStyle(YH.ink)
                HStack(spacing: 6) {
                    if let when = event.occurredAt {
                        Text(when.formatted(date: .abbreviated, time: .shortened))
                    }
                    if event.scope == "account" {
                        Text("· account-wide")
                    }
                }
                .font(.yhCaption).foregroundStyle(YH.muted)
                if let detail = event.description, !detail.isEmpty {
                    Text(detail).font(.yhCaption).foregroundStyle(.tertiary)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 8)

            if event.kind != "account" {
                Text(amountText)
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(event.isOutgoing ? YH.danger : YH.ink)
                    .monospacedDigit()
            }
        }
    }

    private var amountText: String {
        let value = event.amount.formatted(.currency(code: event.currency?.uppercased() ?? "USD")
            .precision(.fractionLength(2)))
        return event.isOutgoing ? "-\(value)" : value
    }

    private var tint: Color {
        if event.isTrouble { return YH.danger }
        if event.kind == "payout" { return YH.success }
        return YH.ink
    }
}

/// Shown whenever Stripe says the connected account can't fully do its job.
/// Deliberately loud: the alternative is finding out when a tap fails in
/// front of a member.
struct StripeStatusBanner: View {
    let status: GardenStripeStatus
    var compact: Bool = false

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(alignment: .top, spacing: 12) {
                    Image(systemName: icon)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(tint)
                        .frame(width: 32, height: 32)
                        .background(tint.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(title).font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text(status.message).font(.yhCaption).foregroundStyle(YH.muted)
                    }
                    Spacer()
                }
                if !compact, !status.requirementsDue.isEmpty {
                    Text("Stripe still needs: "
                         + status.requirementsDue.prefix(3)
                            .map(Self.humanize).joined(separator: ", "))
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
                if !compact, let urlString = status.dashboardUrl,
                   let url = URL(string: urlString) {
                    Link(destination: url) {
                        Text("Open Stripe")
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14).padding(.vertical, 7)
                            .foregroundStyle(YH.lime)
                            .background(YH.ink)
                            .clipShape(Capsule())
                    }
                }
            }
        }
    }

    private var title: String {
        switch status.state {
        case "restricted":   return "Stripe paused your payouts"
        case "not_started":  return "No payout account yet"
        default:             return "Stripe needs more information"
        }
    }

    private var icon: String {
        status.state == "not_started" ? "building.columns" : "exclamationmark.triangle.fill"
    }

    private var tint: Color {
        status.state == "restricted" ? YH.danger : YH.warning
    }

    /// `individual.verification.document` -> `Individual verification document`
    static func humanize(_ requirement: String) -> String {
        let words = requirement.replacingOccurrences(of: ".", with: " ")
            .replacingOccurrences(of: "_", with: " ")
        return words.prefix(1).uppercased() + words.dropFirst()
    }
}
