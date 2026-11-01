package app.yardharvest.manager

import android.content.Intent
import android.os.Build
import android.os.Bundle
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.fragment.app.FragmentActivity
import app.yardharvest.manager.core.AppLock
import app.yardharvest.manager.core.DeepLinks
import app.yardharvest.manager.core.PushManager
import app.yardharvest.manager.ui.YardHarvestRoot

class MainActivity : FragmentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // The lime/Onest skin is light-first, as on iOS: dark icons on light bars.
        enableEdgeToEdge(
            statusBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
            navigationBarStyle = SystemBarStyle.light(android.graphics.Color.TRANSPARENT, android.graphics.Color.TRANSPARENT),
        )
        super.onCreate(savedInstanceState)
        AppLock.attach(this)
        handle(intent)
        setContent { YardHarvestRoot() }
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    override fun onResume() {
        super.onResume()
        // With the app lock on, keep the member list and payments out of the
        // recents thumbnail too — the other place a glance could leak them.
        if (Build.VERSION.SDK_INT >= 33) setRecentsScreenshotEnabled(!AppLock.shared.isEnabled)
    }

    private fun handle(intent: Intent?) {
        PushManager.routeFrom(intent)?.let { PushManager.pendingRoute = it }
        DeepLinks.from(intent?.data)?.let { DeepLinks.pending = it }
    }
}
