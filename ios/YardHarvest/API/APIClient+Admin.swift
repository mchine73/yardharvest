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
}
