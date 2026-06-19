import Foundation

/// `user_to_dict()` in `app/api/auth_api.py`.
struct AuthUser: Codable, Identifiable, Equatable {
    let id: Int
    let publicId: String?
    let username: String
    let email: String
    let role: String
    let displayName: String?
    let city: String?
    let state: String?
    let isAdmin: Bool
    let isActiveUser: Bool
    let phoneNumber: String?
    let smsOptIn: Bool?

    enum CodingKeys: String, CodingKey {
        case id
        case publicId = "public_id"
        case username, email, role
        case displayName = "display_name"
        case city, state
        case isAdmin = "is_admin"
        case isActiveUser = "is_active_user"
        case phoneNumber = "phone_number"
        case smsOptIn = "sms_opt_in"
    }

    var bestName: String { displayName?.isEmpty == false ? displayName! : username }
}
