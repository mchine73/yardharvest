package app.yardharvest.manager.model

import app.yardharvest.manager.core.TimestampSerializer
import app.yardharvest.manager.core.WallClockSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

// Shapes mirror the backend's *_to_dict() helpers, and the iOS Codable types
// one-for-one. Optional fields default to null so payloads from an older or
// newer backend still decode.

/** `user_to_dict()` in `app/api/auth_api.py`. */
@Serializable
data class AuthUser(
    val id: Int,
    @SerialName("public_id") val publicId: String? = null,
    val username: String,
    val email: String,
    val role: String,
    @SerialName("display_name") val displayName: String? = null,
    val city: String? = null,
    val state: String? = null,
    @SerialName("is_admin") val isAdmin: Boolean = false,
    @SerialName("is_active_user") val isActiveUser: Boolean = true,
    @SerialName("phone_number") val phoneNumber: String? = null,
    @SerialName("sms_opt_in") val smsOptIn: Boolean? = null,
) {
    val bestName: String get() = displayName?.takeIf { it.isNotEmpty() } ?: username
}

/** `garden_to_dict()` in `app/api/gardens_api.py`. */
@Serializable
data class Garden(
    val id: Int,
    @SerialName("public_id") val publicId: String? = null,
    val name: String,
    val slug: String? = null,
    val description: String? = null,
    val address: String? = null,
    val city: String? = null,
    val state: String? = null,
    @SerialName("zip_code") val zipCode: String? = null,
    @SerialName("photo_url") val photoUrl: String? = null,
    @SerialName("total_plots") val totalPlots: Int? = null,
    @SerialName("plot_fee_annual") val plotFeeAnnual: Double? = null,
    @SerialName("operating_model") val operatingModel: String? = null,
    @SerialName("is_active") val isActive: Boolean = true,
    @SerialName("max_checkouts_per_member") val maxCheckoutsPerMember: Int? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("weather_alerts_enabled") val weatherAlertsEnabled: Boolean? = null,
    @SerialName("grid_rows") val gridRows: Int? = null,
    @SerialName("grid_cols") val gridCols: Int? = null,
    @SerialName("organizer_id") val organizerId: Int? = null,
    @SerialName("organizer_name") val organizerName: String? = null,
    /** This viewer's role and capabilities in the garden (garden_permissions.py). */
    @SerialName("user_garden_role") val userGardenRole: String? = null,
    @SerialName("user_capabilities") val userCapabilities: List<String>? = null,
) {
    /** Capability check mirroring the backend's `can()`. Absent list = no admin powers. */
    fun can(capability: String): Boolean = userCapabilities?.contains(capability) ?: false

    val locationLine: String get() = listOfNotNull(city, state).filter { it.isNotEmpty() }.joinToString(", ")
}

/** `GET /api/gardens/my-gardens`. */
@Serializable
data class MyGardensPayload(
    val organized: List<Garden> = emptyList(),
    /** Gardens where I hold an assigned admin role without being the organizer. */
    val helping: List<Garden>? = null,
    @SerialName("plot_holder") val plotHolder: List<Garden> = emptyList(),
    val waitlisted: List<Garden> = emptyList(),
) {
    val all: List<Garden> get() = organized + (helping ?: emptyList()) + plotHolder + waitlisted
}

/** `GET /api/garden-admin/{id}/dashboard`. */
@Serializable
data class DashboardPayload(
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("garden_name") val gardenName: String,
    @SerialName("is_active") val isActive: Boolean = true,
    val plots: PlotStats,
    @SerialName("waitlist_count") val waitlistCount: Int = 0,
    /** Wall posts awaiting moderation (flagged + auto-denied). */
    @SerialName("wall_flagged_count") val wallFlaggedCount: Int? = null,
    @SerialName("total_harvest_lbs") val totalHarvestLbs: Double = 0.0,
    @SerialName("unread_messages_count") val unreadMessagesCount: Int = 0,
    @SerialName("upcoming_events") val upcomingEvents: List<DashboardEvent> = emptyList(),
    @SerialName("recent_announcements") val recentAnnouncements: List<Announcement> = emptyList(),
    @SerialName("recent_photos") val recentPhotos: List<DashboardPhoto> = emptyList(),
) {
    @Serializable
    data class PlotStats(
        val total: Int = 0,
        val assigned: Int = 0,
        val available: Int = 0,
        val maintenance: Int = 0,
        val reserved: Int = 0,
        @SerialName("occupancy_pct") val occupancyPct: Double = 0.0,
        @SerialName("expiring_soon") val expiringSoon: Int = 0,
    )
}

@Serializable
data class DashboardEvent(
    val id: Int,
    val title: String,
    @Serializable(WallClockSerializer::class) @SerialName("event_date") val eventDate: Instant? = null,
    @SerialName("event_type") val eventType: String? = null,
    @SerialName("rsvp_going") val rsvpGoing: Int? = null,
)

@Serializable
data class DashboardPhoto(
    val id: Int,
    @SerialName("photo_url") val photoUrl: String? = null,
    val caption: String? = null,
    @SerialName("user_name") val userName: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

/** `announcement_to_dict()` in `app/api/garden_admin_api.py`. */
@Serializable
data class Announcement(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("author_id") val authorId: Int? = null,
    @SerialName("author_name") val authorName: String? = null,
    val title: String,
    val body: String,
    val priority: String? = null,
    val pinned: Boolean? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

/** Paginated response from `GET /api/gardens` — the public browse endpoint. */
@Serializable
data class BrowseGardensPage(
    val gardens: List<Garden> = emptyList(),
    val total: Int = 0,
    val pages: Int = 0,
    val page: Int = 1,
    @SerialName("has_next") val hasNext: Boolean = false,
    @SerialName("has_prev") val hasPrev: Boolean = false,
)

/** `GET /api/gardens/{id}` — garden with stats plus per-user context. */
@Serializable
data class GardenDetail(
    val id: Int,
    @SerialName("public_id") val publicId: String? = null,
    val name: String,
    val description: String? = null,
    val address: String? = null,
    val city: String? = null,
    val state: String? = null,
    @SerialName("zip_code") val zipCode: String? = null,
    @SerialName("photo_url") val photoUrl: String? = null,
    @SerialName("total_plots") val totalPlots: Int? = null,
    @SerialName("plot_fee_annual") val plotFeeAnnual: Double? = null,
    @SerialName("operating_model") val operatingModel: String? = null,
    val rules: String? = null,
    @SerialName("contact_email") val contactEmail: String? = null,
    @SerialName("organizer_id") val organizerId: Int? = null,
    @SerialName("organizer_name") val organizerName: String? = null,
    val latitude: Double? = null,
    val longitude: Double? = null,
    @SerialName("available_plots") val availablePlots: Int? = null,
    @SerialName("assigned_plots") val assignedPlots: Int? = null,
    @SerialName("member_count") val memberCount: Int? = null,
    @SerialName("waitlist_count") val waitlistCount: Int? = null,
    @SerialName("reserved_plots") val reservedPlots: Int? = null,
    @SerialName("upcoming_events") val upcomingEvents: Int? = null,
    @SerialName("user_is_organizer") val userIsOrganizer: Boolean = false,
    @SerialName("user_has_plot") val userHasPlot: Boolean = false,
    @SerialName("user_on_waitlist") val userOnWaitlist: Boolean = false,
    @SerialName("user_has_reservation") val userHasReservation: Boolean = false,
    @SerialName("upcoming_events_list") val upcomingEventsList: List<GardenEvent>? = null,
) {
    /** Adapter to a plain [Garden] for the banner card. */
    val asGarden: Garden
        get() = Garden(
            id = id, publicId = publicId, name = name, description = description,
            address = address, city = city, state = state, zipCode = zipCode, photoUrl = photoUrl,
            totalPlots = totalPlots, plotFeeAnnual = plotFeeAnnual, operatingModel = operatingModel,
            isActive = true, latitude = latitude, longitude = longitude,
            organizerId = organizerId, organizerName = organizerName,
        )
}

/** `GET /api/gardens/{id}/my-dues` — what the signed-in user owes. */
@Serializable
data class DuesRecord(
    val id: Int,
    @SerialName("season_year") val seasonYear: Int,
    @SerialName("amount_due") val amountDue: Double,
    @SerialName("amount_paid") val amountPaid: Double = 0.0,
    /** `unpaid`, `partial`, `paid`, `waived`, `comp`. */
    val status: String,
    @SerialName("payment_method") val paymentMethod: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("payment_date") val paymentDate: Instant? = null,
    @SerialName("payment_note") val paymentNote: String? = null,
) {
    val balance: Double get() = maxOf(0.0, amountDue - amountPaid)
    val isPaid: Boolean get() = status == "paid" || status == "waived" || status == "comp"
}

/** `POST /api/gardens/{id}/dues/{did}/pay` — the PaymentIntent (or dev-mode stub). */
@Serializable
data class DuesPaymentIntent(
    @SerialName("client_secret") val clientSecret: String? = null,
    @SerialName("payment_intent_id") val paymentIntentId: String? = null,
    @SerialName("publishable_key") val publishableKey: String? = null,
    val amount: Int = 0,
    val currency: String = "usd",
    @SerialName("dues_id") val duesId: Int,
    @SerialName("routed_to_manager") val routedToManager: Boolean? = null,
    @SerialName("dev_mode") val devMode: Boolean? = null,
) {
    val isDevMode: Boolean get() = devMode == true || clientSecret == null
}

/** `POST /api/gardens/{id}/waitlist`. */
@Serializable
data class WaitlistJoinResponse(val id: Int, val status: String, val position: Int)

/** Manager-side dues record from `GET /api/garden-admin/{id}/dues`. */
@Serializable
data class AdminDuesRecord(
    val id: Int,
    @SerialName("user_id") val userId: Int,
    @SerialName("user_name") val userName: String,
    @SerialName("season_year") val seasonYear: Int,
    @SerialName("amount_due") val amountDue: Double,
    @SerialName("amount_paid") val amountPaid: Double = 0.0,
    val status: String,
    @SerialName("payment_method") val paymentMethod: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("payment_date") val paymentDate: Instant? = null,
    @SerialName("payment_note") val paymentNote: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
) {
    val balance: Double get() = maxOf(0.0, amountDue - amountPaid)
    val isSettled: Boolean get() = status == "paid" || status == "waived" || status == "comp"
}

/**
 * In-person PaymentIntent consumed by Stripe Terminal. Shared by the dues
 * flow and ad-hoc sales, so `dues_id` must stay optional — a sale has none.
 */
@Serializable
data class InPersonPaymentIntent(
    @SerialName("client_secret") val clientSecret: String,
    @SerialName("payment_intent_id") val paymentIntentId: String,
    val amount: Int,
    val currency: String = "usd",
    @SerialName("dues_id") val duesId: Int? = null,
    @SerialName("connected_account_id") val connectedAccountId: String? = null,
)

/** `POST /api/garden-admin/terminal/connection_token`. */
@Serializable
data class TerminalConnectionToken(
    val secret: String,
    /** Stripe Terminal Location the device registers against, on the manager's own account. */
    @SerialName("location_id") val locationId: String? = null,
)

/** `event_to_dict()` in `app/api/gardens_api.py`. `event_date` is garden wall-clock time. */
@Serializable
data class GardenEvent(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    val title: String,
    val description: String? = null,
    @SerialName("event_type") val eventType: String? = null,
    @Serializable(WallClockSerializer::class) @SerialName("event_date") val eventDate: Instant? = null,
    @SerialName("duration_hours") val durationHours: Double? = null,
    @SerialName("max_volunteers") val maxVolunteers: Int? = null,
    val recurring: String = "none",
    @SerialName("created_by_id") val createdById: Int? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
    @SerialName("rsvp_going") val rsvpGoing: Int = 0,
    @SerialName("rsvp_maybe") val rsvpMaybe: Int = 0,
    @SerialName("user_rsvp") val userRsvp: String? = null,
)

enum class RsvpStatus(val raw: String, val label: String) {
    Going("going", "Going"),
    Maybe("maybe", "Maybe"),
    NotGoing("not_going", "Can't go"),
}

/** `harvest_to_dict()` in `app/api/gardens_api.py`. */
@Serializable
data class HarvestLog(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("user_id") val userId: Int,
    @SerialName("user_name") val userName: String? = null,
    val category: String,
    val variety: String? = null,
    @SerialName("quantity_lbs") val quantityLbs: Double,
    @Serializable(WallClockSerializer::class) @SerialName("harvest_date") val harvestDate: Instant? = null,
    val destination: String,
    val notes: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

enum class HarvestDestination(val raw: String, val label: String) {
    Personal("personal", "Personal use"),
    Shared("shared", "Shared with members"),
    FoodBank("food_bank", "Food bank"),
    Marketplace("marketplace", "Sold at market");

    companion object {
        fun from(raw: String) = entries.firstOrNull { it.raw == raw } ?: Personal
    }
}

/** Public garden member shape from `GET /api/gardens/{id}/members`. */
@Serializable
data class GardenMember(
    @SerialName("user_id") val userId: Int,
    val name: String,
    /** `organizer` or `plot_holder`. */
    val role: String,
    @SerialName("plot_number") val plotNumber: String? = null,
    @Serializable(TimestampSerializer::class) val since: Instant? = null,
) {
    val id: Int get() = userId
    val isOrganizer: Boolean get() = role == "organizer"
}

/** `message_to_dict()` in `app/api/messages_api.py`. */
@Serializable
data class YHMessage(
    val id: Int,
    @SerialName("thread_id") val threadId: String,
    @SerialName("sender_id") val senderId: Int,
    @SerialName("recipient_id") val recipientId: Int,
    @SerialName("sender_name") val senderName: String = "",
    @SerialName("recipient_name") val recipientName: String = "",
    @SerialName("listing_id") val listingId: Int? = null,
    val body: String,
    @SerialName("is_read") val isRead: Boolean = false,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

@Serializable
data class InboxThread(
    @SerialName("thread_id") val threadId: String,
    @SerialName("other_user") val otherUser: OtherUser,
    @SerialName("last_message") val lastMessage: YHMessage,
    val unread: Int = 0,
    val listing: ListingRef? = null,
) {
    @Serializable
    data class OtherUser(
        val id: Int,
        @SerialName("display_name") val displayName: String,
        @SerialName("profile_image") val profileImage: String? = null,
    )

    @Serializable
    data class ListingRef(val id: Int, val title: String)
}

@Serializable
data class ThreadPayload(
    val messages: List<YHMessage> = emptyList(),
    @SerialName("other_user") val otherUser: InboxThread.OtherUser,
    @SerialName("listing_id") val listingId: Int? = null,
)

/** `_notif_to_dict()` in `app/api/notifications_api.py`. */
@Serializable
data class YHNotification(
    val id: Int,
    val type: String? = null,
    val title: String,
    val body: String? = null,
    val link: String? = null,
    @SerialName("garden_id") val gardenId: Int? = null,
    @SerialName("is_read") val isRead: Boolean = false,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

@Serializable
data class NotificationsPayload(
    val notifications: List<YHNotification> = emptyList(),
    @SerialName("unread_count") val unreadCount: Int = 0,
    val total: Int = 0,
    val page: Int = 1,
    val pages: Int = 1,
)

@Serializable data class UnreadCountResponse(@SerialName("unread_count") val unreadCount: Int = 0)

/** `/api/messages/unread_count` uses `count`. */
@Serializable data class MessageCountResponse(val count: Int = 0)

/** Plot shape from `admin_list_plots` and `plot_to_dict()`. */
@Serializable
data class Plot(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("plot_number") val plotNumber: String,
    val size: String? = null,
    @SerialName("location_notes") val locationNotes: String? = null,
    /** `assigned`, `available`, `maintenance`, `reserved`. */
    val status: String,
    @SerialName("assigned_to_id") val assignedToId: Int? = null,
    @SerialName("assigned_to_name") val assignedToName: String? = null,
    @SerialName("assigned_to_email") val assignedToEmail: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("assigned_date") val assignedDate: Instant? = null,
    @Serializable(WallClockSerializer::class) @SerialName("renewal_date") val renewalDate: Instant? = null,
    @SerialName("reserved_by_id") val reservedById: Int? = null,
    @SerialName("reserved_by_name") val reservedByName: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("reserved_at") val reservedAt: Instant? = null,
    @SerialName("harvest_total_lbs") val harvestTotalLbs: Double? = null,
    @SerialName("harvest_count") val harvestCount: Int? = null,
    @SerialName("grid_row") val gridRow: Int? = null,
    @SerialName("grid_col") val gridCol: Int? = null,
    @SerialName("custom_name") val customName: String? = null,
    @SerialName("soil_type") val soilType: String? = null,
    @SerialName("sun_exposure") val sunExposure: String? = null,
) {
    val displayLabel: String get() = customName?.takeIf { it.isNotEmpty() } ?: "Plot $plotNumber"
}

/** `waitlist_to_dict` in `app/api/gardens_api.py`. */
@Serializable
data class WaitlistEntry(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("user_id") val userId: Int,
    @SerialName("user_name") val userName: String,
    @Serializable(TimestampSerializer::class) @SerialName("requested_at") val requestedAt: Instant? = null,
    @SerialName("plot_size_pref") val plotSizePref: String? = null,
    val notes: String? = null,
    /** `waiting`, `offered`, `accepted`, `declined`. */
    val status: String,
    val position: Int = 0,
) {
    val isWaiting: Boolean get() = status == "waiting"
}

/** `resource_to_dict()` in `app/api/gardens_api.py`. */
@Serializable
data class GardenResource(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    val name: String,
    @SerialName("resource_type") val resourceType: String? = null,
    val description: String? = null,
    val quantity: Int? = null,
    val condition: String? = null,
    @SerialName("checked_out_to_id") val checkedOutToId: Int? = null,
    @SerialName("checked_out_to_name") val checkedOutToName: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("checked_out_at") val checkedOutAt: Instant? = null,
    @SerialName("checkout_duration_days") val checkoutDurationDays: Int? = null,
    @Serializable(TimestampSerializer::class) @SerialName("due_date") val dueDate: Instant? = null,
    @SerialName("is_overdue") val isOverdue: Boolean = false,
    @SerialName("out_of_service") val outOfService: Boolean = false,
    @SerialName("service_note") val serviceNote: String? = null,
    /** `available`, `checked_out`, `overdue`, `out_of_service`. */
    val status: String = "available",
    /** Opaque token printed onto QR codes. */
    @SerialName("qr_code_token") val qrCodeToken: String? = null,
    /** Full scannable URL the QR code encodes. */
    @SerialName("qr_code_url") val qrCodeUrl: String? = null,
) {
    val isAvailable: Boolean get() = status == "available"
    val isCheckedOut: Boolean get() = status == "checked_out" || status == "overdue"
}

/** `GET /api/gardens/resources/lookup?token=...` — QR scan result. */
@Serializable
data class ResourceLookup(
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("garden_name") val gardenName: String,
    @SerialName("resource_id") val resourceId: Int,
    val resource: GardenResource,
)

/** `shift_to_dict()` in `app/api/gardens_api.py`. */
@Serializable
data class VolunteerShift(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    val title: String,
    val description: String? = null,
    @Serializable(WallClockSerializer::class) @SerialName("shift_date") val shiftDate: Instant? = null,
    @SerialName("start_time") val startTime: String? = null,
    @SerialName("end_time") val endTime: String? = null,
    @SerialName("max_volunteers") val maxVolunteers: Int? = null,
    val recurring: String = "none",
    @SerialName("signup_count") val signupCount: Int = 0,
    @SerialName("spots_left") val spotsLeft: Int? = null,
    @SerialName("created_by_name") val createdByName: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
    @SerialName("user_signed_up") val userSignedUp: Boolean? = null,
    @SerialName("user_signup_status") val userSignupStatus: String? = null,
) {
    val timeRange: String?
        get() {
            val start = startTime ?: return null
            return if (endTime != null) "$start–$endTime" else start
        }

    val isFull: Boolean get() = maxVolunteers?.let { signupCount >= it } ?: false
}
