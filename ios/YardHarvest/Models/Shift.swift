import Foundation

/// `shift_to_dict()` in `app/api/gardens_api.py`.
struct VolunteerShift: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let title: String
    let description: String?
    let shiftDate: Date?
    let startTime: String?
    let endTime: String?
    let maxVolunteers: Int?
    let recurring: String
    let signupCount: Int
    let spotsLeft: Int?
    let createdByName: String?
    let createdAt: Date?
    let userSignedUp: Bool?
    let userSignupStatus: String?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case title, description
        case shiftDate = "shift_date"
        case startTime = "start_time"
        case endTime = "end_time"
        case maxVolunteers = "max_volunteers"
        case recurring
        case signupCount = "signup_count"
        case spotsLeft = "spots_left"
        case createdByName = "created_by_name"
        case createdAt = "created_at"
        case userSignedUp = "user_signed_up"
        case userSignupStatus = "user_signup_status"
    }

    var timeRange: String? {
        guard let start = startTime else { return nil }
        if let end = endTime { return "\(start)–\(end)" }
        return start
    }

    var isFull: Bool {
        guard let max = maxVolunteers else { return false }
        return signupCount >= max
    }
}
