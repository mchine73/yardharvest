import Foundation

/// `harvest_to_dict()` in `app/api/gardens_api.py`.
struct HarvestLog: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let userId: Int
    let userName: String?
    let category: String
    let variety: String?
    let quantityLbs: Double
    let harvestDate: Date?
    let destination: String
    let notes: String?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case userId = "user_id"
        case userName = "user_name"
        case category, variety
        case quantityLbs = "quantity_lbs"
        case harvestDate = "harvest_date"
        case destination, notes
        case createdAt = "created_at"
    }
}

enum HarvestDestination: String, CaseIterable, Identifiable {
    case personal, shared, foodBank = "food_bank", marketplace
    var id: String { rawValue }
    var label: String {
        switch self {
        case .personal: return "Personal use"
        case .shared: return "Shared with members"
        case .foodBank: return "Food bank"
        case .marketplace: return "Sold at market"
        }
    }
}
