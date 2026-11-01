package app.yardharvest.manager.ui.community

import android.content.Context
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Reply
import androidx.compose.material.icons.rounded.ArrowUpward
import androidx.compose.material.icons.rounded.Block
import androidx.compose.material.icons.rounded.ChatBubble
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Delete
import androidx.compose.material.icons.rounded.Favorite
import androidx.compose.material.icons.rounded.FavoriteBorder
import androidx.compose.material.icons.rounded.Flag
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.MoreVert
import androidx.compose.material.icons.rounded.Photo
import androidx.compose.material.icons.rounded.PhotoCamera
import androidx.compose.material.icons.rounded.Upload
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.adminApproveComment
import app.yardharvest.manager.api.adminDeleteComment
import app.yardharvest.manager.api.adminListComments
import app.yardharvest.manager.api.blockMember
import app.yardharvest.manager.api.commentReportReasons
import app.yardharvest.manager.api.deleteGardenPhoto
import app.yardharvest.manager.api.deleteWallComment
import app.yardharvest.manager.api.listGardenPhotos
import app.yardharvest.manager.api.listPhotoComments
import app.yardharvest.manager.api.listWallComments
import app.yardharvest.manager.api.postPhotoComment
import app.yardharvest.manager.api.postWallComment
import app.yardharvest.manager.api.reportWallComment
import app.yardharvest.manager.api.toggleCommentLike
import app.yardharvest.manager.api.togglePhotoLike
import app.yardharvest.manager.api.uploadGardenPhoto
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.AdminCommentsFeed
import app.yardharvest.manager.model.AdminWallComment
import app.yardharvest.manager.model.GalleryPhoto
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.PhotoComment
import app.yardharvest.manager.model.ReportReason
import app.yardharvest.manager.model.WallComment
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHConfirmDialog
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHFormSection
import app.yardharvest.manager.ui.brand.YHFormTextField
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHNoticeDialog
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSegmented
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonBlock
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import coil.compose.AsyncImage
import java.io.ByteArrayOutputStream
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/**
 * The garden's community wall: top-level posts with one level of replies,
 * likes, and a composer pinned below. Posting runs the backend's AI
 * moderator; a held post comes back as an error shown verbatim.
 */
@Composable
fun CommunityScreen(garden: Garden) {
    val nav = LocalNav.current
    val focus = LocalFocusManager.current
    var comments by remember { mutableStateOf<List<WallComment>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var composer by remember { mutableStateOf("") }
    var replyTarget by remember { mutableStateOf<WallComment?>(null) }
    var posting by remember { mutableStateOf(false) }
    var postError by remember { mutableStateOf<String?>(null) }
    var pendingDelete by remember { mutableStateOf<WallComment?>(null) }
    var reportTarget by remember { mutableStateOf<WallComment?>(null) }
    var pendingBlock by remember { mutableStateOf<WallComment?>(null) }
    var notice by remember { mutableStateOf<String?>(null) }
    val composerFocus = remember { FocusRequester() }
    val scope = rememberCoroutineScope()

    // Moderation rides the CONTENT capability, with the identity fallback.
    val isOrganizer = garden.can("content") || (AuthManager.currentUser?.id?.let { it == garden.organizerId } ?: false)

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { comments = ApiClient.listWallComments(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    val topLevel = comments.filter { it.parentId == null }
    fun replies(c: WallComment) = comments.filter { it.parentId == c.id }.sortedBy { it.createdAt }

    fun post() {
        val text = composer.trim()
        if (posting || text.isEmpty()) return
        scope.launch {
            posting = true
            postError = null
            try {
                val posted = ApiClient.postWallComment(garden.id, text, replyTarget?.id)
                comments = listOf(posted) + comments
                composer = ""
                replyTarget = null
                focus.clearFocus()
                Haptics.success()
            } catch (e: Exception) {
                postError = e.userMessage // moderation holds arrive as the server's message
                Haptics.error()
            } finally {
                posting = false
            }
        }
    }

    val actions = CommentActions(
        onLike = { c ->
            scope.launch {
                try {
                    val r = ApiClient.toggleCommentLike(garden.id, c.id)
                    comments = comments.map { if (it.id == c.id) it.copy(likesCount = r.likesCount, likedByMe = r.liked) else it }
                    Haptics.tap()
                } catch (_: Exception) { /* low stakes */ }
            }
        },
        onReply = { c -> replyTarget = c; runCatching { composerFocus.requestFocus() } },
        onDelete = { pendingDelete = it },
        onReport = { reportTarget = it },
        onBlock = { pendingBlock = it },
    )

    YHScreen("Community", actions = {
        if (isOrganizer) YHBarIcon(Icons.Rounded.VerifiedUser, "Moderation queue", tint = YH.ink) { nav.push(Dest.Moderation(garden)) }
    }) {
        Column(Modifier.fillMaxSize().imePadding()) {
            Box(Modifier.weight(1f)) {
                YHLoadable(loading, comments.isEmpty(), error, { scope.launch { load() } },
                    empty = {
                        Column {
                            Box(Modifier.padding(YH.Space.md)) { PhotoStrip(garden) }
                            YHEmpty(Icons.Rounded.Forum, "Nothing on the wall yet", "Say hello — posts here are visible to everyone in the garden.")
                        }
                    }) {
                    YHRefreshable({ load(false) }) {
                        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                            item { PhotoStrip(garden) }
                            items(topLevel, key = { it.id }) { c -> WallCommentCard(c, replies(c), actions) }
                        }
                    }
                }
            }
            // Composer
            Column(Modifier.fillMaxWidth().background(YH.canvas)) {
                HorizontalDivider(color = YH.border)
                replyTarget?.let { rt ->
                    Row(Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = 6.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Icon(Icons.AutoMirrored.Rounded.Reply, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                        Text("Replying to ${rt.authorName}", style = YHType.caption, color = YH.muted, modifier = Modifier.weight(1f))
                        Icon(Icons.Rounded.Close, "Cancel reply", tint = YH.muted, modifier = Modifier.size(18.dp).clickable { replyTarget = null })
                    }
                }
                postError?.let { Text(it, style = YHType.caption, color = YH.danger, modifier = Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = 6.dp)) }
                Row(Modifier.padding(horizontal = YH.Space.md, vertical = YH.Space.sm), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
                    ComposerField(composer, { composer = it }, "Write something…", Modifier.weight(1f).focusRequester(composerFocus), maxLines = 4)
                    SendButton(posting, composer.isNotBlank(), 40.dp) { post() }
                }
            }
        }
    }

    pendingDelete?.let { target ->
        YHConfirmDialog("Delete this post?", "Replies to it are removed too. This can't be undone.", "Delete", destructive = true,
            onConfirm = {
                scope.launch {
                    try {
                        ApiClient.deleteWallComment(garden.id, target.id)
                        comments = comments.filter { it.id != target.id && it.parentId != target.id }
                        Haptics.success()
                    } catch (e: Exception) { error = e.userMessage; Haptics.error() }
                }
            },
            onDismiss = { pendingDelete = null })
    }
    pendingBlock?.let { target ->
        YHConfirmDialog("Block ${target.authorName}?",
            "You won't see their posts or replies anywhere in YardHarvest. They aren't told. You can undo this in Settings.",
            "Block", destructive = true,
            onConfirm = {
                scope.launch {
                    try {
                        ApiClient.blockMember(target.authorId)
                        // Their posts leave this feed now rather than on next load.
                        comments = comments.filter { it.authorId != target.authorId }
                        Haptics.success()
                        notice = "You won't see posts from ${target.authorName} any more."
                    } catch (e: Exception) { error = e.userMessage; Haptics.error() }
                }
            },
            onDismiss = { pendingBlock = null })
    }
    reportTarget?.let { target ->
        ReportCommentSheet(garden, target, onDismiss = { reportTarget = null }) { message ->
            // Mark it reported locally so the menu reads "Reported" without a round trip.
            comments = comments.map { if (it.id == target.id) it.copy(reportedByMe = true) else it }
            notice = message
        }
    }
    notice?.let { YHNoticeDialog("Thanks", it) { notice = null } }
}

private class CommentActions(
    val onLike: (WallComment) -> Unit,
    val onReply: (WallComment) -> Unit,
    val onDelete: (WallComment) -> Unit,
    val onReport: (WallComment) -> Unit,
    val onBlock: (WallComment) -> Unit,
)

@Composable
private fun WallCommentCard(comment: WallComment, replies: List<WallComment>, actions: CommentActions) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            CommentBody(comment, actions, isReply = false)
            replies.forEach { reply ->
                Row(Modifier.padding(start = YH.Space.sm).height(IntrinsicSize.Min), horizontalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
                    Box(Modifier.width(2.dp).fillMaxHeight().clip(RoundedCornerShape(1.dp)).background(YH.border))
                    Box(Modifier.weight(1f)) { CommentBody(reply, actions, isReply = true) }
                }
            }
        }
    }
}

@Composable
private fun CommentBody(c: WallComment, actions: CommentActions, isReply: Boolean) {
    var menu by remember { mutableStateOf(false) }
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            YHAvatar(c.authorName, size = if (isReply) 26.dp else 34.dp)
            Column(Modifier.weight(1f)) {
                Text(c.authorName, style = if (isReply) YHType.captionMed else YHType.bodyMedium, color = YH.ink)
                c.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
            }
            // One overflow menu: delete for your own posts, report and block for others'.
            if (c.canDelete || c.canReport) {
                Box {
                    Icon(Icons.Rounded.MoreVert, "More actions", tint = YH.muted,
                        modifier = Modifier.size(30.dp).clip(CircleShape).clickable { menu = true }.padding(5.dp))
                    DropdownMenu(menu, onDismissRequest = { menu = false }, modifier = Modifier.background(YH.canvas)) {
                        if (c.canReport) {
                            DropdownMenuItem(
                                text = { Text(if (c.reportedByMe) "Reported" else "Report post", color = if (c.reportedByMe) YH.muted else YH.ink) },
                                leadingIcon = { Icon(Icons.Rounded.Flag, null, tint = YH.muted) },
                                enabled = !c.reportedByMe,
                                onClick = { menu = false; actions.onReport(c) },
                            )
                            DropdownMenuItem(
                                text = { Text("Block ${c.authorName}", color = YH.danger) },
                                leadingIcon = { Icon(Icons.Rounded.Block, null, tint = YH.danger) },
                                onClick = { menu = false; actions.onBlock(c) },
                            )
                        }
                        if (c.canDelete) {
                            DropdownMenuItem(
                                text = { Text("Delete post", color = YH.danger) },
                                leadingIcon = { Icon(Icons.Rounded.Delete, null, tint = YH.danger) },
                                onClick = { menu = false; actions.onDelete(c) },
                            )
                        }
                    }
                }
            }
        }
        Text(c.body, style = YHType.subheadline, color = YH.ink)
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable { actions.onLike(c) }.padding(2.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Icon(if (c.likedByMe) Icons.Rounded.Favorite else Icons.Rounded.FavoriteBorder, "Like",
                    tint = if (c.likedByMe) YH.danger else YH.muted, modifier = Modifier.size(16.dp))
                if (c.likesCount > 0) Text("${c.likesCount}", fontSize = 13.sp, fontWeight = FontWeight.Medium, color = YH.muted)
            }
            if (!isReply) Text("Reply", fontSize = 13.sp, fontWeight = FontWeight.Medium, color = YH.muted,
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { actions.onReply(c) }.padding(2.dp))
        }
    }
}

@Composable
private fun ComposerField(value: String, onChange: (String) -> Unit, placeholder: String, modifier: Modifier, maxLines: Int) {
    BasicTextField(
        value, onChange, maxLines = maxLines,
        textStyle = YHType.body.copy(color = YH.ink),
        cursorBrush = SolidColor(YH.ink),
        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
        modifier = modifier,
        decorationBox = { inner ->
            Box(Modifier.clip(RoundedCornerShape(YH.Radius.lg)).background(YH.surface).padding(horizontal = 14.dp, vertical = 10.dp)) {
                if (value.isEmpty()) Text(placeholder, style = YHType.body, color = YH.muted)
                inner()
            }
        },
    )
}

@Composable
private fun SendButton(busy: Boolean, enabled: Boolean, size: Dp, onClick: () -> Unit) {
    Box(
        Modifier.size(size).clip(CircleShape).background(YH.lime).clickable(enabled = enabled && !busy, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        if (busy) CircularProgressIndicator(Modifier.size(18.dp), color = YH.ink, strokeWidth = 2.dp)
        else Icon(Icons.Rounded.ArrowUpward, "Send", tint = if (enabled) YH.ink else YH.muted, modifier = Modifier.size(18.dp))
    }
}

// ---- Report ----------------------------------------------------------------------

/** Offered if the reasons call fails: a report that can't be filed is a rejected app. */
private val fallbackReasons = listOf(
    ReportReason("harassment", "Harassment or bullying"), ReportReason("hate", "Hate speech"),
    ReportReason("spam", "Spam or scam"), ReportReason("sexual", "Sexual content"),
    ReportReason("violence", "Violence or threats"), ReportReason("other", "Something else"),
)

/** Report a wall post: it goes straight to the organizer's moderation queue. */
@Composable
private fun ReportCommentSheet(garden: Garden, comment: WallComment, onDismiss: () -> Unit, onReported: (String) -> Unit) {
    var reasons by remember { mutableStateOf<List<ReportReason>>(emptyList()) }
    var selected by remember { mutableStateOf<String?>(null) }
    var note by remember { mutableStateOf("") }
    var loading by remember { mutableStateOf(true) }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        reasons = runCatching { ApiClient.commentReportReasons() }.getOrNull()?.takeIf { it.isNotEmpty() } ?: fallbackReasons
        loading = false
    }

    fun send() {
        val reason = selected ?: return
        scope.launch {
            sending = true
            error = null
            try {
                ApiClient.reportWallComment(garden.id, comment.id, reason, note.trim())
                Haptics.success()
                onReported("This post has been sent to the garden's organizer for review.")
                onDismiss()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                sending = false
            }
        }
    }

    YHSheet(
        { if (!sending) onDismiss() }, title = "Report post",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, enabled = !sending, onClick = onDismiss) },
        trailing = {
            if (sending) CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
            else YHBarButton("Send", enabled = selected != null) { send() }
        },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Text(comment.authorName, style = YHType.bodyMedium, color = YH.ink)
                Text(comment.body, style = YHType.caption, color = YH.muted, maxLines = 3)
            }
            YHFormSection("What's wrong with it?") {
                if (loading) {
                    Row(Modifier.padding(YH.Space.md), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        CircularProgressIndicator(Modifier.size(18.dp), color = YH.ink, strokeWidth = 2.dp)
                        Text("Loading", color = YH.muted)
                    }
                } else reasons.forEach { r ->
                    Row(Modifier.fillMaxWidth().clickable { selected = r.id }.padding(horizontal = YH.Space.md, vertical = 14.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text(r.label, color = YH.ink, modifier = Modifier.weight(1f))
                        if (selected == r.id) Icon(Icons.Rounded.Check, null, tint = YH.ink)
                    }
                }
            }
            YHFormSection("Anything to add? (optional)") {
                YHFormTextField(note, { note = it }, "Tell the organizer what happened", singleLine = false, minLines = 2)
            }
            Text(
                "The garden's organizer reviews reported posts and can remove them. To stop seeing this member entirely, block them from the same menu.",
                style = YHType.caption, color = YH.muted,
            )
            error?.let { YHInlineError(it) }
        }
    }
}

// ---- Moderation ------------------------------------------------------------------

private enum class Segment(val raw: String) { Reported("reported"), Flagged("flagged"), Blocked("blocked") }

/**
 * Organizer moderation queue. Reported posts are member objections; Flagged
 * are live but the AI wants a human look; Auto-denied were blocked outright and
 * can be published to rescue a false positive. Each card shows the
 * moderator's stated reason, because "the AI said so" is not reviewable.
 */
@Composable
fun ModerationScreen(garden: Garden) {
    var feed by remember { mutableStateOf<AdminCommentsFeed?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var segment by remember { mutableStateOf(Segment.Reported) }
    var workingId by remember { mutableStateOf<Int?>(null) }
    var pendingDelete by remember { mutableStateOf<AdminWallComment?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { feed = ApiClient.adminListComments(garden.id, segment.raw) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id, segment) { load() }

    fun label(s: Segment): String {
        val n = when (s) { Segment.Reported -> feed?.reportedCount ?: 0; Segment.Flagged -> feed?.flaggedCount ?: 0; Segment.Blocked -> feed?.blockedCount ?: 0 }
        val base = when (s) { Segment.Reported -> "Reported"; Segment.Flagged -> "Flagged"; Segment.Blocked -> "Auto-denied" }
        return if (n > 0) "$base ($n)" else base
    }

    YHScreen("Moderation") {
        YHLoadable(loading, feed == null, error, { scope.launch { load() } },
            empty = { YHEmpty(Icons.Rounded.VerifiedUser, "Nothing to review", "Reported, flagged and auto-denied posts appear here.") }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item { YHSegmented(Segment.entries, segment, { label(it) }) { segment = it } }
                    val comments = feed?.comments.orEmpty()
                    if (comments.isEmpty()) item {
                        YHCard {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Icon(Icons.Rounded.Verified, null, tint = YH.muted)
                                Text(
                                    when (segment) {
                                        Segment.Reported -> "No reported posts — nothing is waiting on you."
                                        Segment.Flagged -> "No flagged posts — the wall is clean."
                                        Segment.Blocked -> "Nothing has been auto-denied."
                                    },
                                    style = YHType.subheadline, color = YH.muted,
                                )
                            }
                        }
                    }
                    items(comments, key = { it.id }) { c ->
                        ModerationCard(c, workingId == c.id, if (segment == Segment.Blocked) "Publish" else "Keep",
                            onApprove = {
                                if (workingId == null) scope.launch {
                                    workingId = c.id
                                    try { ApiClient.adminApproveComment(garden.id, c.id); Haptics.success(); load(false) }
                                    catch (e: Exception) { error = e.userMessage; Haptics.error() }
                                    finally { workingId = null }
                                }
                            },
                            onDelete = { pendingDelete = c })
                    }
                    error?.takeIf { feed != null }?.let { item { YHInlineError(it) } }
                }
            }
        }
    }
    pendingDelete?.let { c ->
        YHConfirmDialog(
            "Delete this post?",
            if (segment == Segment.Blocked) "The author was never shown it publicly; this erases it for good." else "Removes it from the wall permanently.",
            "Delete", destructive = true,
            onConfirm = {
                if (workingId == null) scope.launch {
                    workingId = c.id
                    try { ApiClient.adminDeleteComment(garden.id, c.id); Haptics.success(); load(false) }
                    catch (e: Exception) { error = e.userMessage; Haptics.error() }
                    finally { workingId = null }
                }
            },
            onDismiss = { pendingDelete = null },
        )
    }
}

@Composable
private fun ModerationCard(c: AdminWallComment, working: Boolean, approveLabel: String, onApprove: () -> Unit, onDelete: () -> Unit) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                YHAvatar(c.authorName, size = 32.dp)
                Column(Modifier.weight(1f)) {
                    Text(c.authorName, style = YHType.bodyMedium, color = YH.ink)
                    c.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
                }
                val n = c.reportCount ?: 0
                if (n > 0) {
                    // One objection or several changes how urgent this is.
                    Text(if (n == 1) "1 report" else "$n reports", fontSize = 11.sp, fontWeight = FontWeight.SemiBold, color = YH.danger,
                        modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.danger.copy(alpha = 0.12f)).padding(horizontal = 8.dp, vertical = 4.dp))
                }
            }
            Text(c.body, style = YHType.subheadline, color = YH.ink)
            if (!c.moderationReason.isNullOrEmpty()) {
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.sm)).background(YH.warning.copy(alpha = 0.08f)).padding(10.dp),
                    horizontalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Icon(Icons.Rounded.WarningAmber, null, tint = YH.warning, modifier = Modifier.size(14.dp))
                    Text(c.moderationReason, style = YHType.caption, color = YH.warning)
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                YHButton(approveLabel, icon = Icons.Rounded.Check, style = YHButtonStyle.Lime, isLoading = working, fullWidth = false, onClick = onApprove)
                YHButton("Delete", icon = Icons.Rounded.Delete, style = YHButtonStyle.Ghost, fullWidth = false, onClick = onDelete)
            }
        }
    }
}

// ---- Photo strip -----------------------------------------------------------------

/**
 * Latest photos atop the wall with an Add button. Photos are Garden Pro: a
 * non-Pro garden renders nothing rather than an upsell taking wall space.
 */
@Composable
private fun PhotoStrip(garden: Garden) {
    val context = LocalContext.current
    var photos by remember(garden.id) { mutableStateOf<List<GalleryPhoto>>(emptyList()) }
    var proRequired by remember(garden.id) { mutableStateOf(false) }
    var uploading by remember { mutableStateOf(false) }
    var uploadError by remember { mutableStateOf<String?>(null) }
    var staged by remember { mutableStateOf<Bitmap?>(null) }
    var viewing by remember { mutableStateOf<GalleryPhoto?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load() {
        try {
            val feed = ApiClient.listGardenPhotos(garden.id)
            photos = feed.photos
            proRequired = feed.proRequired ?: false
        } catch (_: Exception) { /* decorative; the wall works without it */ }
    }
    LaunchedEffect(garden.id) { load() }

    val picker = rememberLauncherForActivityResult(ActivityResultContracts.PickVisualMedia()) { uri: Uri? ->
        if (uri == null) return@rememberLauncherForActivityResult
        uploadError = null
        scope.launch {
            // Read the picked image and open the caption step — nothing is sent yet.
            staged = withContext(Dispatchers.IO) { decodeScaled(context, uri) }
            if (staged == null) uploadError = "Couldn't read that image — try a different one."
        }
    }

    if (proRequired) return
    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            YHSectionLabel("Photos", Modifier.weight(1f).padding(start = 0.dp))
            if (uploading) CircularProgressIndicator(Modifier.size(16.dp), color = YH.ink, strokeWidth = 2.dp)
        }
        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
            Column(
                Modifier.size(84.dp).clip(RoundedCornerShape(YH.Radius.md)).background(YH.lime)
                    .clickable { Haptics.tap(); picker.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center,
            ) {
                Icon(Icons.Rounded.PhotoCamera, null, tint = YH.ink)
                Text("Add", style = YHType.captionMed, color = YH.ink)
            }
            photos.take(12).forEach { p ->
                Box(Modifier.size(84.dp).clip(RoundedCornerShape(YH.Radius.md)).background(YH.surface).clickable { Haptics.tap(); viewing = p },
                    contentAlignment = Alignment.Center) {
                    Icon(Icons.Rounded.Photo, null, tint = YH.muted)
                    AsyncImage(AppEnvironment.mediaUrl(p.url), p.caption, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                    if (p.commentsCount > 0) Icon(Icons.Rounded.ChatBubble, null, tint = Color.White,
                        modifier = Modifier.align(Alignment.BottomEnd).padding(5.dp).size(10.dp))
                }
            }
        }
        uploadError?.let { Text(it, style = YHType.caption, color = YH.danger) }
    }

    staged?.let { bmp ->
        PhotoComposeSheet(bmp, uploading, onDismiss = { if (!uploading) staged = null }) { caption ->
            scope.launch {
                uploading = true
                uploadError = null
                try {
                    val jpeg = withContext(Dispatchers.Default) {
                        ByteArrayOutputStream().use { out -> bmp.compress(Bitmap.CompressFormat.JPEG, 85, out); out.toByteArray() }
                    }
                    ApiClient.uploadGardenPhoto(garden.id, jpeg, caption.trim())
                    staged = null
                    Haptics.success()
                    load()
                } catch (e: Exception) {
                    uploadError = e.userMessage
                    staged = null
                    Haptics.error()
                } finally {
                    uploading = false
                }
            }
        }
    }
    viewing?.let { p -> PhotoDetailSheet(p, onDismiss = { viewing = null }) { scope.launch { load() } } }
}

/** Decode a picked image, downsampled so a 48 MP original doesn't exhaust memory. */
private fun decodeScaled(context: Context, uri: Uri, maxSide: Int = 2048): Bitmap? = try {
    val bounds = BitmapFactory.Options().apply { inJustDecodeBounds = true }
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, bounds) }
    var sample = 1
    while (maxOf(bounds.outWidth, bounds.outHeight) / (sample * 2) >= maxSide) sample *= 2
    context.contentResolver.openInputStream(uri)?.use { BitmapFactory.decodeStream(it, null, BitmapFactory.Options().apply { inSampleSize = sample }) }
} catch (_: Exception) {
    null
}

/** The pause between picking and posting: a preview and a caption. Nothing uploads until Post. */
@Composable
private fun PhotoComposeSheet(image: Bitmap, posting: Boolean, onDismiss: () -> Unit, onPost: (String) -> Unit) {
    var caption by remember { mutableStateOf("") }
    val focus = LocalFocusManager.current
    YHSheet(onDismiss, title = "New Photo", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, enabled = !posting, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            Image(image.asImageBitmap(), null, contentScale = ContentScale.Fit,
                modifier = Modifier.fillMaxWidth().heightIn(max = 420.dp).clip(RoundedCornerShape(YH.Radius.lg)).background(YH.surface))
            YHTextField(caption, { caption = it }, label = "CAPTION", placeholder = "Say something about it… (optional)", singleLine = false, minLines = 2,
                textStyle = YHType.body.copy(color = YH.ink), autoCorrect = true, capitalization = KeyboardCapitalization.Sentences)
            YHButton("Post Photo", icon = Icons.Rounded.Upload, style = YHButtonStyle.Lime, isLoading = posting) { focus.clearFocus(); onPost(caption) }
        }
    }
}

/** One photo, full width, with likes and its comment thread. */
@Composable
private fun PhotoDetailSheet(initial: GalleryPhoto, onDismiss: () -> Unit, onChange: () -> Unit) {
    var photo by remember { mutableStateOf(initial) }
    var comments by remember { mutableStateOf<List<PhotoComment>>(emptyList()) }
    var loaded by remember { mutableStateOf(false) }
    var composer by remember { mutableStateOf("") }
    var posting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var confirmDelete by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) {
        comments = runCatching { ApiClient.listPhotoComments(photo.id) }.getOrDefault(emptyList())
        loaded = true
    }

    YHSheet(
        onDismiss, title = "Photo",
        leading = { YHBarButton("Close", bold = false, color = YH.muted, onClick = onDismiss) },
        trailing = { if (photo.canDelete) YHBarIcon(Icons.Rounded.Delete, "Delete photo", tint = YH.danger) { confirmDelete = true } },
    ) {
        Column(Modifier.fillMaxSize()) {
            Column(Modifier.weight(1f).verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
                Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.lg)).background(YH.surface), contentAlignment = Alignment.Center) {
                    AsyncImage(AppEnvironment.mediaUrl(photo.url), photo.caption, contentScale = ContentScale.FillWidth, modifier = Modifier.fillMaxWidth().heightIn(min = 200.dp))
                }
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                    YHAvatar(photo.userName, size = 32.dp)
                    Column(Modifier.weight(1f)) {
                        Text(photo.userName, style = YHType.bodyMedium, color = YH.ink)
                        photo.uploadedAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
                    }
                    Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable {
                        scope.launch {
                            try {
                                val r = ApiClient.togglePhotoLike(photo.id)
                                photo = photo.copy(likedByMe = r.liked, likesCount = r.likesCount)
                                Haptics.tap()
                                onChange()
                            } catch (_: Exception) {}
                        }
                    }.padding(4.dp), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        Icon(if (photo.likedByMe) Icons.Rounded.Favorite else Icons.Rounded.FavoriteBorder, "Like",
                            tint = if (photo.likedByMe) YH.danger else YH.muted, modifier = Modifier.size(18.dp))
                        if (photo.likesCount > 0) Text("${photo.likesCount}", color = YH.muted, fontWeight = FontWeight.Medium)
                    }
                }
                if (!photo.caption.isNullOrEmpty()) Text(photo.caption!!, style = YHType.subheadline, color = YH.ink)
                HorizontalDivider(color = YH.border)
                YHSectionLabel("Comments", Modifier.padding(start = 0.dp))
                when {
                    !loaded -> YHSkeletonBlock(height = 40.dp)
                    comments.isEmpty() -> Text("No comments yet.", style = YHType.subheadline, color = YH.muted)
                }
                comments.forEach { c ->
                    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        YHAvatar(c.userName, size = 26.dp)
                        Column {
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(c.userName, style = YHType.captionMed, color = YH.ink)
                                c.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
                            }
                            Text(c.content, style = YHType.subheadline, color = YH.ink)
                        }
                    }
                }
                error?.let { Text(it, style = YHType.caption, color = YH.danger) }
            }
            HorizontalDivider(color = YH.border)
            Row(Modifier.padding(horizontal = YH.Space.md, vertical = YH.Space.sm), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
                ComposerField(composer, { composer = it }, "Add a comment…", Modifier.weight(1f), maxLines = 3)
                SendButton(posting, composer.isNotBlank(), 34.dp) {
                    val text = composer.trim()
                    scope.launch {
                        posting = true
                        error = null
                        try {
                            comments = comments + ApiClient.postPhotoComment(photo.id, text)
                            composer = ""
                            photo = photo.copy(commentsCount = photo.commentsCount + 1)
                            Haptics.success()
                            onChange()
                        } catch (e: Exception) {
                            error = e.userMessage
                            Haptics.error()
                        } finally {
                            posting = false
                        }
                    }
                }
            }
        }
    }
    if (confirmDelete) YHConfirmDialog("Delete this photo?", "Its comments go with it. This can't be undone.", "Delete Photo", destructive = true,
        onConfirm = {
            scope.launch {
                try { ApiClient.deleteGardenPhoto(photo.id); Haptics.success(); onChange(); onDismiss() }
                catch (e: Exception) { error = e.userMessage; Haptics.error() }
            }
        }, onDismiss = { confirmDelete = false })
}
