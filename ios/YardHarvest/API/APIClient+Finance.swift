import Foundation

/// Manager-side money endpoints. Everything here is read-only and comes from
/// what the Stripe webhooks recorded, so the screens load without waiting on
/// a Stripe round-trip.
extension APIClient {

    /// `GET /api/garden-admin/{id}/finance/activity`
    ///
    /// - Parameter kind: comma-separated ledger kinds to filter to
    ///   (`payment`, `refund`, `dispute`, `payout`, ...). Omit for everything.
    func gardenMoneyFeed(gardenID: Int,
                         days: Int = 90,
                         kind: String? = nil,
                         limit: Int = 60) async throws -> GardenMoneyFeed {
        var query = ["days": String(days), "limit": String(limit)]
        if let kind, !kind.isEmpty { query["kind"] = kind }
        return try await get("/api/garden-admin/\(gardenID)/finance/activity", query: query)
    }

    /// `GET /api/garden-admin/{id}/finance/payouts`
    func gardenPayouts(gardenID: Int, days: Int = 90) async throws -> GardenPayoutSummary {
        try await get("/api/garden-admin/\(gardenID)/finance/payouts",
                      query: ["days": String(days)])
    }

    /// `GET /api/garden-admin/{id}/finance/stripe-status`
    ///
    /// Includes an Express dashboard link only when something is wrong — that
    /// is the one time the manager needs to go to Stripe, and fetching it is
    /// the only part of this call that touches Stripe's API.
    func gardenStripeStatus(gardenID: Int) async throws -> GardenStripeStatus {
        try await get("/api/garden-admin/\(gardenID)/finance/stripe-status")
    }
}
