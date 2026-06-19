import Foundation

/// Public garden member shape from `GET /api/gardens/{id}/members`.
struct GardenMember: Codable, Identifiable, Equatable, Hashable {
    let userId: Int
    let name: String
    /// `organizer` or `plot_holder`.
    let role: String
    let plotNumber: String?
    let since: Date?

    var id: Int { userId }

    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case name, role
        case plotNumber = "plot_number"
        case since
    }

    var isOrganizer: Bool { role == "organizer" }
}
