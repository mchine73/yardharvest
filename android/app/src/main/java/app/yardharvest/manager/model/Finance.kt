package app.yardharvest.manager.model

import app.yardharvest.manager.core.TimestampSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

/**
 * One money event Stripe reported for a garden, from
 * `GET /api/garden-admin/{id}/finance/activity`. Fed entirely by the Stripe
 * webhooks, not by anything this app posts — so a Tap to Pay sale shows up
 * here whether or not the phone stayed online afterwards.
 */
@Serializable
data class GardenMoneyEvent(
    val id: Int,
    /** `payment`, `payment_failed`, `refund`, `dispute`, `payout`, `account`. */
    val kind: String,
    /** `dues_online`, `dues_in_person`, `in_person_sale`, `stripe`. */
    val source: String? = null,
    val status: String? = null,
    /** `garden` for money this garden took, `account` for account-level rows. */
    val scope: String = "garden",
    /** Server-rendered one-liner, shown as-is everywhere. */
    val label: String = "",
    val amount: Double = 0.0,
    val fee: Double = 0.0,
    /** Null when Stripe's fee hasn't been looked up yet. */
    @SerialName("stripe_fee") val stripeFee: Double? = null,
    val net: Double = 0.0,
    val currency: String? = null,
    val description: String? = null,
    val counterparty: String? = null,
    @SerialName("dues_id") val duesId: Int? = null,
    @SerialName("stripe_object_id") val stripeObjectId: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("occurred_at") val occurredAt: Instant? = null,
) {
    /** Money leaving is drawn in red and signed. Payouts are transfers, not income. */
    val isOutgoing: Boolean get() = kind == "refund" || (kind == "dispute" && status != "won")

    val isTrouble: Boolean
        get() = (kind == "dispute" && status != "won") ||
            kind == "payment_failed" ||
            (kind == "payout" && status == "failed") ||
            (kind == "account" && status != "ok")
}

/** Stripe-observed money for one garden over the requested window. */
@Serializable
data class GardenMoneyTotals(
    val collected: Double = 0.0,
    /** YardHarvest's application fee. */
    val fees: Double = 0.0,
    /** What Stripe itself charged, read from the balance transaction. */
    @SerialName("stripe_fees") val stripeFees: Double = 0.0,
    val net: Double = 0.0,
    val refunded: Double = 0.0,
    val disputed: Double = 0.0,
    /** What the garden keeps. An upper bound while [feesComplete] is false. */
    val kept: Double = 0.0,
    @SerialName("payment_count") val paymentCount: Int = 0,
    @SerialName("failed_count") val failedCount: Int = 0,
    @SerialName("unknown_fee_count") val unknownFeeCount: Int = 0,
    @SerialName("fees_complete") val feesComplete: Boolean = true,
    @SerialName("by_source") val bySource: Map<String, Double> = emptyMap(),
    @SerialName("has_platform_fee") val hasPlatformFee: Boolean? = null,
) {
    val showsPlatformFee: Boolean get() = hasPlatformFee ?: (fees > 0)
}

/**
 * What Stripe is holding for the connected account right now.
 * **These are CENTS**, unlike every other money figure in the finance API.
 */
@Serializable
data class GardenStripeBalance(
    /** Cleared, awaiting the next payout. Can be negative. */
    val available: Int = 0,
    /** Still settling. */
    val pending: Int = 0,
    val currency: String? = null,
) {
    val total: Int get() = available + pending
}

/** When Stripe pays this account out, in Stripe's own words. */
@Serializable
data class GardenPayoutSchedule(
    /** `daily`, `weekly`, `monthly`, `manual`, or `unknown`. */
    val interval: String? = null,
    @SerialName("delay_days") val delayDays: Int? = null,
    /** Server-rendered sentence, shown verbatim. */
    val description: String? = null,
)

/** Whether this garden can take money, and whether it can reach a bank. */
@Serializable
data class GardenStripeStatus(
    /** `ok`, `action_needed`, `restricted`, `not_started`. */
    val state: String = "not_started",
    val message: String = "",
    val ok: Boolean = false,
    @SerialName("charges_enabled") val chargesEnabled: Boolean = false,
    @SerialName("payouts_enabled") val payoutsEnabled: Boolean = false,
    @SerialName("disabled_reason") val disabledReason: String? = null,
    @SerialName("requirements_due") val requirementsDue: List<String> = emptyList(),
    @SerialName("account_id") val accountId: String? = null,
    /** Null means no `account.updated` webhook has ever arrived. */
    @Serializable(TimestampSerializer::class) @SerialName("synced_at") val syncedAt: Instant? = null,
    @SerialName("dashboard_url") val dashboardUrl: String? = null,
    @SerialName("billing_path") val billingPath: String? = null,
    @SerialName("stripe_configured") val stripeConfigured: Boolean? = null,
) {
    val needsAttention: Boolean get() = !ok
}

/** `GET /api/garden-admin/{id}/finance/activity` */
@Serializable
data class GardenMoneyFeed(
    val events: List<GardenMoneyEvent> = emptyList(),
    @SerialName("window_days") val windowDays: Int = 90,
    val count: Int = 0,
    val totals: GardenMoneyTotals = GardenMoneyTotals(),
    @SerialName("stripe_status") val stripeStatus: GardenStripeStatus = GardenStripeStatus(),
)

/** `GET /api/garden-admin/{id}/finance/payouts` — deposits to the manager's bank. */
@Serializable
data class GardenPayoutSummary(
    @SerialName("window_days") val windowDays: Int = 90,
    @SerialName("paid_total") val paidTotal: Double = 0.0,
    @SerialName("paid_count") val paidCount: Int = 0,
    @Serializable(TimestampSerializer::class) @SerialName("last_payout_at") val lastPayoutAt: Instant? = null,
    @SerialName("last_payout_amount") val lastPayoutAmount: Double = 0.0,
    @SerialName("failed_count") val failedCount: Int = 0,
    val payouts: List<GardenMoneyEvent> = emptyList(),
    /** Stripe's own count of what it holds; null when Stripe was unreachable. */
    val balance: GardenStripeBalance? = null,
    val schedule: GardenPayoutSchedule? = null,
)
