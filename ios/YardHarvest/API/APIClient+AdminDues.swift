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
    func terminalConnectionToken() async throws -> String {
        let resp: TerminalConnectionToken = try await post("/api/garden-admin/terminal/connection_token")
        return resp.secret
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
}
