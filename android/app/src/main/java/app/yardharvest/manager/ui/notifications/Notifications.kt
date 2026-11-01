package app.yardharvest.manager.ui.notifications

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Campaign
import androidx.compose.material.icons.rounded.ChatBubble
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.NotificationsOff
import androidx.compose.material.icons.rounded.ShoppingBasket
import androidx.compose.material.icons.rounded.Verified
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
import app.yardharvest.manager.api.listNotifications
import app.yardharvest.manager.api.markAllNotificationsRead
import app.yardharvest.manager.api.markNotificationRead
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalBadgeStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.YHNotification
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHType
import kotlinx.coroutines.launch

/** Notification list state shared by the pushed screen and the sheet. */
private class NotificationsState {
    var items by mutableStateOf<List<YHNotification>>(emptyList())
    var loading by mutableStateOf(false)
    var error by mutableStateOf<String?>(null)

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { items = ApiClient.listNotifications(perPage = 50).notifications } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
}

@Composable
fun NotificationsScreen() {
    val state = remember { NotificationsState() }
    val badges = LocalBadgeStore.current
    val scope = rememberCoroutineScope()
    YHScreen("Notifications", actions = {
        if (state.items.any { !it.isRead }) YHBarButton("Mark all read") { scope.launch { markAll(state); badges.allNotificationsRead() } }
    }) { NotificationsList(state) }
}

/** The bell on the Garden tab presents notifications as a sheet. */
@Composable
fun NotificationsSheet(onDismiss: () -> Unit) {
    val state = remember { NotificationsState() }
    val badges = LocalBadgeStore.current
    val scope = rememberCoroutineScope()
    YHSheet(
        onDismiss, title = "Notifications",
        leading = {
            if (state.items.any { !it.isRead }) YHBarButton("Mark all read", bold = false) { scope.launch { markAll(state); badges.allNotificationsRead() } }
        },
        trailing = { YHBarButton("Done", onClick = onDismiss) },
    ) { NotificationsList(state) }
}

private suspend fun markAll(state: NotificationsState) {
    try {
        ApiClient.markAllNotificationsRead()
        state.items = state.items.map { it.copy(isRead = true) }
        Haptics.success()
    } catch (_: Exception) {}
}

@Composable
private fun NotificationsList(state: NotificationsState) {
    val badges = LocalBadgeStore.current
    val scope = rememberCoroutineScope()
    LaunchedEffect(Unit) { state.load() }
    YHLoadable(state.loading, state.items.isEmpty(), state.error, { scope.launch { state.load() } },
        empty = { YHEmpty(Icons.Rounded.NotificationsOff, "You're all caught up", "Notifications about your gardens show up here.") }) {
        YHRefreshable({ state.load(false) }) {
            LazyColumn(
                Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(YH.Space.md),
                verticalArrangement = Arrangement.spacedBy(YH.Space.sm),
            ) {
                items(state.items, key = { it.id }) { n ->
                    NotificationRow(n) {
                        if (n.isRead) return@NotificationRow
                        scope.launch {
                            try {
                                ApiClient.markNotificationRead(n.id)
                                state.items = state.items.map { if (it.id == n.id) it.copy(isRead = true) else it }
                                badges.notificationWasRead()
                                Haptics.selection()
                            } catch (_: Exception) {}
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun NotificationRow(n: YHNotification, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(
                Modifier.size(32.dp).clip(RoundedCornerShape(9.dp)).background(if (n.isRead) YH.surface else YH.lime),
                contentAlignment = Alignment.Center,
            ) { Icon(iconFor(n.type), null, tint = YH.ink, modifier = Modifier.size(16.dp)) }
            Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text(n.title, style = if (n.isRead) YHType.body else YHType.bodyMedium, color = YH.ink)
                n.body?.let { Text(it, style = YHType.subheadline, color = YH.muted, maxLines = 2) }
                n.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.tertiary) }
            }
            if (!n.isRead) Box(Modifier.padding(top = 6.dp).size(8.dp).clip(CircleShape).background(YH.ink))
        }
    }
}

private fun iconFor(type: String?) = when (type) {
    "announcement" -> Icons.Rounded.Campaign
    "event" -> Icons.Rounded.CalendarMonth
    "message" -> Icons.Rounded.ChatBubble
    "harvest" -> Icons.Rounded.ShoppingBasket
    "waitlist" -> Icons.Rounded.HourglassTop
    "plot_assigned", "plot_confirmed" -> Icons.Rounded.Verified
    "shift_reminder", "shift_signup" -> Icons.Rounded.Group
    else -> Icons.Rounded.Notifications
}
