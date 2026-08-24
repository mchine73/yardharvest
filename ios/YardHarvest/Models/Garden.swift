import Foundation

/// `garden_to_dict()` in `app/api/gardens_api.py`.
struct Garden: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let publicId: String?
    let name: String
    let slug: String?
    let description: String?
    let address: String?
    let city: String?
    let state: String?
    let zipCode: String?
    let photoUrl: String?
    let totalPlots: Int?
    let plotFeeAnnual: Double?
    let operatingModel: String?
    let isActive: Bool
    let maxCheckoutsPerMember: Int?
    let latitude: Double?
    let longitude: Double?
    let weatherAlertsEnabled: Bool?
    let gridRows: Int?
    let gridCols: Int?
    let organizerId: Int?
    let organizerName: String?
    /// This viewer's role and capabilities in the garden — from
    /// garden_permissions.py via my-gardens / garden detail. Nil on payloads
    /// that predate roles (cached responses, older endpoints).
    let userGardenRole: String?
    let userCapabilities: [String]?

    enum CodingKeys: String, CodingKey {
        case id
        case publicId = "public_id"
        case name, slug, description, address, city, state
        case zipCode = "zip_code"
        case photoUrl = "photo_url"
        case totalPlots = "total_plots"
        case plotFeeAnnual = "plot_fee_annual"
        case operatingModel = "operating_model"
        case isActive = "is_active"
        case maxCheckoutsPerMember = "max_checkouts_per_member"
        case latitude, longitude
        case weatherAlertsEnabled = "weather_alerts_enabled"
        case gridRows = "grid_rows"
        case gridCols = "grid_cols"
        case organizerId = "organizer_id"
        case organizerName = "organizer_name"
        case userGardenRole = "user_garden_role"
        case userCapabilities = "user_capabilities"
    }

    /// Capability check mirroring the backend's `can()`. Capabilities come
    /// down with my-gardens; an absent list means no admin powers.
    func can(_ capability: String) -> Bool {
        userCapabilities?.contains(capability) ?? false
    }
}

/// `GET /api/gardens/my-gardens`.
struct MyGardensPayload: Codable, Equatable {
    let organized: [Garden]
    /// Gardens where I hold an assigned admin role (co-organizer, treasurer,
    /// volunteer lead) without being the organizer. Optional so cached
    /// pre-roles payloads still decode.
    let helping: [Garden]?
    let plotHolder: [Garden]
    let waitlisted: [Garden]

    enum CodingKeys: String, CodingKey {
        case organized, helping
        case plotHolder = "plot_holder"
        case waitlisted
    }

    var all: [Garden] { organized + (helping ?? []) + plotHolder + waitlisted }
}
