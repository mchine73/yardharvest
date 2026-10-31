package app.yardharvest.manager.api

import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.ApiError
import app.yardharvest.manager.core.Dates
import app.yardharvest.manager.core.TokenStore
import app.yardharvest.manager.model.*
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

// Endpoint methods, one-for-one with ios/YardHarvest/API/APIClient+*.swift.

@Serializable private class EmptyJson

// ---- Auth ------------------------------------------------------------------

@Serializable data class TokenResponse(val user: AuthUser, val access_token: String, val refresh_token: String)
@Serializable private data class LoginRequest(val email: String, val password: String)

/** `POST /api/auth/token` */
suspend fun ApiClient.login(email: String, password: String): TokenResponse {
    val response: TokenResponse = try {
        post("/api/auth/token", LoginRequest(email, password), authenticated = false)
    } catch (e: ApiError.Unauthorized) {
        // A 401 here can only mean the credentials were wrong.
        throw ApiError.InvalidCredentials
    } catch (e: ApiError.Forbidden) {
        // The only 403 this endpoint returns is a deactivated account.
        throw ApiError.AccountDeactivated
    }
    TokenStore.set(response.access_token, TokenStore.Key.AccessToken)
    TokenStore.set(response.refresh_token, TokenStore.Key.RefreshToken)
    return response
}

@Serializable private data class ForgotPasswordRequest(val email: String)

/** `POST /api/auth/forgot-password` — always succeeds for a well-formed address. */
suspend fun ApiClient.forgotPassword(email: String) =
    send("POST", "/api/auth/forgot-password", encode(ForgotPasswordRequest(email)), authenticated = false)

/** `GET /api/auth/me` */
suspend fun ApiClient.me(): AuthUser = get("/api/auth/me")

/** `POST /api/auth/logout` */
suspend fun ApiClient.logout() {
    send("POST", "/api/auth/logout")
    TokenStore.clear()
}

@Serializable private data class DeviceTokenRequest(val device_token: String, val platform: String)

/** `PUT /api/auth/device-token` */
suspend fun ApiClient.registerDeviceToken(token: String) =
    send("PUT", "/api/auth/device-token", encode(DeviceTokenRequest(token, "android")))

@Serializable
private data class RegisterRequest(
    val username: String, val email: String, val password: String,
    /** Always `gardener` from the app — managers register on the web. */
    val role: String, val display_name: String, val address: String,
    val city: String, val state: String, val zip_code: String,
)

/** `POST /api/auth/token/register` */
suspend fun ApiClient.register(
    email: String, password: String, displayName: String, username: String,
    address: String, city: String, state: String, zipCode: String,
): TokenResponse {
    val response: TokenResponse = post(
        "/api/auth/token/register",
        RegisterRequest(username, email, password, "gardener", displayName, address, city, state, zipCode),
        authenticated = false,
    )
    TokenStore.set(response.access_token, TokenStore.Key.AccessToken)
    TokenStore.set(response.refresh_token, TokenStore.Key.RefreshToken)
    return response
}

// ---- Discovery ---------------------------------------------------------------

/** `GET /api/gardens?page=&search=` */
suspend fun ApiClient.browseGardens(page: Int = 1, search: String? = null): BrowseGardensPage {
    val q = mutableMapOf("page" to page.toString())
    if (!search.isNullOrEmpty()) q["search"] = search
    return get("/api/gardens", q, authenticated = false)
}

/** `GET /api/gardens/{id}` */
suspend fun ApiClient.gardenDetail(gardenId: Int): GardenDetail = get("/api/gardens/$gardenId")

/** `GET /api/gardens/{id}/plots` — public plot list. */
suspend fun ApiClient.publicPlots(gardenId: Int): List<Plot> = get("/api/gardens/$gardenId/plots", authenticated = false)

/** `GET /api/gardens/{id}/members` — organizer + plot holders. */
suspend fun ApiClient.listGardenMembers(gardenId: Int): List<GardenMember> =
    get("/api/gardens/$gardenId/members", authenticated = false)

/** `POST /api/gardens/{id}/plots/{pid}/reserve` */
suspend fun ApiClient.reservePlot(gardenId: Int, plotId: Int): Plot = post("/api/gardens/$gardenId/plots/$plotId/reserve")

@Serializable private data class WaitlistJoinBody(val plot_size_pref: String?, val notes: String?)

/** `POST /api/gardens/{id}/waitlist` */
suspend fun ApiClient.joinWaitlist(gardenId: Int, sizePref: String?, notes: String?): WaitlistJoinResponse =
    post("/api/gardens/$gardenId/waitlist", WaitlistJoinBody(sizePref?.ifEmpty { null }, notes?.ifEmpty { null }))

/** `GET /api/gardens/{id}/my-dues` */
suspend fun ApiClient.myDues(gardenId: Int): List<DuesRecord> = get("/api/gardens/$gardenId/my-dues")

/** `POST /api/gardens/{id}/dues/{did}/pay` */
suspend fun ApiClient.payDues(gardenId: Int, duesId: Int): DuesPaymentIntent = post("/api/gardens/$gardenId/dues/$duesId/pay")

@Serializable private data class ConfirmPaymentBody(val payment_intent_id: String)
@Serializable data class MessageAck(val message: String? = null)

/** `POST /api/gardens/{id}/dues/{did}/confirm-payment` */
suspend fun ApiClient.confirmDuesPayment(gardenId: Int, duesId: Int, paymentIntentId: String): String {
    val resp: MessageAck = post("/api/gardens/$gardenId/dues/$duesId/confirm-payment", ConfirmPaymentBody(paymentIntentId))
    return resp.message ?: "Payment confirmed."
}

// ---- Gardens (member side) ---------------------------------------------------------------

/** `GET /api/gardens/my-gardens` */
suspend fun ApiClient.myGardens(): MyGardensPayload = get("/api/gardens/my-gardens")

/** `GET /api/gardens/{id}/resources` */
suspend fun ApiClient.listResources(gardenId: Int): List<GardenResource> = get("/api/gardens/$gardenId/resources")

/** `GET /api/gardens/resources/lookup?token=...` — QR scan resolver. */
suspend fun ApiClient.resourceLookup(token: String): ResourceLookup =
    get("/api/gardens/resources/lookup", mapOf("token" to token))

@Serializable private data class CheckoutBody(val duration_days: Int)

/** `POST /api/gardens/{id}/resources/{rid}/checkout` */
suspend fun ApiClient.checkoutResource(gardenId: Int, resourceId: Int, durationDays: Int = 3): GardenResource =
    post("/api/gardens/$gardenId/resources/$resourceId/checkout", CheckoutBody(durationDays))

@Serializable private data class ReturnBody(val condition_at_return: String?)

/** `POST /api/gardens/{id}/resources/{rid}/return` */
suspend fun ApiClient.returnResource(gardenId: Int, resourceId: Int, condition: String? = null): GardenResource =
    post("/api/gardens/$gardenId/resources/$resourceId/return", ReturnBody(condition))

@Serializable
private data class CreateResourceBody(
    val name: String, val resource_type: String, val description: String, val quantity: Int, val condition: String,
)

/** `POST /api/gardens/{id}/resources` — returns the resource with a fresh QR token + URL. */
suspend fun ApiClient.createResource(
    gardenId: Int, name: String, resourceType: String = "tool", description: String = "",
    quantity: Int = 1, condition: String = "good",
): GardenResource = post(
    "/api/gardens/$gardenId/resources",
    CreateResourceBody(name, resourceType, description, quantity, condition),
)

/** `GET /api/gardens/{id}/events?show=upcoming|past|all` */
suspend fun ApiClient.listEvents(gardenId: Int, show: String = "upcoming"): List<GardenEvent> =
    get("/api/gardens/$gardenId/events", mapOf("show" to show))

@Serializable private data class RsvpBody(val status: String)

suspend fun ApiClient.rsvpEvent(gardenId: Int, eventId: Int, status: RsvpStatus): GardenEvent =
    post("/api/gardens/$gardenId/events/$eventId/rsvp", RsvpBody(status.raw))

suspend fun ApiClient.cancelRsvp(gardenId: Int, eventId: Int): GardenEvent =
    delete("/api/gardens/$gardenId/events/$eventId/rsvp")

/** `GET /api/gardens/{id}/shifts?show=upcoming|past|all` */
suspend fun ApiClient.listShifts(gardenId: Int, show: String = "upcoming"): List<VolunteerShift> =
    get("/api/gardens/$gardenId/shifts", mapOf("show" to show))

/** `POST /api/gardens/{id}/shifts/{sid}/signup` */
suspend fun ApiClient.signUpForShift(gardenId: Int, shiftId: Int) =
    send("POST", "/api/gardens/$gardenId/shifts/$shiftId/signup")

/** `DELETE /api/gardens/{id}/shifts/{sid}/signup` */
suspend fun ApiClient.cancelShiftSignup(gardenId: Int, shiftId: Int) =
    send("DELETE", "/api/gardens/$gardenId/shifts/$shiftId/signup")

/** `GET /api/gardens/{id}/harvests` */
suspend fun ApiClient.listHarvests(gardenId: Int): List<HarvestLog> = get("/api/gardens/$gardenId/harvests")

@Serializable
private data class HarvestBody(
    val category: String, val variety: String?, val quantity_lbs: Double,
    val harvest_date: String, val destination: String, val notes: String?,
)

/** `POST /api/gardens/{id}/harvests` */
suspend fun ApiClient.logHarvest(
    gardenId: Int, category: String, variety: String?, quantityLbs: Double,
    harvestDate: Instant, destination: HarvestDestination, notes: String?,
): HarvestLog = post(
    "/api/gardens/$gardenId/harvests",
    HarvestBody(
        category, variety?.ifEmpty { null }, quantityLbs, Dates.ymd(harvestDate),
        destination.raw, notes?.ifEmpty { null },
    ),
)

// ---- Community wall ------------------------------------------------------------

/** `GET /api/gardens/{id}/comments` */
suspend fun ApiClient.listWallComments(gardenId: Int): List<WallComment> = get("/api/gardens/$gardenId/comments")

@Serializable private data class PostCommentBody(val body: String, val parent_id: Int?)

/** `POST /api/gardens/{id}/comments`. A 422 means the AI moderator held it — show the message. */
suspend fun ApiClient.postWallComment(gardenId: Int, body: String, parentId: Int? = null): WallComment =
    post("/api/gardens/$gardenId/comments", PostCommentBody(body, parentId))

@Serializable data class LikeToggle(@SerialName("likes_count") val likesCount: Int, val liked: Boolean)

/** `POST /api/gardens/{id}/comments/{cid}/like` — toggles. */
suspend fun ApiClient.toggleCommentLike(gardenId: Int, commentId: Int): LikeToggle =
    post("/api/gardens/$gardenId/comments/$commentId/like")

/** `DELETE /api/gardens/{id}/comments/{cid}` — author or organizer. */
suspend fun ApiClient.deleteWallComment(gardenId: Int, commentId: Int) =
    send("DELETE", "/api/gardens/$gardenId/comments/$commentId")

/** `GET /api/gardens/comment-report-reasons` */
suspend fun ApiClient.commentReportReasons(): List<ReportReason> = get("/api/gardens/comment-report-reasons")

@Serializable private data class ReportCommentBody(val reason: String, val note: String?)
@Serializable data class ReportAck(val success: Boolean? = null, @SerialName("already_reported") val alreadyReported: Boolean? = null)

/** `POST /api/gardens/{id}/comments/{cid}/report` — reporting twice is a no-op success. */
suspend fun ApiClient.reportWallComment(gardenId: Int, commentId: Int, reason: String, note: String?): ReportAck =
    post("/api/gardens/$gardenId/comments/$commentId/report", ReportCommentBody(reason, note?.ifEmpty { null }))

/** `GET /api/profile/blocks` */
suspend fun ApiClient.blockedMembers(): List<BlockedMember> = get("/api/profile/blocks")

@Serializable private data class BlockBody(val user_id: Int)
@Serializable data class BlockAck(val success: Boolean? = null, val name: String? = null)

/** `POST /api/profile/blocks` — hides that member's wall posts from you. */
suspend fun ApiClient.blockMember(userId: Int): BlockAck = post("/api/profile/blocks", BlockBody(userId))

/** `DELETE /api/profile/blocks/{userId}` */
suspend fun ApiClient.unblockMember(userId: Int) = send("DELETE", "/api/profile/blocks/$userId")

// ---- Photo gallery ------------------------------------------------------------

@Serializable
data class PhotosFeed(
    val photos: List<GalleryPhoto> = emptyList(),
    val total: Int? = null,
    @SerialName("pro_required") val proRequired: Boolean? = null,
)

/** `GET /api/photos/garden/{id}` — newest first. */
suspend fun ApiClient.listGardenPhotos(gardenId: Int, page: Int = 1): PhotosFeed =
    get("/api/photos/garden/$gardenId", mapOf("page" to page.toString()))

@Serializable data class UploadedPhoto(val id: Int? = null, val url: String? = null, val message: String? = null)

/** `POST /api/photos/upload` — multipart; the server downsizes. Pro-gated. */
suspend fun ApiClient.uploadGardenPhoto(gardenId: Int, jpeg: ByteArray, caption: String): UploadedPhoto =
    uploadMultipart(
        "/api/photos/upload",
        fields = mapOf("garden_id" to gardenId.toString(), "caption" to caption, "category" to "general"),
        fileField = "photo",
        fileName = "photo.jpg",
        mimeType = "image/jpeg",
        fileData = jpeg,
        deserializer = UploadedPhoto.serializer(),
    )

@Serializable data class PhotoLikeToggle(val liked: Boolean, @SerialName("likes_count") val likesCount: Int)

/** `POST /api/photos/{id}/like` — toggles. */
suspend fun ApiClient.togglePhotoLike(photoId: Int): PhotoLikeToggle = post("/api/photos/$photoId/like")

@Serializable private data class PhotoCommentsFeed(val comments: List<PhotoComment> = emptyList())

suspend fun ApiClient.listPhotoComments(photoId: Int): List<PhotoComment> =
    get<PhotoCommentsFeed>("/api/photos/$photoId/comments").comments

@Serializable private data class PhotoCommentBody(val content: String)

suspend fun ApiClient.postPhotoComment(photoId: Int, content: String): PhotoComment =
    post("/api/photos/$photoId/comments", PhotoCommentBody(content))

/** `DELETE /api/photos/{id}` — poster, garden admin, or site admin. */
suspend fun ApiClient.deleteGardenPhoto(photoId: Int) = send("DELETE", "/api/photos/$photoId")

// ---- Roles, events, shifts (admin capabilities) ----------------------------------

@Serializable private data class RoleChangeBody(val role: String)
@Serializable private data class RoleChangeAck(val role: String)

/** `POST /api/garden-admin/{id}/members/{uid}/role` — ROLES capability. */
suspend fun ApiClient.changeMemberRole(gardenId: Int, userId: Int, role: String): String =
    post<RoleChangeBody, RoleChangeAck>("/api/garden-admin/$gardenId/members/$userId/role", RoleChangeBody(role)).role

@Serializable
data class CreateEventBody(
    val title: String,
    val description: String,
    val event_type: String,
    /** Naive local ISO datetime — the backend stores garden-local time. */
    val event_date: String,
    val duration_hours: Double,
    val max_volunteers: Int?,
    val recurring: String,
)

/** `POST /api/gardens/{id}/events` — recurring expands server-side. */
suspend fun ApiClient.createEvent(gardenId: Int, body: CreateEventBody): GardenEvent =
    post("/api/gardens/$gardenId/events", body)

@Serializable
data class CreateShiftBody(
    val title: String,
    val description: String,
    val shift_date: String,
    val start_time: String,
    val end_time: String,
    val max_volunteers: Int?,
    val recurring: String,
)

/** `POST /api/garden-admin/{id}/shifts` — SHIFTS capability, Garden Pro. */
suspend fun ApiClient.createShift(gardenId: Int, body: CreateShiftBody): VolunteerShift =
    post("/api/garden-admin/$gardenId/shifts", body)

// ---- Inbox & notifications ------------------------------------------------------

suspend fun ApiClient.inbox(): List<InboxThread> = get("/api/messages/inbox")

suspend fun ApiClient.thread(threadId: String): ThreadPayload = get("/api/messages/thread/$threadId")

@Serializable private data class SendMessageBody(val recipient_id: Int, val body: String, val listing_id: Int?)

suspend fun ApiClient.sendMessage(recipientId: Int, body: String, listingId: Int? = null): YHMessage =
    post("/api/messages/send", SendMessageBody(recipientId, body, listingId))

suspend fun ApiClient.messagesUnreadCount(): Int = get<MessageCountResponse>("/api/messages/unread_count").count

suspend fun ApiClient.listNotifications(page: Int = 1, perPage: Int = 20, unreadOnly: Boolean = false): NotificationsPayload =
    get("/api/notifications", mapOf("page" to "$page", "per_page" to "$perPage", "unread_only" to unreadOnly.toString()))

suspend fun ApiClient.notificationsUnreadCount(): Int =
    get<UnreadCountResponse>("/api/notifications/unread-count").unreadCount

suspend fun ApiClient.markNotificationRead(notificationId: Int) = send("POST", "/api/notifications/$notificationId/read")
suspend fun ApiClient.markAllNotificationsRead() = send("POST", "/api/notifications/mark-all-read")
suspend fun ApiClient.deleteNotification(notificationId: Int) = send("DELETE", "/api/notifications/$notificationId")

// ---- Garden admin ------------------------------------------------------------

/** `GET /api/garden-admin/{id}/dashboard` */
suspend fun ApiClient.dashboard(gardenId: Int): DashboardPayload = get("/api/garden-admin/$gardenId/dashboard")

/** `GET /api/garden-admin/{id}/plots` */
suspend fun ApiClient.adminListPlots(gardenId: Int): List<Plot> = get("/api/garden-admin/$gardenId/plots")

@Serializable
data class PlotMaintenanceResponse(
    val id: Int,
    @SerialName("plot_number") val plotNumber: String,
    val status: String,
    val message: String? = null,
)

/** `PUT /api/garden-admin/{id}/plots/{pid}/maintenance` — toggles maintenance ⇄ available. */
suspend fun ApiClient.toggleMaintenance(gardenId: Int, plotId: Int): PlotMaintenanceResponse =
    put("/api/garden-admin/$gardenId/plots/$plotId/maintenance", EmptyJson())

@Serializable private data class AssignPlotBody(val user_id: Int)

/** `PUT /api/gardens/{id}/plots/{pid}/assign` — organizer-only. */
suspend fun ApiClient.assignPlot(gardenId: Int, plotId: Int, userId: Int): Plot =
    put("/api/gardens/$gardenId/plots/$plotId/assign", AssignPlotBody(userId))

/** `PUT /api/gardens/{id}/plots/{pid}/release` — clears assignment and any reservation. */
suspend fun ApiClient.releasePlot(gardenId: Int, plotId: Int): Plot =
    put("/api/gardens/$gardenId/plots/$plotId/release", EmptyJson())

/** Only keys that are present are touched. `renewal_date` is yyyy-MM-dd; "" clears it. */
@Serializable
data class EditPlotBody(
    val custom_name: String? = null,
    val size: String? = null,
    val soil_type: String? = null,
    val sun_exposure: String? = null,
    val renewal_date: String? = null,
    val location_notes: String? = null,
)

/** `PUT /api/garden-admin/{id}/plots/{pid}` */
suspend fun ApiClient.adminEditPlot(gardenId: Int, plotId: Int, body: EditPlotBody): Plot =
    put("/api/garden-admin/$gardenId/plots/$plotId", body)

suspend fun ApiClient.confirmReservation(gardenId: Int, plotId: Int): Plot =
    post("/api/garden-admin/$gardenId/plots/$plotId/confirm", EmptyJson())

suspend fun ApiClient.declineReservation(gardenId: Int, plotId: Int): Plot =
    post("/api/garden-admin/$gardenId/plots/$plotId/decline-reservation", EmptyJson())

/** `GET /api/gardens/{id}/waitlist` */
suspend fun ApiClient.adminListWaitlist(gardenId: Int): List<WaitlistEntry> = get("/api/gardens/$gardenId/waitlist")

@Serializable private data class WaitlistApproveBody(val plot_id: Int)

@Serializable
data class WaitlistApproveResponse(val plot: Plot, @SerialName("waitlist_entry") val waitlistEntry: WaitlistEntry)

suspend fun ApiClient.approveWaitlistEntry(gardenId: Int, entryId: Int, plotId: Int): WaitlistApproveResponse =
    post("/api/garden-admin/$gardenId/waitlist/$entryId/approve", WaitlistApproveBody(plotId))

suspend fun ApiClient.declineWaitlistEntry(gardenId: Int, entryId: Int): WaitlistEntry =
    post("/api/garden-admin/$gardenId/waitlist/$entryId/decline", EmptyJson())

@Serializable private data class AnnouncementsPage(val announcements: List<Announcement> = emptyList())

suspend fun ApiClient.listAnnouncements(gardenId: Int): List<Announcement> =
    get<AnnouncementsPage>("/api/garden-admin/$gardenId/announcements").announcements

@Serializable private data class AnnouncementBody(val title: String, val body: String, val send_email: Boolean, val send_sms: Boolean)

suspend fun ApiClient.createAnnouncement(gardenId: Int, title: String, body: String, sendEmail: Boolean, sendSms: Boolean): Announcement =
    post("/api/garden-admin/$gardenId/announcements", AnnouncementBody(title, body, sendEmail, sendSms))

/** `GET /api/garden-admin/{id}/comments?status=…` — the moderation feed. */
suspend fun ApiClient.adminListComments(gardenId: Int, status: String): AdminCommentsFeed =
    get("/api/garden-admin/$gardenId/comments", mapOf("status" to status))

/** Clears a flag, or publishes an auto-denied post. */
suspend fun ApiClient.adminApproveComment(gardenId: Int, commentId: Int): AdminWallComment =
    post("/api/garden-admin/$gardenId/comments/$commentId/approve")

suspend fun ApiClient.adminDeleteComment(gardenId: Int, commentId: Int) =
    send("DELETE", "/api/garden-admin/$gardenId/comments/$commentId")

// ---- Admin dues & Tap to Pay ------------------------------------------------------

/** `GET /api/garden-admin/{id}/dues?status=` */
suspend fun ApiClient.adminListDues(gardenId: Int, status: String? = null): List<AdminDuesRecord> {
    val q = if (status != null && status != "all") mapOf("status" to status) else emptyMap()
    return get("/api/garden-admin/$gardenId/dues", q)
}

@Serializable private data class TerminalSessionBody(val garden_id: Int)

/**
 * Connection-token secret plus the Location the reader registers to. With a
 * garden id, both are scoped to that garden's payout account (MONEY role) —
 * how a co-organizer or treasurer takes payment.
 */
suspend fun ApiClient.terminalSession(gardenId: Int? = null): TerminalConnectionToken =
    if (gardenId != null) post("/api/garden-admin/terminal/connection_token", TerminalSessionBody(gardenId))
    else post("/api/garden-admin/terminal/connection_token")

suspend fun ApiClient.terminalConnectionToken(gardenId: Int? = null): String = terminalSession(gardenId).secret

/** `POST /api/garden-admin/{id}/dues/{did}/collect-in-person` */
suspend fun ApiClient.createInPersonDuesPaymentIntent(gardenId: Int, duesId: Int): InPersonPaymentIntent =
    post("/api/garden-admin/$gardenId/dues/$duesId/collect-in-person")

@Serializable
private data class FinalizeInPersonResponse(val message: String? = null, @SerialName("dues_status") val duesStatus: String? = null)

/** `POST /api/garden-admin/{id}/dues/{did}/finalize-in-person` */
suspend fun ApiClient.finalizeInPersonDues(gardenId: Int, duesId: Int, paymentIntentId: String): String =
    post<ConfirmPaymentBody, FinalizeInPersonResponse>(
        "/api/garden-admin/$gardenId/dues/$duesId/finalize-in-person", ConfirmPaymentBody(paymentIntentId),
    ).message ?: "Dues marked paid."

@Serializable private data class AdHocChargeBody(val amount_cents: Int, val memo: String?)

/** `POST /api/garden-admin/{id}/in-person-charge` — ad-hoc Tap to Pay for any amount + memo. */
suspend fun ApiClient.createInPersonCharge(gardenId: Int, amountCents: Int, memo: String?): InPersonPaymentIntent =
    post("/api/garden-admin/$gardenId/in-person-charge", AdHocChargeBody(amountCents, memo?.ifEmpty { null }))

// ---- Finance (read-only, webhook-fed) ---------------------------------------------

suspend fun ApiClient.gardenMoneyFeed(gardenId: Int, days: Int = 90, kind: String? = null, limit: Int = 60): GardenMoneyFeed {
    val q = mutableMapOf("days" to "$days", "limit" to "$limit")
    if (!kind.isNullOrEmpty()) q["kind"] = kind
    return get("/api/garden-admin/$gardenId/finance/activity", q)
}

suspend fun ApiClient.gardenPayouts(gardenId: Int, days: Int = 90): GardenPayoutSummary =
    get("/api/garden-admin/$gardenId/finance/payouts", mapOf("days" to "$days"))

/** Includes an Express dashboard link only when something is wrong. */
suspend fun ApiClient.gardenStripeStatus(gardenId: Int): GardenStripeStatus =
    get("/api/garden-admin/$gardenId/finance/stripe-status")
