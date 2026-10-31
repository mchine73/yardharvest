package app.yardharvest.manager.core

import android.Manifest
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import app.yardharvest.manager.BuildConfig
import app.yardharvest.manager.MainActivity
import app.yardharvest.manager.R
import app.yardharvest.manager.api.registerDeviceToken
import com.google.firebase.messaging.FirebaseMessaging
import com.google.firebase.messaging.FirebaseMessagingService
import com.google.firebase.messaging.RemoteMessage
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.tasks.await

/**
 * Push on the client side: permission, FCM registration, foreground
 * presentation, and tap routing — the counterpart of the iOS PushManager.
 *
 * The server half (`app/push_service.py`) fans out of `notify()`, so any
 * in-app notification the backend creates also reaches the phone. Payloads
 * carry `type`, `link`, and `garden_id`; a tap parks them in [pendingRoute],
 * which the home shell consumes to switch tabs.
 */
object PushManager {
    data class PushRoute(val type: String, val link: String, val gardenId: Int?)

    const val CHANNEL_ID = "garden_updates"

    /** The tapped notification waiting to be routed. */
    var pendingRoute: PushRoute? by mutableStateOf(null)

    /** Push needs a Firebase project; builds without one simply don't register. */
    val isAvailable: Boolean get() = BuildConfig.PUSH_CONFIGURED

    private lateinit var appContext: Context
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    fun init(context: Context) {
        appContext = context.applicationContext
        val channel = NotificationChannel(
            CHANNEL_ID,
            context.getString(R.string.notification_channel_general),
            NotificationManager.IMPORTANCE_HIGH,
        ).apply { description = context.getString(R.string.notification_channel_general_desc) }
        context.getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    /** Whether the POST_NOTIFICATIONS runtime permission still needs asking (Android 13+). */
    fun needsPermissionPrompt(context: Context): Boolean =
        Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(context, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED

    /**
     * Fetch the FCM token and register it with the backend. Safe on every
     * sign-in: it keeps the server's copy fresh.
     */
    suspend fun register() {
        if (!isAvailable) return
        try {
            val token = FirebaseMessaging.getInstance().token.await()
            ApiClient.registerDeviceToken(token)
        } catch (_: Exception) {
            // No Play services, or offline: the in-app poll still covers updates.
        }
    }

    /** Called when FCM rotates the token. */
    fun onNewToken(token: String) {
        if (AuthManager.currentUser == null) return
        scope.launch { runCatching { ApiClient.registerDeviceToken(token) } }
    }

    /** Read a route out of a launch intent built by FCM or by [show]. */
    fun routeFrom(intent: Intent?): PushRoute? {
        val extras = intent?.extras ?: return null
        val type = extras.getString("type") ?: return null
        val gardenId = extras.getString("garden_id")?.toIntOrNull()
            ?: extras.getInt("garden_id", -1).takeIf { it >= 0 }
        return PushRoute(type, extras.getString("link") ?: "", gardenId)
    }

    /**
     * Foreground pushes still show as a system notification — the in-app
     * toast covers polled updates, but a push can beat the poll and
     * shouldn't vanish.
     */
    fun show(message: RemoteMessage) {
        val ctx = appContext
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED
        ) return
        val title = message.notification?.title ?: message.data["title"] ?: return
        val body = message.notification?.body ?: message.data["body"]
        val intent = Intent(ctx, MainActivity::class.java).apply {
            flags = Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP
            message.data.forEach { (k, v) -> putExtra(k, v) }
        }
        val pending = PendingIntent.getActivity(
            ctx, message.messageId?.hashCode() ?: 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE,
        )
        val notification = NotificationCompat.Builder(ctx, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_leaf)
            .setColor(ContextCompat.getColor(ctx, R.color.yh_ink))
            .setContentTitle(title)
            .setContentText(body)
            .setStyle(NotificationCompat.BigTextStyle().bigText(body))
            .setAutoCancel(true)
            .setContentIntent(pending)
            .build()
        NotificationManagerCompat.from(ctx).notify(System.currentTimeMillis().toInt(), notification)
    }

    /** The app is in front — what the notification shade held has been seen. */
    fun clearDelivered() {
        if (::appContext.isInitialized) NotificationManagerCompat.from(appContext).cancelAll()
    }
}

/** FCM entry point (declared in the manifest). */
class YHMessagingService : FirebaseMessagingService() {
    override fun onNewToken(token: String) = PushManager.onNewToken(token)
    override fun onMessageReceived(message: RemoteMessage) = PushManager.show(message)
}
