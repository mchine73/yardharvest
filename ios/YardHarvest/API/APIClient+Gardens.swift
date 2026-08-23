import Foundation

extension APIClient {
    // MARK: - Gardens

    /// `GET /api/gardens/my-gardens`
    func myGardens() async throws -> MyGardensPayload {
        try await get("/api/gardens/my-gardens")
    }

    // MARK: - Resources (member-side)

    /// `GET /api/gardens/{id}/resources`
    func listResources(gardenID: Int) async throws -> [GardenResource] {
        try await get("/api/gardens/\(gardenID)/resources")
    }

    /// `GET /api/gardens/resources/lookup?token=...` — QR scan resolver.
    func resourceLookup(token: String) async throws -> ResourceLookup {
        try await get("/api/gardens/resources/lookup", query: ["token": token])
    }

    struct CheckoutBody: Encodable { let duration_days: Int }
    /// `POST /api/gardens/{id}/resources/{rid}/checkout`
    func checkoutResource(gardenID: Int, resourceID: Int, durationDays: Int = 3) async throws -> GardenResource {
        try await post("/api/gardens/\(gardenID)/resources/\(resourceID)/checkout",
                       body: CheckoutBody(duration_days: durationDays))
    }

    struct ReturnBody: Encodable { let condition_at_return: String? }
    /// `POST /api/gardens/{id}/resources/{rid}/return`
    func returnResource(gardenID: Int, resourceID: Int, condition: String? = nil) async throws -> GardenResource {
        try await post("/api/gardens/\(gardenID)/resources/\(resourceID)/return",
                       body: ReturnBody(condition_at_return: condition))
    }

    struct CreateResourceBody: Encodable {
        let name: String
        let resource_type: String
        let description: String
        let quantity: Int
        let condition: String
    }
    /// `POST /api/gardens/{id}/resources` — manager-only on the backend
    /// (the route checks `garden.organizer_id == current_user.id`). The
    /// returned resource includes a freshly minted `qr_code_token` +
    /// `qr_code_url` so the caller can immediately render and print a QR.
    func createResource(gardenID: Int,
                         name: String,
                         resourceType: String = "tool",
                         description: String = "",
                         quantity: Int = 1,
                         condition: String = "good") async throws -> GardenResource {
        try await post("/api/gardens/\(gardenID)/resources",
                       body: CreateResourceBody(
                        name: name,
                        resource_type: resourceType,
                        description: description,
                        quantity: quantity,
                        condition: condition))
    }

    // MARK: - Events

    /// `GET /api/gardens/{id}/events?show=upcoming|past|all`
    func listEvents(gardenID: Int, show: String = "upcoming") async throws -> [GardenEvent] {
        try await get("/api/gardens/\(gardenID)/events", query: ["show": show])
    }

    struct RSVPBody: Encodable { let status: String }
    func rsvpEvent(gardenID: Int, eventID: Int, status: RSVPStatus) async throws -> GardenEvent {
        try await post("/api/gardens/\(gardenID)/events/\(eventID)/rsvp",
                       body: RSVPBody(status: status.rawValue))
    }
    func cancelRSVP(gardenID: Int, eventID: Int) async throws -> GardenEvent {
        try await delete("/api/gardens/\(gardenID)/events/\(eventID)/rsvp")
    }

    // MARK: - Shifts (member-side; admin actions in +Admin)

    /// `GET /api/gardens/{id}/shifts?show=upcoming|past|all`
    func listShifts(gardenID: Int, show: String = "upcoming") async throws -> [VolunteerShift] {
        try await get("/api/gardens/\(gardenID)/shifts", query: ["show": show])
    }

    struct AckMessage: Decodable { let message: String? }
    /// `POST /api/gardens/{id}/shifts/{sid}/signup` — returns {message}.
    func signUpForShift(gardenID: Int, shiftID: Int) async throws {
        let _: AckMessage = try await post("/api/gardens/\(gardenID)/shifts/\(shiftID)/signup")
    }
    /// `DELETE /api/gardens/{id}/shifts/{sid}/signup`
    func cancelShiftSignup(gardenID: Int, shiftID: Int) async throws {
        let _: AckMessage = try await delete("/api/gardens/\(gardenID)/shifts/\(shiftID)/signup")
    }

    // MARK: - Harvest

    /// `GET /api/gardens/{id}/harvests`
    func listHarvests(gardenID: Int) async throws -> [HarvestLog] {
        try await get("/api/gardens/\(gardenID)/harvests")
    }

    struct HarvestBody: Encodable {
        let category: String
        let variety: String?
        let quantity_lbs: Double
        let harvest_date: String
        let destination: String
        let notes: String?
    }

    /// `POST /api/gardens/{id}/harvests`
    func logHarvest(gardenID: Int, category: String, variety: String?,
                    quantityLbs: Double, harvestDate: Date,
                    destination: HarvestDestination, notes: String?) async throws -> HarvestLog {
        let fmt = DateFormatter()
        fmt.dateFormat = "yyyy-MM-dd"
        fmt.timeZone = .current
        return try await post("/api/gardens/\(gardenID)/harvests",
                              body: HarvestBody(
                                category: category,
                                variety: variety?.isEmpty == false ? variety : nil,
                                quantity_lbs: quantityLbs,
                                harvest_date: fmt.string(from: harvestDate),
                                destination: destination.rawValue,
                                notes: notes?.isEmpty == false ? notes : nil))
    }

    // MARK: - Community wall

    /// `GET /api/gardens/{id}/comments` — the garden's public comment wall.
    /// Replies attach one level deep via `parent_id`.
    func listWallComments(gardenID: Int) async throws -> [WallComment] {
        try await get("/api/gardens/\(gardenID)/comments")
    }

    struct PostCommentBody: Encodable {
        let body: String
        var parent_id: Int?
    }

    /// `POST /api/gardens/{id}/comments`. The AI moderator can hold a post —
    /// that surfaces as a 422 whose message explains why; show it verbatim.
    func postWallComment(gardenID: Int, body: String, parentID: Int? = nil) async throws -> WallComment {
        try await post("/api/gardens/\(gardenID)/comments",
                       body: PostCommentBody(body: body, parent_id: parentID))
    }

    struct LikeToggle: Decodable {
        let likesCount: Int
        let liked: Bool
        enum CodingKeys: String, CodingKey {
            case likesCount = "likes_count"
            case liked
        }
    }

    /// `POST /api/gardens/{id}/comments/{cid}/like` — toggles; returns new state.
    func toggleCommentLike(gardenID: Int, commentID: Int) async throws -> LikeToggle {
        try await post("/api/gardens/\(gardenID)/comments/\(commentID)/like")
    }

    struct DeleteAck: Decodable { let success: Bool? }

    /// `DELETE /api/gardens/{id}/comments/{cid}` — author or organizer only.
    func deleteWallComment(gardenID: Int, commentID: Int) async throws {
        let _: DeleteAck = try await delete("/api/gardens/\(gardenID)/comments/\(commentID)")
    }

}
