import Foundation

/// `resource_to_dict()` in `app/api/gardens_api.py`.
struct GardenResource: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let name: String
    let resourceType: String?
    let description: String?
    let quantity: Int?
    let condition: String?
    let checkedOutToId: Int?
    let checkedOutToName: String?
    let checkedOutAt: Date?
    let checkoutDurationDays: Int?
    let dueDate: Date?
    let isOverdue: Bool
    let outOfService: Bool
    let serviceNote: String?
    /// `available`, `checked_out`, `overdue`, `out_of_service`.
    let status: String
    /// Opaque token printed onto QR codes — accepted by
    /// `GET /api/gardens/resources/lookup?token=…`. The backend mints one
    /// on resource creation and lazy-fills for legacy rows.
    let qrCodeToken: String?
    /// Full scannable URL the QR code should encode. Encoding the URL
    /// (rather than the raw token) lets iOS Camera + universal links
    /// route directly into YardHarvest, while our own scanner still
    /// resolves via the same lookup endpoint.
    let qrCodeURL: String?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case name
        case resourceType = "resource_type"
        case description
        case quantity
        case condition
        case checkedOutToId = "checked_out_to_id"
        case checkedOutToName = "checked_out_to_name"
        case checkedOutAt = "checked_out_at"
        case checkoutDurationDays = "checkout_duration_days"
        case dueDate = "due_date"
        case isOverdue = "is_overdue"
        case outOfService = "out_of_service"
        case serviceNote = "service_note"
        case status
        case qrCodeToken = "qr_code_token"
        case qrCodeURL = "qr_code_url"
    }

    var isAvailable: Bool { status == "available" }
    var isCheckedOut: Bool { status == "checked_out" || status == "overdue" }
}

/// Response of `GET /api/gardens/resources/lookup?token=...` — QR scan result.
struct ResourceLookup: Codable, Equatable {
    let gardenId: Int
    let gardenName: String
    let resourceId: Int
    let resource: GardenResource

    enum CodingKeys: String, CodingKey {
        case gardenId = "garden_id"
        case gardenName = "garden_name"
        case resourceId = "resource_id"
        case resource
    }
}
