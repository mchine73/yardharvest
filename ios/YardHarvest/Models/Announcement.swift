import Foundation

/// `announcement_to_dict()` in `app/api/garden_admin_api.py`.
struct Announcement: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let gardenId: Int
    let authorId: Int?
    let authorName: String?
    let title: String
    let body: String
    let priority: String?
    let pinned: Bool?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case authorId = "author_id"
        case authorName = "author_name"
        case title, body, priority, pinned
        case createdAt = "created_at"
    }
}
