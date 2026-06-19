import Foundation

/// `GET /api/gardens/{id}/my-dues` — what the signed-in user owes for this garden.
struct DuesRecord: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let seasonYear: Int
    let amountDue: Double
    let amountPaid: Double
    /// `unpaid`, `partial`, `paid`, `waived`, `comp`.
    let status: String
    let paymentMethod: String?
    let paymentDate: Date?
    let paymentNote: String?

    enum CodingKeys: String, CodingKey {
        case id
        case seasonYear = "season_year"
        case amountDue = "amount_due"
        case amountPaid = "amount_paid"
        case status
        case paymentMethod = "payment_method"
        case paymentDate = "payment_date"
        case paymentNote = "payment_note"
    }

    var balance: Double { max(0, amountDue - amountPaid) }
    var isPaid: Bool { status == "paid" || status == "waived" || status == "comp" }
}

/// `POST /api/gardens/{id}/dues/{did}/pay` — the PaymentIntent (or dev-mode stub).
struct DuesPaymentIntent: Codable, Equatable {
    let clientSecret: String?
    let paymentIntentId: String?
    let publishableKey: String?
    let amount: Int
    let currency: String
    let duesId: Int
    let routedToManager: Bool?
    let devMode: Bool?

    enum CodingKeys: String, CodingKey {
        case clientSecret = "client_secret"
        case paymentIntentId = "payment_intent_id"
        case publishableKey = "publishable_key"
        case amount, currency
        case duesId = "dues_id"
        case routedToManager = "routed_to_manager"
        case devMode = "dev_mode"
    }

    var isDevMode: Bool { devMode == true || clientSecret == nil }
}

/// `POST /api/gardens/{id}/waitlist` — minimal join body.
struct WaitlistJoinResponse: Codable, Equatable {
    let id: Int
    let status: String
    let position: Int
}
