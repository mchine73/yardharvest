import Foundation

/// Manager-side dues record from `GET /api/garden-admin/{id}/dues`.
struct AdminDuesRecord: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let userId: Int
    let userName: String
    let seasonYear: Int
    let amountDue: Double
    let amountPaid: Double
    /// `unpaid`, `partial`, `paid`, `waived`, `comp`.
    let status: String
    let paymentMethod: String?
    let paymentDate: Date?
    let paymentNote: String?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case userId = "user_id"
        case userName = "user_name"
        case seasonYear = "season_year"
        case amountDue = "amount_due"
        case amountPaid = "amount_paid"
        case status
        case paymentMethod = "payment_method"
        case paymentDate = "payment_date"
        case paymentNote = "payment_note"
        case createdAt = "created_at"
    }

    var balance: Double { max(0, amountDue - amountPaid) }
    var isSettled: Bool { status == "paid" || status == "waived" || status == "comp" }
}

/// `POST /api/garden-admin/{id}/dues/{did}/collect-in-person` response — the
/// PaymentIntent the iOS Stripe Terminal SDK consumes to drive the Tap to Pay
/// UX.
struct InPersonPaymentIntent: Codable, Equatable {
    let clientSecret: String
    let paymentIntentId: String
    let amount: Int
    let currency: String
    /// Only present on the dues flow. An ad-hoc sale has no dues record, so
    /// this must stay optional — the two endpoints share this type, and a
    /// required key here made every "New Sale" fail to decode.
    let duesId: Int?
    let connectedAccountId: String?

    enum CodingKeys: String, CodingKey {
        case clientSecret = "client_secret"
        case paymentIntentId = "payment_intent_id"
        case amount, currency
        case duesId = "dues_id"
        case connectedAccountId = "connected_account_id"
    }
}

/// `POST /api/garden-admin/terminal/connection_token` response.
struct TerminalConnectionToken: Codable, Equatable {
    let secret: String
    /// Stripe Terminal Location the device registers itself against. Issued by
    /// the backend from the manager's own Connect account.
    let locationID: String?

    enum CodingKeys: String, CodingKey {
        case secret
        case locationID = "location_id"
    }
}
