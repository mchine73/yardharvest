import Foundation

extension APIClient {

    // MARK: - Admin dues list

    /// `GET /api/garden-admin/{id}/dues?status=&season_year=`
    func adminListDues(gardenID: Int, status: String? = nil) async throws -> [AdminDuesRecord] {
        var query: [String: String] = [:]
        if let status, status != "all" { query["status"] = status }
        return try await get("/api/garden-admin/\(gardenID)/dues", query: query)
    }

    // MARK: - Tap to Pay

    /// `POST /api/garden-admin/terminal/connection_token`
    func terminalConnectionToken(gardenID: Int? = nil) async throws -> String {
        try await terminalSession(gardenID: gardenID).secret
    }

    struct TerminalSessionBody: Encodable { let garden_id: Int }

    /// Full Terminal session payload — the connection-token secret plus the
    /// Location the reader must register to. With a gardenID the backend
    /// scopes both to that garden's payout account, gated by the MONEY role
    /// capability — how a co-organizer or treasurer takes payment. Without
    /// one it falls back to the signed-in user's own account (organizer-only
    /// behavior, kept for compatibility).
    func terminalSession(gardenID: Int? = nil) async throws -> TerminalConnectionToken {
        if let gardenID {
            return try await post("/api/garden-admin/terminal/connection_token",
                                  body: TerminalSessionBody(garden_id: gardenID))
        }
        return try await post("/api/garden-admin/terminal/connection_token")
    }

    /// `POST /api/garden-admin/{id}/dues/{did}/collect-in-person`
    func createInPersonDuesPaymentIntent(gardenID: Int, duesID: Int) async throws -> InPersonPaymentIntent {
        try await post("/api/garden-admin/\(gardenID)/dues/\(duesID)/collect-in-person")
    }

    struct FinalizeInPersonBody: Encodable {
        let payment_intent_id: String
    }
    struct FinalizeInPersonResponse: Decodable {
        let message: String?
        let duesStatus: String?
        enum CodingKeys: String, CodingKey {
            case message
            case duesStatus = "dues_status"
        }
    }

    /// `POST /api/garden-admin/{id}/dues/{did}/finalize-in-person`
    @discardableResult
    func finalizeInPersonDues(gardenID: Int, duesID: Int,
                              paymentIntentID: String) async throws -> String {
        let resp: FinalizeInPersonResponse = try await post(
            "/api/garden-admin/\(gardenID)/dues/\(duesID)/finalize-in-person",
            body: FinalizeInPersonBody(payment_intent_id: paymentIntentID))
        return resp.message ?? "Dues marked paid."
    }

    // MARK: - Ad-hoc in-person charge (sales, day passes, etc.)

    struct AdHocChargeBody: Encodable {
        let amount_cents: Int
        let memo: String?
    }

    /// `POST /api/garden-admin/{id}/in-person-charge` — ad-hoc Tap-to-Pay
    /// for any amount + memo. Not tied to a dues record; the Stripe Connect
    /// dashboard is the system of record.
    func createInPersonCharge(gardenID: Int,
                              amountCents: Int,
                              memo: String?) async throws -> InPersonPaymentIntent {
        try await post("/api/garden-admin/\(gardenID)/in-person-charge",
                       body: AdHocChargeBody(
                            amount_cents: amountCents,
                            memo: memo?.isEmpty == false ? memo : nil))
    }
}
