import Foundation

extension APIClient {

    // MARK: - Registration (mobile)

    struct RegisterRequest: Encodable {
        let username: String
        let email: String
        let password: String
        /// Hardcoded to `gardener` from the iOS app — only the website lets
        /// you register as a `manager`.
        let role: String
        let display_name: String
        let address: String
        let city: String
        let state: String
        let zip_code: String
    }

    /// `POST /api/auth/token/register`
    func register(email: String, password: String, displayName: String,
                  username: String, address: String, city: String,
                  state: String, zipCode: String) async throws -> TokenResponse {
        let response: TokenResponse = try await post(
            "/api/auth/token/register",
            body: RegisterRequest(
                username: username,
                email: email,
                password: password,
                role: "gardener",
                display_name: displayName,
                address: address,
                city: city,
                state: state,
                zip_code: zipCode
            ),
            authenticated: false
        )
        KeychainStore.set(response.access_token, for: .accessToken)
        KeychainStore.set(response.refresh_token, for: .refreshToken)
        return response
    }

    // MARK: - Browse / detail

    /// `GET /api/gardens?page=&search=`
    func browseGardens(page: Int = 1, search: String? = nil) async throws -> BrowseGardensPage {
        var query: [String: String] = ["page": String(page)]
        if let search, !search.isEmpty { query["search"] = search }
        return try await get("/api/gardens", query: query, authenticated: false)
    }

    /// `GET /api/gardens/{id}`
    func gardenDetail(gardenID: Int) async throws -> GardenDetail {
        try await get("/api/gardens/\(gardenID)")
    }

    /// `GET /api/gardens/{id}/plots` — public plot list.
    func publicPlots(gardenID: Int) async throws -> [Plot] {
        try await get("/api/gardens/\(gardenID)/plots", authenticated: false)
    }

    /// `GET /api/gardens/{id}/members` — public roster of organizer + plot
    /// holders. Used by the messaging picker to surface peers you can DM.
    func listGardenMembers(gardenID: Int) async throws -> [GardenMember] {
        try await get("/api/gardens/\(gardenID)/members", authenticated: false)
    }

    // MARK: - Reserve / waitlist

    /// `POST /api/gardens/{id}/plots/{pid}/reserve` — returns the now-reserved plot.
    func reservePlot(gardenID: Int, plotID: Int) async throws -> Plot {
        try await post("/api/gardens/\(gardenID)/plots/\(plotID)/reserve")
    }

    struct WaitlistJoinBody: Encodable {
        let plot_size_pref: String?
        let notes: String?
    }

    /// `POST /api/gardens/{id}/waitlist`
    func joinWaitlist(gardenID: Int, sizePref: String?, notes: String?) async throws -> WaitlistJoinResponse {
        try await post("/api/gardens/\(gardenID)/waitlist",
                       body: WaitlistJoinBody(
                        plot_size_pref: sizePref?.isEmpty == false ? sizePref : nil,
                        notes: notes?.isEmpty == false ? notes : nil))
    }

    // MARK: - Dues + payment

    /// `GET /api/gardens/{id}/my-dues`
    func myDues(gardenID: Int) async throws -> [DuesRecord] {
        try await get("/api/gardens/\(gardenID)/my-dues")
    }

    /// `POST /api/gardens/{id}/dues/{did}/pay` — creates a Stripe PaymentIntent
    /// (or returns a dev-mode stub if Stripe isn't configured).
    func payDues(gardenID: Int, duesID: Int) async throws -> DuesPaymentIntent {
        try await post("/api/gardens/\(gardenID)/dues/\(duesID)/pay")
    }

    struct ConfirmPaymentBody: Encodable {
        let payment_intent_id: String
    }
    struct ConfirmPaymentResponse: Decodable {
        let message: String?
    }

    /// `POST /api/gardens/{id}/dues/{did}/confirm-payment`
    func confirmDuesPayment(gardenID: Int, duesID: Int,
                            paymentIntentID: String) async throws -> String {
        let resp: ConfirmPaymentResponse = try await post(
            "/api/gardens/\(gardenID)/dues/\(duesID)/confirm-payment",
            body: ConfirmPaymentBody(payment_intent_id: paymentIntentID))
        return resp.message ?? "Payment confirmed."
    }
}
