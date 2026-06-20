import Foundation

/// Plot shape from `app/api/garden_admin_api.py:admin_list_plots` and
/// `plot_to_dict()` in `gardens_api.py`.
struct Plot: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let plotNumber: String
    let size: String?
    let locationNotes: String?
    /// `assigned`, `available`, `maintenance`, `reserved`.
    let status: String
    let assignedToId: Int?
    let assignedToName: String?
    let assignedToEmail: String?
    let assignedDate: Date?
    let renewalDate: Date?
    let reservedById: Int?
    let reservedByName: String?
    let reservedAt: Date?
    let harvestTotalLbs: Double?
    let harvestCount: Int?
    let gridRow: Int?
    let gridCol: Int?
    let customName: String?
    let soilType: String?
    let sunExposure: String?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case plotNumber = "plot_number"
        case size
        case locationNotes = "location_notes"
        case status
        case assignedToId = "assigned_to_id"
        case assignedToName = "assigned_to_name"
        case assignedToEmail = "assigned_to_email"
        case assignedDate = "assigned_date"
        case renewalDate = "renewal_date"
        case reservedById = "reserved_by_id"
        case reservedByName = "reserved_by_name"
        case reservedAt = "reserved_at"
        case harvestTotalLbs = "harvest_total_lbs"
        case harvestCount = "harvest_count"
        case gridRow = "grid_row"
        case gridCol = "grid_col"
        case customName = "custom_name"
        case soilType = "soil_type"
        case sunExposure = "sun_exposure"
    }

    var displayLabel: String {
        if let name = customName, !name.isEmpty { return name }
        return "Plot \(plotNumber)"
    }
}

/// `GET /api/gardens/{id}/waitlist` — shape from `waitlist_to_dict` in
/// `app/api/gardens_api.py`. Used by the admin "Waitlist" screen to show
/// pending entries with promote / decline actions.
struct WaitlistEntry: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let userId: Int
    let userName: String
    let requestedAt: Date?
    let plotSizePref: String?
    let notes: String?
    /// `waiting`, `offered`, `accepted`, `declined`.
    let status: String
    let position: Int

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case userId = "user_id"
        case userName = "user_name"
        case requestedAt = "requested_at"
        case plotSizePref = "plot_size_pref"
        case notes, status, position
    }

    var isWaiting: Bool { status == "waiting" }
}
