package app.yardharvest.manager.ui.more

import android.content.Intent
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.HelpOutline
import androidx.compose.material.icons.automirrored.rounded.Logout
import androidx.compose.material.icons.automirrored.rounded.OpenInNew
import androidx.compose.material.icons.rounded.AdminPanelSettings
import androidx.compose.material.icons.rounded.AttachMoney
import androidx.compose.material.icons.rounded.Block
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Campaign
import androidx.compose.material.icons.rounded.Contactless
import androidx.compose.material.icons.rounded.Fingerprint
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.SettingsInputAntenna
import androidx.compose.material.icons.rounded.ShoppingBasket
import androidx.compose.material.icons.rounded.UnfoldMore
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateMapOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import app.yardharvest.manager.api.blockedMembers
import app.yardharvest.manager.api.changeMemberRole
import app.yardharvest.manager.api.listGardenMembers
import app.yardharvest.manager.api.unblockMember
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.AppLock
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalBadgeStore
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.BlockedMember
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenMember
import app.yardharvest.manager.ui.auth.ConnectionSettingsSheet
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.SheetAction
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHActionSheet
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHIconTile
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHNavRow
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSwitch
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.GardenPickerSheet
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import kotlinx.coroutines.launch

@Composable
fun MoreTab() {
    val nav = LocalNav.current
    val store = LocalGardenStore.current
    val badges = LocalBadgeStore.current
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    var showPicker by remember { mutableStateOf(false) }
    var showConnection by remember { mutableStateOf(false) }

    /** Capability check with the blanket-admin fallback for payloads that predate roles. */
    fun canDo(capability: String, garden: Garden) = garden.userCapabilities?.contains(capability) ?: store.hasAdminAccess

    YHScreen("More", showBack = false) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md),
            verticalArrangement = Arrangement.spacedBy(YH.Space.md),
        ) {
            AuthManager.currentUser?.let { user ->
                YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
                        YHAvatar(user.bestName, size = 52.dp)
                        Column {
                            Text(user.bestName, style = YHType.bodyMedium, color = YH.ink)
                            Text(user.email, style = YHType.caption, color = YH.muted)
                        }
                    }
                }
            }

            Section("Activity") {
                YHNavRow("Messages", Icons.Rounded.Forum, badge = badges.unreadMessages) { nav.push(Dest.Inbox) }
                YHNavRow("Notifications", Icons.Rounded.Notifications, badge = badges.unreadNotifications) { nav.push(Dest.Notifications) }
                YHNavRow("Find a Garden", Icons.Rounded.Search) { nav.push(Dest.BrowseGardens) }
            }

            store.selectedGarden?.let { garden ->
                Section("Garden") {
                    RowCard {
                        Row(Modifier.padding(YH.Space.md), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(garden.name, style = YHType.bodyMedium, color = YH.ink)
                                Text(garden.locationLine, style = YHType.caption, color = YH.muted)
                            }
                            Text(
                                "Switch", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = YH.ink,
                                modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.surface)
                                    .clickable { Haptics.tap(); showPicker = true }.padding(horizontal = 12.dp, vertical = 6.dp),
                            )
                        }
                    }
                    YHNavRow("My Dues", Icons.Rounded.AttachMoney) { nav.push(Dest.MyDues(garden)) }
                    // Admin rows gate on role capabilities: a treasurer sees
                    // Payments without the rest; a volunteer lead sees neither.
                    if (canDo("money", garden)) YHNavRow("Payments — Tap to Pay", Icons.Rounded.Contactless) { nav.push(Dest.Payments(garden)) }
                    if (canDo("resources", garden)) YHNavRow("Manage Tools", Icons.Rounded.QrCode2) { nav.push(Dest.AdminTools(garden)) }
                    if (store.can("roles")) YHNavRow("Roles", Icons.Rounded.AdminPanelSettings) { nav.push(Dest.Roles(garden)) }
                    YHNavRow("Events", Icons.Rounded.CalendarMonth) { nav.push(Dest.Events(garden)) }
                    YHNavRow("Volunteer Shifts", Icons.Rounded.Group) { nav.push(Dest.Shifts(garden)) }
                    YHNavRow("Harvest Log", Icons.Rounded.ShoppingBasket) { nav.push(Dest.Harvest(garden)) }
                    YHNavRow("Announcements", Icons.Rounded.Campaign) { nav.push(Dest.Announcements(garden)) }
                }
            }

            Section("App") {
                BiometricLockRow()
                // Blocking is undone here and nowhere else, so the row always shows.
                YHNavRow("Blocked Members", Icons.Rounded.Block) { nav.push(Dest.BlockedMembers) }
                // The website's Help Center opens in the browser; it points out of the app.
                YHNavRow("Help Center", Icons.AutoMirrored.Rounded.HelpOutline, showsChevron = false, trailing = {
                    Icon(Icons.AutoMirrored.Rounded.OpenInNew, null, tint = YH.muted, modifier = Modifier.size(16.dp))
                }) {
                    runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, "https://www.yardharvest.app/help".toUri())) }
                }
                YHNavRow("Connection Settings", Icons.Rounded.SettingsInputAntenna, showsChevron = false) { showConnection = true }
                RowCard {
                    Row(Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = 14.dp, bottom = 14.dp),
                        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                        YHIconTile(Icons.Rounded.Info)
                        Text("Version", style = YHType.bodyMedium, color = YH.ink, modifier = Modifier.weight(1f))
                        Text("${AppEnvironment.appVersion} (${AppEnvironment.buildNumber})", style = YHType.caption, color = YH.muted)
                    }
                }
            }

            RowCard(onClick = { Haptics.warning(); scope.launch { AuthManager.signOut() } }) {
                Row(Modifier.fillMaxWidth().padding(vertical = 14.dp), horizontalArrangement = Arrangement.Center, verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.AutoMirrored.Rounded.Logout, null, tint = YH.danger, modifier = Modifier.size(18.dp))
                    Text("  Sign Out", style = YHType.bodyMedium, color = YH.danger)
                }
            }
        }
    }
    if (showPicker) GardenPickerSheet { showPicker = false }
    if (showConnection) ConnectionSettingsSheet { showConnection = false }
}

@Composable
private fun Section(title: String, content: @Composable () -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        YHSectionLabel(title)
        content()
    }
}

/** The card chrome every row on the More tab wears. */
@Composable
private fun RowCard(onClick: (() -> Unit)? = null, content: @Composable () -> Unit) {
    val shape = RoundedCornerShape(YH.Radius.md)
    Column(
        Modifier.fillMaxWidth().clip(shape).background(YH.canvas).border(1.dp, YH.border, shape)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
    ) { content() }
}

/**
 * Opt-in biometric lock. The switch shows only where the phone can do it;
 * otherwise the reason is shown so the person knows what to fix.
 */
@Composable
private fun BiometricLockRow() {
    val context = LocalContext.current
    val lock = AppLock.shared
    val scope = rememberCoroutineScope()
    var on by remember { mutableStateOf(lock.isEnabled) }
    var error by remember { mutableStateOf<String?>(null) }
    val name = AppLock.biometryName(context)
    val unavailable = AppLock.unavailableReason(context)
    RowCard {
        Column(Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = 10.dp, bottom = 14.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                YHIconTile(Icons.Rounded.Fingerprint)
                Text("Require biometric unlock", style = YHType.bodyMedium, color = YH.ink, modifier = Modifier.weight(1f))
                if (name != null) {
                    YHSwitch(on, onCheckedChange = { wanted ->
                        scope.launch {
                            // Both directions require passing the check; a cancel
                            // puts the switch back where it was.
                            val ok = if (wanted) lock.enable() else lock.disable()
                            on = lock.isEnabled
                            if (ok) { error = null; Haptics.success() } else error = lock.lastError
                        }
                    })
                }
            }
            val note = unavailable ?: error ?: "Ask for $name when you come back to YardHarvest after a minute away."
            Text(note, style = YHType.caption, color = if (unavailable == null && error != null) YH.danger else YH.muted,
                modifier = Modifier.padding(top = 4.dp))
        }
    }
}

// ---- Roles -------------------------------------------------------------------------

private data class RoleOption(val id: String, val label: String, val blurb: String)

private val roleOptions = listOf(
    RoleOption("co_organizer", "Co-organizer",
        "Can run the garden: plots, members, events, shifts, resources, dues and reports. Cannot change roles, billing or where payouts go."),
    RoleOption("treasurer", "Treasurer",
        "Can manage dues, expenses and reports — including taking Tap to Pay payments. No access to plots, members or settings."),
    RoleOption("volunteer_lead", "Volunteer lead", "Can manage events and volunteer shifts. No access to money or members."),
    RoleOption("member", "Member", "No administrative access."),
)

/**
 * Organizer-only role management (garden permissions). 'Organizer' is not
 * assignable: it follows garden ownership, and the backend refuses it.
 */
@Composable
fun RolesScreen(garden: Garden) {
    var members by remember { mutableStateOf<List<GardenMember>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var picking by remember { mutableStateOf<GardenMember?>(null) }
    var workingId by remember { mutableStateOf<Int?>(null) }
    val assigned = remember { mutableStateMapOf<Int, String>() }
    var info by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { members = ApiClient.listGardenMembers(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    fun assign(role: String, member: GardenMember) {
        picking = null
        scope.launch {
            workingId = member.userId
            try {
                val set = ApiClient.changeMemberRole(garden.id, member.userId, role)
                assigned[member.userId] = set
                val label = roleOptions.firstOrNull { it.id == set }?.label ?: set
                info = "${member.name} is now ${if (label.lowercase() == "member") "a member" else label.lowercase()}."
                Haptics.success()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                workingId = null
            }
        }
    }

    YHScreen("Roles") {
        YHLoadable(loading, members.isEmpty(), error, { scope.launch { load() } },
            empty = { YHEmpty(Icons.Rounded.Group, "No members yet", "Roles can be assigned once people join your garden.") }) {
            YHRefreshable({ load(false) }) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHBand {
                        Text("Share the load", style = YHType.title3, color = YH.ink)
                        Text(
                            "A co-organizer runs the day-to-day, a treasurer takes the money — including Tap to Pay — and a volunteer lead owns events and shifts. Roles grant only what they say.",
                            style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f), modifier = Modifier.padding(top = 4.dp),
                        )
                    }
                    members.forEach { m ->
                        YHCard {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                YHAvatar(m.name, size = 42.dp)
                                Column(Modifier.weight(1f)) {
                                    Text(m.name, style = YHType.bodyMedium, color = YH.ink)
                                    Text(
                                        when { m.isOrganizer -> "Owns the garden"; m.plotNumber != null -> "Plot ${m.plotNumber}"; else -> "Member" },
                                        style = YHType.caption, color = YH.muted,
                                    )
                                }
                                when {
                                    m.isOrganizer -> YHPill("Organizer", tint = YH.ink, background = YH.lime)
                                    workingId == m.userId -> CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                                    else -> Row(
                                        Modifier.clip(RoundedCornerShape(50)).background(YH.surface)
                                            .clickable { Haptics.tap(); picking = m }.padding(horizontal = 12.dp, vertical = 6.dp),
                                        verticalAlignment = Alignment.CenterVertically,
                                    ) {
                                        // The public roster doesn't carry roles: show what was set
                                        // this session, else offer the change without claiming to know.
                                        val label = assigned[m.userId]?.let { set -> roleOptions.firstOrNull { it.id == set }?.label ?: set } ?: "Set role"
                                        Text(label, fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = YH.ink)
                                        Icon(Icons.Rounded.UnfoldMore, null, tint = YH.ink, modifier = Modifier.size(14.dp))
                                    }
                                }
                            }
                        }
                    }
                    info?.let { Text(it, style = YHType.subheadline, color = YH.ink) }
                }
            }
        }
    }
    picking?.let { m ->
        YHActionSheet(
            title = "Role for ${m.name}",
            message = roleOptions.joinToString("\n\n") { "${it.label}: ${it.blurb}" },
            actions = roleOptions.map { r -> SheetAction(r.label) { assign(r.id, m) } },
            onDismiss = { picking = null },
        )
    }
}

// ---- Blocked members ---------------------------------------------------------------

/** The people you've blocked, and the way back. Reachable whether or not the list is empty. */
@Composable
fun BlockedMembersScreen() {
    var members by remember { mutableStateOf<List<BlockedMember>>(emptyList()) }
    var loading by remember { mutableStateOf(true) }
    var error by remember { mutableStateOf<String?>(null) }
    val working = remember { mutableStateMapOf<Int, Boolean>() }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        try { members = ApiClient.blockedMembers(); error = null } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(Unit) { load() }

    YHScreen("Blocked") {
        YHLoadable(loading, members.isEmpty(), error, { scope.launch { load() } },
            empty = {
                YHEmpty(Icons.Rounded.Block, "Nobody blocked",
                    "Block someone from the menu on any post on a garden's community wall. Their posts stop showing up for you.")
            }) {
            YHRefreshable({ load(false) }) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    members.forEach { m ->
                        YHCard {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                                YHAvatar(m.name, size = 34.dp)
                                Column(Modifier.weight(1f)) {
                                    Text(m.name, style = YHType.bodyMedium, color = YH.ink)
                                    m.blockedAt?.let { Text("Blocked ${Fmt.relative(it)}", style = YHType.caption, color = YH.muted) }
                                }
                                if (working[m.userId] == true) {
                                    CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                                } else {
                                    Text("Unblock", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = YH.ink,
                                        modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable {
                                            scope.launch {
                                                working[m.userId] = true
                                                try {
                                                    ApiClient.unblockMember(m.userId)
                                                    members = members.filter { it.userId != m.userId }
                                                    Haptics.success()
                                                } catch (e: Exception) {
                                                    error = e.userMessage
                                                    Haptics.error()
                                                } finally {
                                                    working.remove(m.userId)
                                                }
                                            }
                                        }.padding(8.dp))
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
