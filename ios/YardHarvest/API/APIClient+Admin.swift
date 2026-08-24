import Foundation

extension APIClient {

    // MARK: - Dashboard

    /// `GET /api/garden-admin/{id}/dashboard`
    func dashboard(gardenID: Int) async throws -> DashboardPayload {
        try await get("/api/garden-admin/\(gardenID)/dashboard")
    }

    // MARK: - Plots (admin)

    /// `GET /api/garden-admin/{id}/plots`
    func adminListPlots(gardenID: Int) async throws -> [Plot] {
        try await get("/api/garden-admin/\(gardenID)/plots")
    }

    struct PlotMaintenanceResponse: Decodable {
        let id: Int
        let plotNumber: String
        let status: String
        let message: String?

        enum CodingKeys: String, CodingKey {
            case id
            case plotNumber = "plot_number"
            case status, message
        }
    }

    struct EmptyJSON: Encodable {}

    /// `PUT /api/garden-admin/{id}/plots/{pid}/maintenance` — toggles
    /// maintenance ⇄ available; 400 for assigned plots.
    func toggleMaintenance(gardenID: Int, plotID: Int) async throws -> PlotMaintenanceResponse {
        try await put("/api/garden-admin/\(gardenID)/plots/\(plotID)/maintenance",
                      body: EmptyJSON())
    }

    // MARK: - Reservation reviews (admin)

    /// `POST /api/garden-admin/{id}/plots/{pid}/confirm` — approve a
    /// member's plot reservation, flips it from `reserved` to `assigned`.
    struct AssignPlotBody: Encodable { let user_id: Int }

    /// `PUT /api/gardens/{id}/plots/{pid}/assign` — organizer-only. Assigns
    /// the plot to a member, flips it to `assigned`, and notifies them.
    func assignPlot(gardenID: Int, plotID: Int, userID: Int) async throws -> Plot {
        try await put("/api/gardens/\(gardenID)/plots/\(plotID)/assign",
                      body: AssignPlotBody(user_id: userID))
    }

    /// `PUT /api/gardens/{id}/plots/{pid}/release` — organizer-only. Clears
    /// assignment AND any pending reservation; the plot becomes available.
    func releasePlot(gardenID: Int, plotID: Int) async throws -> Plot {
        try await put("/api/gardens/\(gardenID)/plots/\(plotID)/release",
                      body: EmptyJSON())
    }

    /// Body for `PUT /api/garden-admin/{id}/plots/{pid}`. Encodable optionals
    /// are omitted when nil, matching the endpoint's "only touch keys that
    /// are present" semantics. `renewal_date` is "YYYY-MM-DD"; empty string
    /// clears it.
    struct EditPlotBody: Encodable {
        var custom_name: String?
        var size: String?
        var soil_type: String?
        var sun_exposure: String?
        var renewal_date: String?
        var location_notes: String?
    }

    /// `PUT /api/garden-admin/{id}/plots/{pid}` — edit plot details.
    /// Response is a partial plot dict; every field beyond the basics is
    /// optional on `Plot`, so it decodes (missing keys become nil).
    func adminEditPlot(gardenID: Int, plotID: Int, body: EditPlotBody) async throws -> Plot {
        try await put("/api/garden-admin/\(gardenID)/plots/\(plotID)", body: body)
    }

    func confirmReservation(gardenID: Int, plotID: Int) async throws -> Plot {
        try await post("/api/garden-admin/\(gardenID)/plots/\(plotID)/confirm",
                       body: EmptyJSON())
    }

    /// `POST /api/garden-admin/{id}/plots/{pid}/decline-reservation` —
    /// release a reservation back to `available`.
    func declineReservation(gardenID: Int, plotID: Int) async throws -> Plot {
        try await post("/api/garden-admin/\(gardenID)/plots/\(plotID)/decline-reservation",
                       body: EmptyJSON())
    }

    // MARK: - Waitlist (admin)

    /// `GET /api/gardens/{id}/waitlist` — public-but-organizer-only
    /// listing of every entry on this garden's waitlist (status =
    /// waiting + offered).
    func adminListWaitlist(gardenID: Int) async throws -> [WaitlistEntry] {
        try await get("/api/gardens/\(gardenID)/waitlist")
    }

    struct WaitlistApproveBody: Encodable { let plot_id: Int }
    struct WaitlistApproveResponse: Decodable {
        let plot: Plot
        let waitlistEntry: WaitlistEntry
        enum CodingKeys: String, CodingKey {
            case plot
            case waitlistEntry = "waitlist_entry"
        }
    }

    /// `POST /api/garden-admin/{id}/waitlist/{wlid}/approve` — promote a
    /// waitlist entry onto the chosen available plot. Returns both the
    /// updated plot (now `assigned`) and the waitlist entry (now
    /// `accepted`).
    func approveWaitlistEntry(gardenID: Int, entryID: Int, plotID: Int)
        async throws -> WaitlistApproveResponse {
        try await post("/api/garden-admin/\(gardenID)/waitlist/\(entryID)/approve",
                       body: WaitlistApproveBody(plot_id: plotID))
    }

    /// `POST /api/garden-admin/{id}/waitlist/{wlid}/decline`
    func declineWaitlistEntry(gardenID: Int, entryID: Int) async throws -> WaitlistEntry {
        try await post("/api/garden-admin/\(gardenID)/waitlist/\(entryID)/decline",
                       body: EmptyJSON())
    }

    // MARK: - Announcements (admin)

    /// Paginated wrapper from `GET /api/garden-admin/{id}/announcements`.
    struct AnnouncementsPage: Decodable {
        let announcements: [Announcement]
    }

    func listAnnouncements(gardenID: Int) async throws -> [Announcement] {
        let page: AnnouncementsPage =
            try await get("/api/garden-admin/\(gardenID)/announcements")
        return page.announcements
    }

    struct AnnouncementBody: Encodable {
        let title: String
        let body: String
        let send_email: Bool
        let send_sms: Bool
    }

    func createAnnouncement(gardenID: Int, title: String, body: String,
                            sendEmail: Bool, sendSMS: Bool) async throws -> Announcement {
        try await post("/api/garden-admin/\(gardenID)/announcements",
                       body: AnnouncementBody(title: title, body: body,
                                              send_email: sendEmail, send_sms: sendSMS))
    }

    // MARK: - Wall moderation

    /// `_admin_comment_to_dict` — moderation view of a wall post, including
    /// the AI moderator's stated reason.
    struct AdminWallComment: Decodable, Identifiable, Equatable {
        let id: Int
        let gardenId: Int
        let authorId: Int
        let authorName: String
        let body: String
        /// `approved`, `flagged`, or `blocked` (auto-denied, never public).
        let status: String
        let moderationReason: String?
        let createdAt: Date?

        enum CodingKeys: String, CodingKey {
            case id
            case gardenId = "garden_id"
            case authorId = "author_id"
            case authorName = "author_name"
            case body, status
            case moderationReason = "moderation_reason"
            case createdAt = "created_at"
        }
    }

    struct AdminCommentsFeed: Decodable, Equatable {
        let comments: [AdminWallComment]
        let flaggedCount: Int
        let blockedCount: Int

        enum CodingKeys: String, CodingKey {
            case comments
            case flaggedCount = "flagged_count"
            case blockedCount = "blocked_count"
        }
    }

    /// `GET /api/garden-admin/{id}/comments?status=…` — the moderation feed.
    func adminListComments(gardenID: Int, status: String) async throws -> AdminCommentsFeed {
        try await get("/api/garden-admin/\(gardenID)/comments", query: ["status": status])
    }

    /// `POST /api/garden-admin/{id}/comments/{cid}/approve` — clears a flag,
    /// or publishes an auto-denied post (rescuing a false positive).
    func adminApproveComment(gardenID: Int, commentID: Int) async throws -> AdminWallComment {
        try await post("/api/garden-admin/\(gardenID)/comments/\(commentID)/approve")
    }

    /// `DELETE /api/garden-admin/{id}/comments/{cid}`.
    func adminDeleteComment(gardenID: Int, commentID: Int) async throws {
        struct Ack: Decodable { let success: Bool? }
        let _: Ack = try await delete("/api/garden-admin/\(gardenID)/comments/\(commentID)")
    }

}
