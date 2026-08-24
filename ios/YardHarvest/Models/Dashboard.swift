import Foundation

/// `GET /api/garden-admin/{id}/dashboard`.
struct DashboardPayload: Codable, Equatable {
    let gardenId: Int
    let gardenName: String
    let isActive: Bool
    let plots: PlotStats
    let waitlistCount: Int
    /// Wall posts awaiting moderation (flagged + auto-denied). Optional so
    /// cached pre-moderation payloads still decode.
    let wallFlaggedCount: Int?
    let totalHarvestLbs: Double
    let unreadMessagesCount: Int
    let upcomingEvents: [DashboardEvent]
    let recentAnnouncements: [Announcement]
    let recentPhotos: [DashboardPhoto]

    enum CodingKeys: String, CodingKey {
        case gardenId = "garden_id"
        case gardenName = "garden_name"
        case isActive = "is_active"
        case plots
        case waitlistCount = "waitlist_count"
        case wallFlaggedCount = "wall_flagged_count"
        case totalHarvestLbs = "total_harvest_lbs"
        case unreadMessagesCount = "unread_messages_count"
        case upcomingEvents = "upcoming_events"
        case recentAnnouncements = "recent_announcements"
        case recentPhotos = "recent_photos"
    }

    struct PlotStats: Codable, Equatable {
        let total: Int
        let assigned: Int
        let available: Int
        let maintenance: Int
        let reserved: Int
        let occupancyPct: Double
        let expiringSoon: Int

        enum CodingKeys: String, CodingKey {
            case total, assigned, available, maintenance, reserved
            case occupancyPct = "occupancy_pct"
            case expiringSoon = "expiring_soon"
        }
    }
}

struct DashboardEvent: Codable, Identifiable, Equatable {
    let id: Int
    let title: String
    let eventDate: Date?
    let eventType: String?
    let rsvpGoing: Int?

    enum CodingKeys: String, CodingKey {
        case id, title
        case eventDate = "event_date"
        case eventType = "event_type"
        case rsvpGoing = "rsvp_going"
    }
}

struct DashboardPhoto: Codable, Identifiable, Equatable {
    let id: Int
    let photoUrl: String?
    let caption: String?
    let userName: String?
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case photoUrl = "photo_url"
        case caption
        case userName = "user_name"
        case createdAt = "created_at"
    }
}
