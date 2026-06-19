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
