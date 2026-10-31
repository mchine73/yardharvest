package app.yardharvest.manager.ui.inbox

import android.content.ActivityNotFoundException
import android.content.Intent
import android.net.Uri
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.ArrowUpward
import androidx.compose.material.icons.rounded.Eco
import androidx.compose.material.icons.rounded.EditNote
import androidx.compose.material.icons.rounded.Email
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.Schedule
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
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import app.yardharvest.manager.api.inbox
import app.yardharvest.manager.api.listGardenMembers
import app.yardharvest.manager.api.sendMessage
import app.yardharvest.manager.api.thread
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalBadgeStore
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.InboxThread
import app.yardharvest.manager.model.YHMessage
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHContentReveal
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHErrorState
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonBlock
import app.yardharvest.manager.ui.brand.YHSkeletonCard
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import java.time.Instant
import java.util.UUID
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private const val SUPPORT_EMAIL = "james@yardharvest.app"
private const val SUPPORT_SUBJECT = "YardHarvest support"

/** Threaded inbox. The "+" opens a peer picker with a YardHarvest Admin email shortcut. */
@Composable
fun InboxScreen() {
    val nav = LocalNav.current
    val badges = LocalBadgeStore.current
    val context = LocalContext.current
    var threads by remember { mutableStateOf<List<InboxThread>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showPicker by remember { mutableStateOf(false) }
    var toast by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { threads = ApiClient.inbox() } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(Unit) { load() }
    val refreshAfterChange: () -> Unit = { scope.launch { badges.refresh(); load(false) } }

    fun showToast(text: String) {
        scope.launch { toast = text; delay(2400); toast = null }
    }

    fun openAdminMail() {
        val uri = "mailto:$SUPPORT_EMAIL?subject=${Uri.encode(SUPPORT_SUBJECT)}".toUri()
        try {
            context.startActivity(Intent(Intent.ACTION_SENDTO, uri))
        } catch (_: ActivityNotFoundException) {
            showToast("No email app is set up on this device.")
        }
    }

    YHScreen("Messages", actions = { YHBarIcon(Icons.Rounded.EditNote, "New message", tint = YH.ink) { showPicker = true } }) {
        Box(Modifier.fillMaxSize()) {
            YHLoadable(loading, threads.isEmpty(), error, { scope.launch { load() } },
                empty = { YHEmpty(Icons.Rounded.Forum, "No messages yet", "Conversations with members and organizers show up here.") }) {
                YHContentReveal(Icons.Rounded.Forum, id = "inbox", caption = "Your conversations") {
                    YHRefreshable({ load(false) }) {
                        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                            items(threads, key = { it.threadId }) { t ->
                                InboxRow(t) { nav.push(Dest.Thread(t.otherUser.id, t.otherUser.displayName, t, refreshAfterChange)) }
                            }
                        }
                    }
                }
            }
            InboxToast(toast)
        }
    }

    if (showPicker) NewMessagePickerSheet(onDismiss = { showPicker = false }) { dest ->
        showPicker = false
        when (dest) {
            is PickerDestination.Peer -> {
                // An existing conversation shows its history; otherwise start a
                // fresh thread that the first send materializes server-side.
                val existing = threads.firstOrNull { it.otherUser.id == dest.userId }
                nav.push(Dest.Thread(dest.userId, dest.name, existing, refreshAfterChange))
            }
            PickerDestination.Admin -> openAdminMail()
        }
    }
}

/** A short notice at the top of the inbox (e.g. no email app installed). */
@Composable
private fun InboxToast(text: String?) {
    Box(Modifier.fillMaxSize().padding(top = 8.dp), contentAlignment = Alignment.TopCenter) {
        AnimatedVisibility(text != null, enter = slideInVertically() + fadeIn(), exit = slideOutVertically() + fadeOut()) {
            Text(text ?: "", style = YHType.captionMed, color = YH.ink,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 14.dp, vertical = 8.dp))
        }
    }
}

@Composable
private fun InboxRow(t: InboxThread, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            YHAvatar(t.otherUser.displayName, size = 44.dp)
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Row {
                    Text(t.otherUser.displayName, style = if (t.unread > 0) YHType.bodyMedium else YHType.body, color = YH.ink, modifier = Modifier.weight(1f))
                    t.lastMessage.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
                }
                Text(t.lastMessage.body, style = YHType.subheadline, color = if (t.unread > 0) YH.ink else YH.muted, maxLines = 2)
            }
            if (t.unread > 0) {
                Text("${t.unread}", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = YH.ink,
                    modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 8.dp, vertical = 3.dp))
            }
        }
    }
}

// ---- Thread ----------------------------------------------------------------------

/** A real message or an optimistic stub while a send is in flight. */
private data class DisplayMessage(val key: String, val pending: Boolean, val body: String, val createdAt: Instant?, val senderId: Int) {
    companion object {
        fun of(m: YHMessage) = DisplayMessage("r${m.id}", false, m.body, m.createdAt, m.senderId)
    }
}

/**
 * Chat-style conversation: outgoing bubbles in ink, incoming in surface gray,
 * composer above the keyboard. [thread] is null for a brand-new conversation.
 */
@Composable
fun ThreadScreen(recipientId: Int, recipientName: String, thread: InboxThread?, onChange: () -> Unit) {
    val badges = LocalBadgeStore.current
    val me = AuthManager.currentUser?.id
    var messages by remember { mutableStateOf<List<DisplayMessage>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var draft by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val scope = rememberCoroutineScope()

    suspend fun load() {
        val t = thread ?: return // brand-new conversation: nothing to fetch
        loading = true
        error = null
        try {
            messages = ApiClient.thread(t.threadId).messages.map(DisplayMessage::of)
            badges.threadWasRead(t.unread)
            onChange()
        } catch (e: Exception) {
            error = e.userMessage
        } finally {
            loading = false
        }
    }
    LaunchedEffect(recipientId) { load() }
    LaunchedEffect(messages.size) { if (messages.isNotEmpty()) listState.animateScrollToItem(messages.lastIndex) }

    fun send() {
        val body = draft.trim()
        if (body.isEmpty() || sending || me == null) return
        val pending = DisplayMessage("p${UUID.randomUUID()}", true, body, Instant.now(), me)
        // Optimistic: the bubble appears at once and is swapped on success.
        draft = ""
        error = null
        sending = true
        messages = messages + pending
        scope.launch {
            try {
                val sent = ApiClient.sendMessage(recipientId, body, thread?.listing?.id)
                messages = messages.map { if (it.key == pending.key) DisplayMessage.of(sent) else it }
                Haptics.success()
                onChange()
            } catch (e: Exception) {
                messages = messages.filter { it.key != pending.key }
                draft = body // restore so nothing is lost
                error = e.userMessage
                Haptics.error()
            } finally {
                sending = false
            }
        }
    }

    YHScreen(recipientName) {
        Column(Modifier.fillMaxSize().imePadding()) {
            Box(Modifier.weight(1f)) {
                when {
                    messages.isEmpty() && loading -> Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        repeat(4) { YHSkeletonBlock(height = 44.dp) }
                    }
                    messages.isEmpty() && error != null -> YHErrorState(error!!) { scope.launch { load() } }
                    messages.isEmpty() -> Column(
                        Modifier.fillMaxSize().padding(16.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                        verticalArrangement = Arrangement.spacedBy(YH.Space.md, Alignment.CenterVertically),
                    ) {
                        YHAvatar(recipientName, size = 76.dp)
                        Text("Say hi to $recipientName", style = YHType.title3, color = YH.ink)
                        Text("This is the start of your conversation.", style = YHType.subheadline, color = YH.muted)
                    }
                    else -> LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = PaddingValues(YH.Space.md)) {
                        itemsIndexed(messages, key = { _, m -> m.key }) { i, m ->
                            val prev = messages.getOrNull(i - 1)
                            val next = messages.getOrNull(i + 1)
                            Bubble(
                                m, isMine = m.senderId == me,
                                firstInGroup = prev?.senderId != m.senderId,
                                lastInGroup = next?.senderId != m.senderId,
                            )
                        }
                    }
                }
            }
            // Composer
            Column(Modifier.fillMaxWidth().background(YH.canvas)) {
                androidx.compose.material3.HorizontalDivider(color = YH.border)
                Row(Modifier.padding(horizontal = YH.Space.md, vertical = YH.Space.sm), verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val shape = RoundedCornerShape(20.dp)
                    BasicTextField(
                        draft, { draft = it }, maxLines = 5,
                        textStyle = YHType.body.copy(color = YH.ink),
                        cursorBrush = SolidColor(YH.ink),
                        keyboardOptions = KeyboardOptions(capitalization = KeyboardCapitalization.Sentences),
                        modifier = Modifier.weight(1f),
                        decorationBox = { inner ->
                            Box(Modifier.clip(shape).background(YH.surface).border(1.dp, YH.border, shape).padding(horizontal = 14.dp, vertical = 10.dp)) {
                                if (draft.isEmpty()) Text("Message", style = YHType.body, color = YH.muted)
                                inner()
                            }
                        },
                    )
                    val canSend = draft.isNotBlank()
                    Box(
                        Modifier.size(40.dp).clip(CircleShape).background(if (canSend) YH.ink else YH.surface)
                            .clickable(enabled = canSend && !sending) { send() },
                        contentAlignment = Alignment.Center,
                    ) {
                        Icon(if (sending) Icons.Rounded.MoreHoriz else Icons.Rounded.ArrowUpward, "Send",
                            tint = if (canSend) Color.White else YH.muted, modifier = Modifier.size(18.dp))
                    }
                }
                error?.takeIf { messages.isNotEmpty() }?.let {
                    Text(it, style = YHType.caption, color = YH.danger, modifier = Modifier.padding(start = YH.Space.md, end = YH.Space.md, bottom = YH.Space.xs))
                }
            }
        }
    }
}

@Composable
private fun Bubble(m: DisplayMessage, isMine: Boolean, firstInGroup: Boolean, lastInGroup: Boolean) {
    val big = 18.dp
    val small = 6.dp
    // Stacked-bubble shape: corners shrink on the sender's side within a group.
    val shape = if (isMine) RoundedCornerShape(topStart = big, topEnd = if (firstInGroup) big else small, bottomEnd = if (lastInGroup) big else small, bottomStart = big)
    else RoundedCornerShape(topStart = if (firstInGroup) big else small, topEnd = big, bottomEnd = big, bottomStart = if (lastInGroup) big else small)
    Row(Modifier.fillMaxWidth().padding(top = if (firstInGroup) 6.dp else 1.dp), horizontalArrangement = if (isMine) Arrangement.End else Arrangement.Start) {
        if (isMine) Spacer(Modifier.size(56.dp, 1.dp))
        Column(horizontalAlignment = if (isMine) Alignment.End else Alignment.Start, verticalArrangement = Arrangement.spacedBy(3.dp)) {
            Text(
                m.body, style = YHType.body, color = if (isMine) Color.White else YH.ink,
                modifier = Modifier.widthIn(max = 300.dp).alpha(if (m.pending) 0.6f else 1f).clip(shape)
                    .background(if (isMine) YH.ink else YH.surface).padding(horizontal = 14.dp, vertical = 10.dp),
            )
            if (lastInGroup && m.createdAt != null) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    if (m.pending) Icon(Icons.Rounded.Schedule, null, tint = YH.muted, modifier = Modifier.size(10.dp))
                    Text(Fmt.time(m.createdAt), fontSize = 10.sp, fontWeight = FontWeight.Medium, color = YH.muted)
                }
            }
        }
        if (!isMine) Spacer(Modifier.size(56.dp, 1.dp))
    }
}

// ---- Compose & pick ------------------------------------------------------------------

/** New message to a specific recipient (e.g. a garden's organizer). */
@Composable
fun ComposeMessageSheet(recipientId: Int, recipientName: String, contextLabel: String? = null, onDismiss: () -> Unit, onSent: () -> Unit) {
    var body by remember { mutableStateOf("") }
    var sending by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val focus = remember { FocusRequester() }
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { delay(350); runCatching { focus.requestFocus() } }

    YHSheet(onDismiss, title = "New Message", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    YHSectionLabel("To", Modifier.padding(start = 0.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        YHAvatar(recipientName, size = 36.dp)
                        Text(recipientName, style = YHType.bodyMedium, color = YH.ink)
                    }
                    if (contextLabel != null) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Icon(Icons.Rounded.Eco, null, tint = YH.muted, modifier = Modifier.size(12.dp))
                            Text(contextLabel, style = YHType.caption, color = YH.muted)
                        }
                    }
                }
            }
            YHCard {
                YHSectionLabel("Message", Modifier.padding(start = 0.dp, bottom = 8.dp))
                YHTextField(body, { body = it }, singleLine = false, minLines = 7, textStyle = YHType.body.copy(color = YH.ink),
                    autoCorrect = true, capitalization = KeyboardCapitalization.Sentences, modifier = Modifier.focusRequester(focus))
            }
            error?.let { YHInlineError(it) }
            YHButton("Send", icon = Icons.AutoMirrored.Rounded.Send, isLoading = sending, enabled = body.isNotBlank()) {
                scope.launch {
                    sending = true
                    error = null
                    try {
                        ApiClient.sendMessage(recipientId, body.trim())
                        Haptics.success()
                        onSent()
                        onDismiss()
                    } catch (e: Exception) {
                        error = e.userMessage
                        Haptics.error()
                    } finally {
                        sending = false
                    }
                }
            }
        }
    }
}

sealed interface PickerDestination {
    data class Peer(val userId: Int, val name: String) : PickerDestination
    data object Admin : PickerDestination
}

private data class PeerRow(val userId: Int, val name: String, val isOrganizer: Boolean, val gardens: List<String>, val plotNumber: String?)

/**
 * Recipient picker: a pinned "YardHarvest Admin" contact (opens email), then
 * peers from every garden the user belongs to, deduplicated and searchable.
 */
@Composable
private fun NewMessagePickerSheet(onDismiss: () -> Unit, onSelected: (PickerDestination) -> Unit) {
    val gardenStore = LocalGardenStore.current
    val me = AuthManager.currentUser?.id
    var peers by remember { mutableStateOf<List<PeerRow>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var search by remember { mutableStateOf("") }

    LaunchedEffect(Unit) {
        val gardens = gardenStore.gardens?.all.orEmpty()
        if (gardens.isEmpty()) return@LaunchedEffect
        loading = true
        // All rosters in parallel.
        val rosters = coroutineScope {
            gardens.map { g -> async { g.name to runCatching { ApiClient.listGardenMembers(g.id) }.getOrDefault(emptyList()) } }.awaitAll()
        }
        val bucket = linkedMapOf<Int, PeerRow>()
        for ((gardenName, members) in rosters) {
            for (m in members) {
                if (m.userId == me) continue
                val existing = bucket[m.userId]
                bucket[m.userId] = if (existing == null) PeerRow(m.userId, m.name, m.isOrganizer, listOf(gardenName), m.plotNumber)
                else if (gardenName in existing.gardens) existing
                else existing.copy(isOrganizer = existing.isOrganizer || m.isOrganizer, gardens = existing.gardens + gardenName,
                    plotNumber = existing.plotNumber ?: m.plotNumber)
            }
        }
        peers = bucket.values.sortedBy { it.name }
        loading = false
    }
    val filtered = if (search.isEmpty()) peers else peers.filter {
        it.name.lowercase().contains(search.lowercase()) || it.gardens.joinToString(" ").lowercase().contains(search.lowercase())
    }

    YHSheet(onDismiss, title = "New Message", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        YHTextField(search, { search = it }, placeholder = "Search peers", textStyle = YHType.body.copy(color = YH.ink),
            modifier = Modifier.padding(horizontal = YH.Space.md, vertical = 8.dp))
        LazyColumn(contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            item { YHSectionLabel("Support") }
            item {
                YHCard(onClick = { onSelected(PickerDestination.Admin) }) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Box(Modifier.size(44.dp).clip(RoundedCornerShape(14.dp)).background(YH.ink), contentAlignment = Alignment.Center) {
                            Icon(Icons.Rounded.Email, null, tint = YH.lime)
                        }
                        Column(Modifier.weight(1f)) {
                            Text("YardHarvest Admin", style = YHType.bodyMedium, color = YH.ink)
                            Text("Email $SUPPORT_EMAIL", style = YHType.caption, color = YH.muted)
                        }
                        Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, tint = YH.muted, modifier = Modifier.size(16.dp))
                    }
                }
            }
            item { YHSectionLabel("From your gardens", Modifier.padding(top = 8.dp)) }
            when {
                loading -> items(3) { YHSkeletonCard(rows = 1) }
                peers.isEmpty() -> item {
                    YHCard {
                        Text("No peers yet", style = YHType.bodyMedium, color = YH.ink)
                        Text("Join a garden to message its members.", style = YHType.subheadline, color = YH.muted)
                    }
                }
                filtered.isEmpty() -> item { YHCard { Text("No matches for “$search”.", style = YHType.subheadline, color = YH.muted) } }
                else -> items(filtered, key = { it.userId }) { p ->
                    YHCard(onClick = { onSelected(PickerDestination.Peer(p.userId, p.name)) }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHAvatar(p.name, size = 44.dp)
                            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(3.dp)) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    Text(p.name, style = YHType.bodyMedium, color = YH.ink)
                                    if (p.isOrganizer) YHPill("Organizer", tint = YH.ink, background = YH.lime)
                                }
                                val gardens = p.gardens.joinToString(" · ")
                                Text(if (!p.plotNumber.isNullOrEmpty()) "Plot ${p.plotNumber} · $gardens" else gardens,
                                    style = YHType.caption, color = YH.muted, maxLines = 1)
                            }
                            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                        }
                    }
                }
            }
        }
    }
}
