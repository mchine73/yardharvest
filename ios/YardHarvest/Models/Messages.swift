import Foundation

/// `message_to_dict()` in `app/api/messages_api.py`.
struct YHMessage: Codable, Identifiable, Equatable, Hashable {
    let id: Int
    let threadId: String
    let senderId: Int
    let recipientId: Int
    let senderName: String
    let recipientName: String
    let listingId: Int?
    let body: String
    let isRead: Bool
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case threadId = "thread_id"
        case senderId = "sender_id"
        case recipientId = "recipient_id"
        case senderName = "sender_name"
        case recipientName = "recipient_name"
        case listingId = "listing_id"
        case body
        case isRead = "is_read"
        case createdAt = "created_at"
    }
}

struct InboxThread: Codable, Identifiable, Equatable, Hashable {
    let threadId: String
    let otherUser: OtherUser
    let lastMessage: YHMessage
    let unread: Int
    let listing: ListingRef?

    var id: String { threadId }

    enum CodingKeys: String, CodingKey {
        case threadId = "thread_id"
        case otherUser = "other_user"
        case lastMessage = "last_message"
        case unread, listing
    }

    struct OtherUser: Codable, Equatable, Hashable {
        let id: Int
        let displayName: String
        let profileImage: String?

        enum CodingKeys: String, CodingKey {
            case id
            case displayName = "display_name"
            case profileImage = "profile_image"
        }
    }

    struct ListingRef: Codable, Equatable, Hashable {
        let id: Int
        let title: String
    }
}

struct ThreadPayload: Codable, Equatable {
    let messages: [YHMessage]
    let otherUser: InboxThread.OtherUser
    let listingId: Int?

    enum CodingKeys: String, CodingKey {
        case messages
        case otherUser = "other_user"
        case listingId = "listing_id"
    }
}
