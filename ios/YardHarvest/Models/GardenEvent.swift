import Foundation

/// `event_to_dict()` in `app/api/gardens_api.py`.
struct GardenEvent: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let title: String
    let description: String?
    let eventType: String?
    let eventDate: Date?
    let durationHours: Double?
    let maxVolunteers: Int?
    let recurring: String
    let createdById: Int?
    let createdByName: String?
    let createdAt: Date?
    let rsvpGoing: Int
    let rsvpMaybe: Int
    let userRsvp: String?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case title, description
        case eventType = "event_type"
        case eventDate = "event_date"
        case durationHours = "duration_hours"
        case maxVolunteers = "max_volunteers"
        case recurring
        case createdById = "created_by_id"
        case createdByName = "created_by_name"
        case createdAt = "created_at"
        case rsvpGoing = "rsvp_going"
        case rsvpMaybe = "rsvp_maybe"
        case userRsvp = "user_rsvp"
    }
}

enum RSVPStatus: String, CaseIterable, Identifiable {
    case going, maybe, notGoing = "not_going"
    var id: String { rawValue }
    var label: String {
        switch self {
        case .going: return "Going"
        case .maybe: return "Maybe"
        case .notGoing: return "Can't go"
        }
    }
}
