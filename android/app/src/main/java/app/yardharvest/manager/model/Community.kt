package app.yardharvest.manager.model

import app.yardharvest.manager.core.TimestampSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import java.time.Instant

/** A post on the garden's community wall. Replies attach one level deep via [parentId]. */
@Serializable
data class WallComment(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("parent_id") val parentId: Int? = null,
    @SerialName("author_id") val authorId: Int,
    @SerialName("author_name") val authorName: String,
    @SerialName("author_image") val authorImage: String? = null,
    val body: String,
    /** `approved` or `flagged` (flagged posts show, but the organizer was alerted). */
    val status: String = "approved",
    @SerialName("likes_count") val likesCount: Int = 0,
    @SerialName("liked_by_me") val likedByMe: Boolean = false,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
    @SerialName("can_delete") val canDelete: Boolean = false,
    /** False on your own posts — there is nothing to report or block there. */
    @SerialName("can_report") val canReport: Boolean = false,
    @SerialName("reported_by_me") val reportedByMe: Boolean = false,
)

/** One photo in the garden gallery (`app/api/photos_api.py`). */
@Serializable
data class GalleryPhoto(
    val id: Int,
    val filename: String = "",
    val url: String,
    val caption: String? = null,
    val width: Int? = null,
    val height: Int? = null,
    @SerialName("user_id") val userId: Int,
    @SerialName("user_name") val userName: String = "",
    @SerialName("likes_count") val likesCount: Int = 0,
    @SerialName("liked_by_me") val likedByMe: Boolean = false,
    @SerialName("comments_count") val commentsCount: Int = 0,
    @SerialName("can_delete") val canDelete: Boolean = false,
    @Serializable(TimestampSerializer::class) @SerialName("uploaded_at") val uploadedAt: Instant? = null,
)

@Serializable
data class PhotoComment(
    val id: Int,
    @SerialName("photo_id") val photoId: Int,
    @SerialName("user_id") val userId: Int,
    @SerialName("user_name") val userName: String = "",
    val content: String,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
)

/** Moderation view of a wall post, including the AI moderator's stated reason. */
@Serializable
data class AdminWallComment(
    val id: Int,
    @SerialName("garden_id") val gardenId: Int,
    @SerialName("author_id") val authorId: Int,
    @SerialName("author_name") val authorName: String,
    val body: String,
    /** `approved`, `flagged`, or `blocked` (auto-denied, never public). */
    val status: String,
    @SerialName("moderation_reason") val moderationReason: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("created_at") val createdAt: Instant? = null,
    /** Unanswered member reports on this post. */
    @SerialName("report_count") val reportCount: Int? = null,
)

@Serializable
data class AdminCommentsFeed(
    val comments: List<AdminWallComment> = emptyList(),
    @SerialName("flagged_count") val flaggedCount: Int = 0,
    @SerialName("blocked_count") val blockedCount: Int = 0,
    @SerialName("reported_count") val reportedCount: Int? = null,
)

/** A reason a post can be reported for; the backend owns the list. */
@Serializable
data class ReportReason(val id: String, val label: String)

/** A member the signed-in user has blocked. */
@Serializable
data class BlockedMember(
    @SerialName("user_id") val userId: Int,
    val name: String,
    val image: String? = null,
    @Serializable(TimestampSerializer::class) @SerialName("blocked_at") val blockedAt: Instant? = null,
)
