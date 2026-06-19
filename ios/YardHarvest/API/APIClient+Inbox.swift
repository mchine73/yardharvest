import Foundation

extension APIClient {

    // MARK: - Messages

    func inbox() async throws -> [InboxThread] {
        try await get("/api/messages/inbox")
    }

    func thread(threadID: String) async throws -> ThreadPayload {
        try await get("/api/messages/thread/\(threadID)")
    }

    struct SendMessageBody: Encodable {
        let recipient_id: Int
        let body: String
        let listing_id: Int?
    }

    func sendMessage(recipientID: Int, body: String, listingID: Int? = nil) async throws -> YHMessage {
        try await post("/api/messages/send",
                       body: SendMessageBody(recipient_id: recipientID, body: body, listing_id: listingID))
    }

    func messagesUnreadCount() async throws -> Int {
        let resp: MessageCountResponse = try await get("/api/messages/unread_count")
        return resp.count
    }

    // MARK: - Notifications

    func listNotifications(page: Int = 1, perPage: Int = 20,
                            unreadOnly: Bool = false) async throws -> NotificationsPayload {
        try await get("/api/notifications", query: [
            "page": String(page),
            "per_page": String(perPage),
            "unread_only": unreadOnly ? "true" : "false",
        ])
    }

    func notificationsUnreadCount() async throws -> Int {
        let resp: UnreadCountResponse = try await get("/api/notifications/unread-count")
        return resp.unreadCount
    }

    struct AckOK: Decodable { let ok: Bool }

    func markNotificationRead(notificationID: Int) async throws {
        let _: AckOK = try await post("/api/notifications/\(notificationID)/read")
    }
    func markAllNotificationsRead() async throws {
        let _: AckOK = try await post("/api/notifications/mark-all-read")
    }
    func deleteNotification(notificationID: Int) async throws {
        let _: AckOK = try await delete("/api/notifications/\(notificationID)")
    }
}
