package app.yardharvest.manager.core

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.core.content.edit
import app.yardharvest.manager.api.listNotifications
import app.yardharvest.manager.api.messagesUnreadCount
import app.yardharvest.manager.api.myGardens
import app.yardharvest.manager.api.notificationsUnreadCount
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.MyGardensPayload
import app.yardharvest.manager.model.YHNotification
import java.util.UUID
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Job
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch

/**
 * The user's gardens and the currently selected one. The selection persists
 * so the user lands on the same garden between launches.
 */
class GardenStore {
    var gardens: MyGardensPayload? by mutableStateOf(null)
        private set
    var isLoading by mutableStateOf(false)
        private set
    var lastError: String? by mutableStateOf(null)
        private set

    private var _selected by mutableStateOf(loadSelected())
    var selectedGardenId: Int?
        get() = _selected
        set(value) {
            _selected = value
            AppEnvironment.prefs.edit {
                if (value == null) remove(SELECTED_KEY) else putInt(SELECTED_KEY, value)
            }
        }

    private fun loadSelected(): Int? =
        AppEnvironment.prefs.getInt(SELECTED_KEY, 0).takeIf { it != 0 }

    suspend fun bootstrapIfNeeded() {
        if (gardens != null || isLoading) return
        reload()
    }

    suspend fun reload() {
        isLoading = true
        try {
            val payload = ApiClient.myGardens()
            gardens = payload
            val current = selectedGardenId
            if (current == null || payload.all.none { it.id == current }) {
                selectedGardenId = payload.organized.firstOrNull()?.id ?: payload.all.firstOrNull()?.id
            }
            lastError = null
        } catch (e: Exception) {
            lastError = e.userMessage
        } finally {
            isLoading = false
        }
    }

    val selectedGarden: Garden?
        get() {
            val id = selectedGardenId ?: return null
            return gardens?.all?.firstOrNull { it.id == id }
        }

    /**
     * True when the signed-in user holds ANY admin capability in the active
     * garden — the organizer, or an assigned role. Which screens they get is
     * a per-capability question; ask [can].
     */
    val hasAdminAccess: Boolean
        get() {
            val id = selectedGardenId ?: return false
            val payload = gardens ?: return false
            if (payload.organized.any { it.id == id }) return true
            return !selectedGarden?.userCapabilities.isNullOrEmpty()
        }

    /** Capability names from garden_permissions.py: money, content, resources, roles, … */
    fun can(capability: String): Boolean = selectedGarden?.can(capability) ?: false

    companion object {
        const val SELECTED_KEY = "yh.selectedGardenID"
    }
}

/** In-app alert payload — surfaces a fresh message or notification as a toast. */
data class AppAlert(
    val kind: Kind,
    val title: String,
    val body: String?,
    val id: String = UUID.randomUUID().toString(),
) {
    enum class Kind { Message, Announcement, Alert, Generic }
}

/** Pub-sub for in-app toasts. Auto-dismisses after a few seconds. */
class AppAlertCenter(private val scope: CoroutineScope) {
    var current: AppAlert? by mutableStateOf(null)
        private set
    private var dismissJob: Job? = null

    fun enqueue(alert: AppAlert) {
        dismissJob?.cancel()
        current = alert
        Haptics.confirm()
        dismissJob = scope.launch {
            delay(4_000)
            current = null
        }
    }

    fun dismiss() {
        dismissJob?.cancel()
        current = null
    }
}

/**
 * Polls unread message + notification counts every 60s for the More tab
 * badge, and raises toasts when the counts go up.
 */
class BadgeStore(private val scope: CoroutineScope) {
    var unreadMessages by mutableIntStateOf(0)
        private set
    var unreadNotifications by mutableIntStateOf(0)
        private set
    private var pollJob: Job? = null
    private var hasLoadedOnce = false

    var alertCenter: AppAlertCenter? = null

    val totalUnread: Int get() = unreadMessages + unreadNotifications

    fun startPolling() {
        if (pollJob != null) return
        pollJob = scope.launch {
            while (isActive) {
                refresh()
                delay(60_000)
            }
        }
    }

    fun stopPolling() {
        pollJob?.cancel()
        pollJob = null
    }

    suspend fun refresh() {
        val (m, n) = coroutineScope {
            val msgs = async { runCatching { ApiClient.messagesUnreadCount() }.getOrDefault(0) }
            val notifs = async { runCatching { ApiClient.notificationsUnreadCount() }.getOrDefault(0) }
            msgs.await() to notifs.await()
        }
        val prevMessages = unreadMessages
        val prevNotifications = unreadNotifications
        unreadMessages = m
        unreadNotifications = n

        // The first refresh only sets a baseline — no toast for what was
        // already unread before the app opened.
        if (!hasLoadedOnce) {
            hasLoadedOnce = true
            return
        }
        val center = alertCenter ?: return
        if (m > prevMessages) {
            val delta = m - prevMessages
            center.enqueue(AppAlert(AppAlert.Kind.Message, if (delta == 1) "New message" else "$delta new messages", null))
        }
        if (n > prevNotifications) {
            val delta = n - prevNotifications
            val latest = fetchLatestNotification()
            if (latest != null) {
                center.enqueue(AppAlert(kindFor(latest.type), latest.title, latest.body))
            } else {
                center.enqueue(AppAlert(AppAlert.Kind.Generic, if (delta == 1) "New notification" else "$delta new notifications", null))
            }
        }
    }

    private suspend fun fetchLatestNotification(): YHNotification? = try {
        ApiClient.listNotifications(page = 1, perPage = 1, unreadOnly = true).notifications.firstOrNull()
    } catch (_: Exception) {
        null
    }

    private fun kindFor(type: String?) = when (type) {
        "announcement" -> AppAlert.Kind.Announcement
        "weather_alert", "alert" -> AppAlert.Kind.Alert
        "message" -> AppAlert.Kind.Message
        else -> AppAlert.Kind.Generic
    }

    fun notificationWasRead() { unreadNotifications = maxOf(0, unreadNotifications - 1) }
    fun allNotificationsRead() { unreadNotifications = 0 }
    fun threadWasRead(unread: Int) { unreadMessages = maxOf(0, unreadMessages - unread) }
}

val LocalGardenStore = staticCompositionLocalOf<GardenStore> { error("No GardenStore") }
val LocalBadgeStore = staticCompositionLocalOf<BadgeStore> { error("No BadgeStore") }
val LocalAlertCenter = staticCompositionLocalOf<AppAlertCenter> { error("No AppAlertCenter") }
