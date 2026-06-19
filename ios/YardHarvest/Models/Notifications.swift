import Foundation

/// `_notif_to_dict()` in `app/api/notifications_api.py`.
struct YHNotification: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let type: String?
    let title: String
    let body: String?
    let link: String?
    let gardenId: Int?
    let isRead: Bool
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, type, title, body, link
        case gardenId = "garden_id"
        case isRead = "is_read"
        case createdAt = "created_at"
    }
}

struct NotificationsPayload: Codable, Equatable {
    let notifications: [YHNotification]
    let unreadCount: Int
    let total: Int
    let page: Int
    let pages: Int

    enum CodingKeys: String, CodingKey {
        case notifications
        case unreadCount = "unread_count"
        case total, page, pages
    }
}

struct UnreadCountResponse: Codable, Equatable {
    let unreadCount: Int
    enum CodingKeys: String, CodingKey { case unreadCount = "unread_count" }
}

struct MessageCountResponse: Codable, Equatable {
    /// `/api/messages/unread_count` uses `count`.
    let count: Int
}
