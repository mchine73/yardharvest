import Foundation

/// One money event Stripe reported for a garden.
///
/// These come from `GET /api/garden-admin/{id}/finance/activity`, which is
/// fed entirely by the Stripe webhooks — not by anything this app posts. That
/// matters for Tap to Pay in particular: a sale collected at the plot gate
/// shows up here whether or not the phone stayed on the network afterwards.
struct GardenMoneyEvent: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    /// `payment`, `payment_failed`, `refund`, `dispute`, `payout`, `account`.
    let kind: String
    /// `dues_online`, `dues_in_person`, `in_person_sale`, `stripe`.
    let source: String?
    let status: String?
    /// `garden` for money this garden took, `account` for bank deposits and
    /// account-status rows, which belong to the whole Stripe account.
    let scope: String
    /// Server-rendered one-liner. Rendered as-is so the phrasing stays the
    /// same here, on the web, and in notifications.
    let label: String
    let amount: Double
    let fee: Double
    /// `nil` when Stripe's fee for this payment hasn't been looked up yet.
    let stripeFee: Double?
    let net: Double
    let currency: String?
    let description: String?
    let counterparty: String?
    let duesId: Int?
    let stripeObjectId: String?
    let occurredAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, kind, source, status, scope, label, amount, fee, net, currency
        case description, counterparty
        case stripeFee = "stripe_fee"
        case duesId = "dues_id"
        case stripeObjectId = "stripe_object_id"
        case occurredAt = "occurred_at"
    }

    /// Money leaving is drawn in red and signed; everything else reads as
    /// neutral. Payouts are a transfer, not income, so they stay unsigned.
    var isOutgoing: Bool {
        kind == "refund" || (kind == "dispute" && status != "won")
    }

    var isTrouble: Bool {
        kind == "dispute" && status != "won"
            || kind == "payment_failed"
            || (kind == "payout" && status == "failed")
            || (kind == "account" && status != "ok")
    }

    var systemImage: String {
        switch kind {
        case "payment":        return source == "dues_online" ? "globe" : "wave.3.right"
        case "payment_failed": return "xmark.circle"
        case "refund":         return "arrow.uturn.backward"
        case "dispute":        return "exclamationmark.shield"
        case "payout":         return status == "failed" ? "building.columns.circle" : "building.columns"
        default:               return "person.badge.shield.checkmark"
        }
    }
}

/// Stripe-observed money for one garden over the requested window.
struct GardenMoneyTotals: Codable, Equatable {
    let collected: Double
    /// YardHarvest's application fee.
    let fees: Double
    /// What Stripe itself charged, read from the connected account's balance
    /// transaction rather than assumed.
    let stripeFees: Double
    let net: Double
    let refunded: Double
    let disputed: Double
    /// Net of both fees, less anything given back — what the garden keeps.
    /// An *upper bound* while `feesComplete` is false.
    let kept: Double
    let paymentCount: Int
    let failedCount: Int
    /// Payments whose Stripe fee hasn't been looked up yet.
    let unknownFeeCount: Int
    let feesComplete: Bool
    let bySource: [String: Double]
    /// The server's own answer to "is there a platform fee to show". Optional
    /// for payloads that predate the flag; `fees > 0` is the same rule.
    let hasPlatformFee: Bool?

    enum CodingKeys: String, CodingKey {
        case collected, fees, net, refunded, disputed, kept
        case stripeFees = "stripe_fees"
        case paymentCount = "payment_count"
        case failedCount = "failed_count"
        case unknownFeeCount = "unknown_fee_count"
        case feesComplete = "fees_complete"
        case bySource = "by_source"
        case hasPlatformFee = "has_platform_fee"
    }

    var showsPlatformFee: Bool { hasPlatformFee ?? (fees > 0) }
}

/// What Stripe is holding for the connected account right now.
///
/// **These are CENTS**, unlike every other money figure in the finance API,
/// which arrives pre-divided as dollars. They come straight off
/// `stripe.Balance.retrieve` and are passed through unconverted, so render
/// them with `money(cents:)` and never the dollar formatter.
struct GardenStripeBalance: Codable, Equatable {
    /// Cleared and waiting for the next scheduled payout. Can be NEGATIVE
    /// when a refund or fee landed before there were cleared funds.
    let available: Int
    /// Still settling.
    let pending: Int
    let currency: String?

    /// Everything Stripe holds, cleared or not.
    var total: Int { available + pending }
}

/// When Stripe pays this account out, in Stripe's own words.
struct GardenPayoutSchedule: Codable, Equatable {
    /// `daily`, `weekly`, `monthly`, `manual`, or `unknown`.
    let interval: String?
    let delayDays: Int?
    /// Server-rendered sentence — shown verbatim so the app, the web and
    /// Stripe's dashboard all describe the schedule the same way.
    let description: String?

    enum CodingKeys: String, CodingKey {
        case interval, description
        case delayDays = "delay_days"
    }
}

/// Whether this garden can take money, and whether that money can reach a bank.
///
/// Mirrored from the `account.updated` webhook, so it is Stripe's own view of
/// the connected account rather than a memory of onboarding having finished.
struct GardenStripeStatus: Codable, Equatable {
    /// `ok`, `action_needed`, `restricted`, `not_started`.
    let state: String
    let message: String
    let ok: Bool
    let chargesEnabled: Bool
    let payoutsEnabled: Bool
    let disabledReason: String?
    let requirementsDue: [String]
    let accountId: String?
    /// `nil` means no `account.updated` has ever reached the backend — which
    /// usually means the Connect webhook endpoint isn't configured, so the UI
    /// says "not synced" rather than implying everything is fine.
    let syncedAt: Date?
    // Present only on the dedicated status endpoint.
    let dashboardUrl: String?
    let billingPath: String?
    let stripeConfigured: Bool?

    enum CodingKeys: String, CodingKey {
        case state, message, ok
        case chargesEnabled = "charges_enabled"
        case payoutsEnabled = "payouts_enabled"
        case disabledReason = "disabled_reason"
        case requirementsDue = "requirements_due"
        case accountId = "account_id"
        case syncedAt = "synced_at"
        case dashboardUrl = "dashboard_url"
        case billingPath = "billing_path"
        case stripeConfigured = "stripe_configured"
    }

    var needsAttention: Bool { !ok }
}

/// `GET /api/garden-admin/{id}/finance/activity`
struct GardenMoneyFeed: Codable, Equatable {
    let events: [GardenMoneyEvent]
    let windowDays: Int
    let count: Int
    let totals: GardenMoneyTotals
    let stripeStatus: GardenStripeStatus

    enum CodingKeys: String, CodingKey {
        case events, count, totals
        case windowDays = "window_days"
        case stripeStatus = "stripe_status"
    }
}

/// `GET /api/garden-admin/{id}/finance/payouts` — deposits to the manager's
/// bank. Account-level: a payout can cover more than one garden, so it is
/// never folded into a single garden's totals.
struct GardenPayoutSummary: Codable, Equatable {
    let windowDays: Int
    let paidTotal: Double
    let paidCount: Int
    let lastPayoutAt: Date?
    let lastPayoutAmount: Double
    let failedCount: Int
    let payouts: [GardenMoneyEvent]
    /// Stripe's own count of what it holds — authoritative, and complete in a
    /// way the ledger above cannot be: the ledger only knows about payments
    /// whose webhooks arrived. `nil` when Stripe was unreachable.
    let balance: GardenStripeBalance?
    let schedule: GardenPayoutSchedule?

    enum CodingKeys: String, CodingKey {
        case payouts, balance, schedule
        case windowDays = "window_days"
        case paidTotal = "paid_total"
        case paidCount = "paid_count"
        case lastPayoutAt = "last_payout_at"
        case lastPayoutAmount = "last_payout_amount"
        case failedCount = "failed_count"
    }
}
