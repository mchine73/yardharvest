package app.yardharvest.manager.ui.home

import android.Manifest
import androidx.activity.compose.BackHandler
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
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
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Campaign
import androidx.compose.material.icons.rounded.ChatBubble
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Handyman
import androidx.compose.material.icons.rounded.Home
import androidx.compose.material.icons.rounded.MoreHoriz
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.Badge
import androidx.compose.material3.BadgedBox
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.NavigationBarItemDefaults
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import app.yardharvest.manager.core.AppAlert
import app.yardharvest.manager.core.AppAlertCenter
import app.yardharvest.manager.core.BadgeStore
import app.yardharvest.manager.core.DeepLinks
import app.yardharvest.manager.core.GardenStore
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalAlertCenter
import app.yardharvest.manager.core.LocalBadgeStore
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.PushManager
import app.yardharvest.manager.model.AuthUser
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.NavHost
import app.yardharvest.manager.ui.nav.NavStack
import app.yardharvest.manager.ui.nav.RouteContent
import app.yardharvest.manager.ui.tools.ScanRequests
import kotlinx.coroutines.launch

private enum class Tab(val label: String) { Garden("Garden"), Tools("Tools"), Announcements("Announcements"), More("More") }

/**
 * Top-level tab shell after sign-in — Garden / Tools / Announcements / More,
 * the same four-tab IA as the web's primary nav and the iOS app.
 *
 * Owns the badge poll and the toast bus. New messages and announcement-style
 * notifications surface as a toast floating above the active tab.
 */
@Composable
fun HomeShell(user: AuthUser) {
    val scope = rememberCoroutineScope()
    val gardenStore = remember(user.id) { GardenStore() }
    val alerts = remember { AppAlertCenter(scope) }
    val badges = remember { BadgeStore(scope) }
    var tab by rememberSaveable { mutableIntStateOf(Tab.Garden.ordinal) }
    val stacks = remember {
        listOf(NavStack(Dest.GardenTab), NavStack(Dest.ToolsTab), NavStack(Dest.AnnouncementsTab), NavStack(Dest.MoreTab))
    }

    val notifPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) {
        scope.launch { PushManager.register() }
    }
    val context = LocalContext.current

    fun route(type: String) {
        tab = when (type) {
            "announcement" -> Tab.Announcements.ordinal
            "comment_flagged" -> Tab.Garden.ordinal // moderation lives off the wall
            else -> Tab.More.ordinal
        }
    }

    LaunchedEffect(Unit) {
        // Wire the badge poll to the toast bus before polling, so the first
        // delta has somewhere to land.
        badges.alertCenter = alerts
        gardenStore.bootstrapIfNeeded()
        badges.startPolling()
        // Signed in and home — the moment to ask about notifications.
        if (PushManager.isAvailable && PushManager.needsPermissionPrompt(context)) {
            notifPermission.launch(Manifest.permission.POST_NOTIFICATIONS)
        } else {
            PushManager.register()
        }
    }
    DisposableEffect(Unit) { onDispose { badges.stopPolling() } }

    // A tapped push, cold start or warm.
    val pendingRoute = PushManager.pendingRoute
    LaunchedEffect(pendingRoute) {
        val r = pendingRoute ?: return@LaunchedEffect
        PushManager.pendingRoute = null
        route(r.type)
    }

    // Launcher shortcuts.
    val pendingLink = DeepLinks.pending
    LaunchedEffect(pendingLink, gardenStore.selectedGarden) {
        val link = pendingLink ?: return@LaunchedEffect
        when (link) {
            DeepLinks.Link.Scan -> {
                DeepLinks.pending = null
                tab = Tab.Tools.ordinal
                ScanRequests.request()
            }
            DeepLinks.Link.LogHarvest -> {
                val garden = gardenStore.selectedGarden ?: return@LaunchedEffect // wait for gardens to load
                DeepLinks.pending = null
                tab = Tab.Garden.ordinal
                stacks[Tab.Garden.ordinal].popToRoot()
                stacks[Tab.Garden.ordinal].push(Dest.Harvest(garden, autoCompose = true))
            }
        }
    }

    // Back from a non-home tab's root returns to the Garden tab.
    BackHandler(enabled = tab != Tab.Garden.ordinal && !stacks[tab].canPop) { tab = Tab.Garden.ordinal }

    val lifecycle = LocalLifecycleOwner.current.lifecycle
    DisposableEffect(lifecycle) {
        val obs = LifecycleEventObserver { _, event ->
            if (event == Lifecycle.Event.ON_RESUME) {
                scope.launch { badges.refresh() }
                PushManager.clearDelivered()
            }
        }
        lifecycle.addObserver(obs)
        onDispose { lifecycle.removeObserver(obs) }
    }

    CompositionLocalProvider(
        LocalGardenStore provides gardenStore,
        LocalBadgeStore provides badges,
        LocalAlertCenter provides alerts,
    ) {
        Box(Modifier.fillMaxSize()) {
            Scaffold(
                containerColor = YH.canvas,
                bottomBar = {
                    NavigationBar(containerColor = YH.canvas, tonalElevation = 0.dp) {
                        Tab.entries.forEach { t ->
                            val selected = tab == t.ordinal
                            NavigationBarItem(
                                selected = selected,
                                onClick = {
                                    Haptics.selection()
                                    // Re-tapping the current tab pops to its root.
                                    if (selected) stacks[t.ordinal].popToRoot() else tab = t.ordinal
                                },
                                icon = {
                                    val icon = when (t) {
                                        Tab.Garden -> Icons.Rounded.Home
                                        Tab.Tools -> Icons.Rounded.Handyman
                                        Tab.Announcements -> Icons.Rounded.Campaign
                                        Tab.More -> Icons.Rounded.MoreHoriz
                                    }
                                    if (t == Tab.More && badges.totalUnread > 0) {
                                        BadgedBox(badge = { Badge(containerColor = YH.danger) { Text("${badges.totalUnread}") } }) { Icon(icon, null) }
                                    } else {
                                        Icon(icon, null)
                                    }
                                },
                                label = { Text(t.label, fontSize = 11.sp, maxLines = 1, overflow = TextOverflow.Ellipsis) },
                                colors = NavigationBarItemDefaults.colors(
                                    selectedIconColor = YH.ink, selectedTextColor = YH.ink,
                                    indicatorColor = YH.lime,
                                    unselectedIconColor = YH.muted, unselectedTextColor = YH.muted,
                                ),
                            )
                        }
                    }
                },
            ) { padding ->
                Box(Modifier.fillMaxSize().padding(bottom = padding.calculateBottomPadding())) {
                    // Each tab keeps its own stack, like a TabView of NavigationStacks.
                    NavHost(stacks[tab]) { RouteContent(it) }
                }
            }

            ToastOverlay(alerts) { alert ->
                when (alert.kind) {
                    AppAlert.Kind.Announcement -> tab = Tab.Announcements.ordinal
                    else -> tab = Tab.More.ordinal
                }
            }
        }
    }
}

/** Top-of-screen toast for fresh messages and notifications. */
@Composable
private fun ToastOverlay(center: AppAlertCenter, onTap: (AppAlert) -> Unit) {
    val alert = center.current
    AnimatedVisibility(
        visible = alert != null,
        enter = slideInVertically { -it } + fadeIn(),
        exit = slideOutVertically { -it } + fadeOut(),
        modifier = Modifier.fillMaxWidth().windowInsetsPadding(WindowInsets.statusBars),
    ) {
        val a = alert ?: return@AnimatedVisibility
        val shape = RoundedCornerShape(18.dp)
        Row(
            Modifier
                .padding(horizontal = 12.dp, vertical = 6.dp)
                .fillMaxWidth()
                .shadow(10.dp, shape)
                .clip(shape)
                .background(YH.canvas)
                .border(1.dp, YH.border, shape)
                .clickable { Haptics.tap(); onTap(a); center.dismiss() }
                .padding(horizontal = 12.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Box(Modifier.size(34.dp).clip(CircleShape).background(YH.lime), contentAlignment = Alignment.Center) {
                val icon = when (a.kind) {
                    AppAlert.Kind.Message -> Icons.Rounded.ChatBubble
                    AppAlert.Kind.Announcement -> Icons.Rounded.Campaign
                    AppAlert.Kind.Alert -> Icons.Rounded.WarningAmber
                    AppAlert.Kind.Generic -> Icons.Rounded.Notifications
                }
                Icon(icon, null, tint = YH.ink, modifier = Modifier.size(16.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(a.title, style = YHType.bodyMedium, color = YH.ink, maxLines = 1, overflow = TextOverflow.Ellipsis)
                if (!a.body.isNullOrEmpty()) Text(a.body, style = YHType.caption, color = YH.muted, maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
            Spacer(Modifier.size(8.dp))
            Box(
                Modifier.size(24.dp).clip(CircleShape).background(YH.surface).clickable { Haptics.tap(); center.dismiss() },
                contentAlignment = Alignment.Center,
            ) { Icon(Icons.Rounded.Close, "Dismiss", tint = YH.muted, modifier = Modifier.size(12.dp)) }
        }
    }
}
