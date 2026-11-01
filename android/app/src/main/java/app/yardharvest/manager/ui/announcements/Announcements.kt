package app.yardharvest.manager.ui.announcements

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Campaign
import androidx.compose.material.icons.rounded.EditNote
import androidx.compose.material.icons.rounded.Email
import androidx.compose.material.icons.rounded.PushPin
import androidx.compose.material.icons.rounded.Sms
import androidx.compose.material.icons.rounded.SwapVert
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
import androidx.compose.ui.unit.dp
import app.yardharvest.manager.api.createAnnouncement
import app.yardharvest.manager.api.listAnnouncements
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Announcement
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHContentReveal
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonCard
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHToggleRow
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.GardenPickerSheet
import kotlinx.coroutines.launch

/** Announcements tab root: the selected garden's announcements. */
@Composable
fun AnnouncementsTab() {
    val store = LocalGardenStore.current
    var showPicker by remember { mutableStateOf(false) }
    var showCompose by remember { mutableStateOf(false) }
    val garden = store.selectedGarden
    YHScreen(
        "Announcements", showBack = false,
        actions = {
            if (garden != null) YHBarIcon(Icons.Rounded.EditNote, "New announcement", tint = YH.ink) { showCompose = true }
            YHBarIcon(Icons.Rounded.SwapVert, "Switch garden") { showPicker = true }
        },
    ) {
        when {
            garden != null -> AnnouncementsContent(garden, showCompose) { showCompose = it }
            store.isLoading -> Box(Modifier.padding(16.dp)) { YHSkeletonCard() }
            else -> YHEmpty(Icons.Rounded.Campaign, "No garden selected", "Pick a garden to view announcements.")
        }
    }
    if (showPicker) GardenPickerSheet { showPicker = false }
}

/** Announcements pushed from the dashboard or the More tab. */
@Composable
fun AnnouncementsScreen(garden: Garden) {
    var showCompose by remember { mutableStateOf(false) }
    YHScreen("Announcements", actions = { YHBarIcon(Icons.Rounded.EditNote, "New announcement", tint = YH.ink) { showCompose = true } }) {
        AnnouncementsContent(garden, showCompose) { showCompose = it }
    }
}

@Composable
private fun ColumnScope.AnnouncementsContent(garden: Garden, showCompose: Boolean, setCompose: (Boolean) -> Unit) {
    var items by remember(garden.id) { mutableStateOf<List<Announcement>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { items = ApiClient.listAnnouncements(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    YHLoadable(loading, items.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3, skeletonRows = 3,
        empty = { YHEmpty(Icons.Rounded.Campaign, "Nothing posted yet", "Tap + to share an update with members.", actionTitle = "Post Announcement") { setCompose(true) } }) {
        YHContentReveal(Icons.Rounded.Campaign, id = "announcements-${garden.id}", caption = "Fresh from your garden") {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    items(items, key = { it.id }) { AnnouncementCard(it) }
                }
            }
        }
    }
    if (showCompose) ComposeAnnouncementSheet(garden, onDismiss = { setCompose(false) }) { items = listOf(it) + items }
}

@Composable
private fun AnnouncementCard(a: Announcement) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                if (a.pinned == true) {
                    Box(Modifier.size(22.dp).clip(CircleShape).background(YH.lime), contentAlignment = Alignment.Center) {
                        Icon(Icons.Rounded.PushPin, null, tint = YH.ink, modifier = Modifier.size(12.dp))
                    }
                }
                Text(a.title, style = YHType.title3, color = YH.ink)
            }
            Text(a.body, style = YHType.body, color = YH.ink.copy(alpha = 0.85f))
            val meta = listOfNotNull(a.authorName, a.createdAt?.let { Fmt.relative(it) })
            if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = YHType.caption, color = YH.muted)
        }
    }
}

@Composable
private fun ComposeAnnouncementSheet(garden: Garden, onDismiss: () -> Unit, onCreate: (Announcement) -> Unit) {
    var title by remember { mutableStateOf("") }
    var body by remember { mutableStateOf("") }
    var sendEmail by remember { mutableStateOf(true) }
    var sendSms by remember { mutableStateOf(false) }
    var posting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    YHSheet(onDismiss, title = "New Announcement", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHTextField(title, { title = it }, label = "Title", textStyle = YHType.body.copy(color = YH.ink), autoCorrect = true,
                capitalization = androidx.compose.ui.text.input.KeyboardCapitalization.Sentences)
            YHTextField(body, { body = it }, label = "Message", singleLine = false, minLines = 6, textStyle = YHType.body.copy(color = YH.ink),
                autoCorrect = true, capitalization = androidx.compose.ui.text.input.KeyboardCapitalization.Sentences)
            YHCard(padding = 4.dp) {
                YHToggleRow("Send email", sendEmail, icon = Icons.Rounded.Email) { sendEmail = it }
                YHToggleRow("Send SMS", sendSms, icon = Icons.Rounded.Sms) { sendSms = it }
            }
            error?.let { YHInlineError(it) }
            YHButton("Post", icon = Icons.AutoMirrored.Rounded.Send, isLoading = posting, enabled = title.isNotEmpty() && body.isNotEmpty()) {
                scope.launch {
                    posting = true
                    error = null
                    try {
                        onCreate(ApiClient.createAnnouncement(garden.id, title, body, sendEmail, sendSms))
                        Haptics.success()
                        onDismiss()
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
