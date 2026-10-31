package app.yardharvest.manager.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Assignment
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.AttachMoney
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Contactless
import androidx.compose.material.icons.rounded.Forum
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.Handyman
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Notifications
import androidx.compose.material.icons.rounded.NotificationsActive
import androidx.compose.material.icons.rounded.Photo
import androidx.compose.material.icons.rounded.PieChart
import androidx.compose.material.icons.rounded.PushPin
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.ShoppingBasket
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
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.dashboard
import app.yardharvest.manager.api.listEvents
import app.yardharvest.manager.api.listResources
import app.yardharvest.manager.api.listShifts
import app.yardharvest.manager.api.listWallComments
import app.yardharvest.manager.api.myDues
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.LocalBadgeStore
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Announcement
import app.yardharvest.manager.model.DashboardEvent
import app.yardharvest.manager.model.DashboardPayload
import app.yardharvest.manager.model.DashboardPhoto
import app.yardharvest.manager.model.DuesRecord
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenEvent
import app.yardharvest.manager.model.GardenResource
import app.yardharvest.manager.model.ResourceLookup
import app.yardharvest.manager.model.VolunteerShift
import app.yardharvest.manager.model.WallComment
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDateChip
import app.yardharvest.manager.ui.brand.YHDivider
import app.yardharvest.manager.ui.brand.YHErrorState
import app.yardharvest.manager.ui.brand.YHIconTile
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionHeader
import app.yardharvest.manager.ui.brand.YHSkeletonBento
import app.yardharvest.manager.ui.brand.YHSkeletonBlock
import app.yardharvest.manager.ui.brand.YHStatTile
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.GardenCard
import app.yardharvest.manager.ui.home.GardenPickerSheet
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import app.yardharvest.manager.ui.notifications.NotificationsSheet
import app.yardharvest.manager.ui.tools.ResourceActionSheet
import coil.compose.AsyncImage
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.temporal.ChronoUnit
import kotlinx.coroutines.launch

/** Garden tab root: manager or member dashboard for the selected garden. */
@Composable
fun DashboardTab() {
    val store = LocalGardenStore.current
    val badges = LocalBadgeStore.current
    var showPicker by remember { mutableStateOf(false) }
    var showNotifications by remember { mutableStateOf(false) }
    val garden = store.selectedGarden

    YHScreen(
        title = if (garden == null) "Garden" else "",
        showBack = false,
        leading = {
            YHBarIcon(
                if (badges.unreadNotifications > 0) Icons.Rounded.NotificationsActive else Icons.Rounded.Notifications,
                "Notifications",
                tint = if (badges.unreadNotifications > 0) YH.ink else YH.muted,
            ) { showNotifications = true }
        },
        actions = { YHBarIcon(Icons.Rounded.SwapVert, "Switch garden") { showPicker = true } },
    ) {
        when {
            garden != null && store.hasAdminAccess -> ManagerDashboard(garden)
            garden != null -> MemberDashboard(garden)
            store.isLoading -> Box(Modifier.padding(YH.Space.md)) { YHSkeletonBento() }
            else -> NoGardenWelcome()
        }
    }
    if (showPicker) GardenPickerSheet { showPicker = false }
    if (showNotifications) NotificationsSheet { showNotifications = false }
}

// ---- Manager ---------------------------------------------------------------------

/** Bento dashboard: garden hero, 2×2 stats, a Today band, Payments, then drillable sections. */
@Composable
fun ManagerDashboard(garden: Garden) {
    val nav = LocalNav.current
    var payload by remember { mutableStateOf<DashboardPayload?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { payload = ApiClient.dashboard(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    YHRefreshable({ load(false) }) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = YH.Space.md, end = YH.Space.md, bottom = YH.Space.xl),
            verticalArrangement = Arrangement.spacedBy(YH.Space.md),
        ) {
            GardenCard(garden)
            val p = payload
            when {
                p != null -> {
                    StatBento(garden, p)
                    TodayBand(p)
                    PaymentsBand { nav.push(Dest.Payments(garden)) }
                    if (p.upcomingEvents.isNotEmpty()) EventsSection(p.upcomingEvents) { nav.push(Dest.Events(garden)) }
                    if (p.recentAnnouncements.isNotEmpty()) AnnouncementsSection(p.recentAnnouncements) { nav.push(Dest.Announcements(garden)) }
                    if (p.recentPhotos.isNotEmpty()) PhotosSection(p.recentPhotos) { nav.push(Dest.Community(garden)) }
                }
                loading -> YHSkeletonBento()
                error != null -> Box(Modifier.heightIn(min = 240.dp)) { YHErrorState(error!!) { scope.launch { load() } } }
            }
        }
    }
}

@Composable
private fun StatBento(garden: Garden, p: DashboardPayload) {
    val nav = LocalNav.current
    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
        Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHStatTile(
                "Occupancy", "${Math.round(p.plots.occupancyPct)}%", Modifier.weight(1f),
                detail = "${p.plots.assigned} of ${p.plots.total} plots", icon = Icons.Rounded.PieChart,
            ) { nav.push(Dest.Plots(garden)) }
            // Community replaces the old Waitlist tile; waitlist management lives
            // on the Plots screen's toolbar.
            YHStatTile(
                "Community", "Wall", Modifier.weight(1f),
                detail = if (p.waitlistCount > 0) "${p.waitlistCount} on the waitlist too" else "posts from your members",
                icon = Icons.Rounded.Forum,
            ) { nav.push(Dest.Community(garden)) }
        }
        Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHStatTile(
                "Harvest", "${Fmt.pounds(p.totalHarvestLbs)} lb", Modifier.weight(1f),
                detail = "this season", icon = Icons.Rounded.ShoppingBasket,
            ) { nav.push(Dest.Harvest(garden)) }
            // Everything awaiting a human decision: reservations plus held wall posts.
            val flags = p.wallFlaggedCount ?: 0
            YHStatTile(
                "Reviews", "${p.plots.reserved + flags}", Modifier.weight(1f),
                detail = reviewsDetail(p.plots.reserved, flags), icon = Icons.AutoMirrored.Rounded.Assignment,
            ) { nav.push(Dest.Reviews(garden)) }
        }
    }
}

private fun reviewsDetail(reservations: Int, flags: Int): String = when {
    reservations == 0 && flags == 0 -> "all caught up"
    flags == 0 -> if (reservations == 1) "reservation to review" else "reservations to review"
    reservations == 0 -> if (flags == 1) "flagged wall post" else "flagged wall posts"
    else -> "$reservations reservations · $flags wall"
}

/** Tap to Pay entry point, next to the KPIs. */
@Composable
private fun PaymentsBand(onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.size(56.dp).clip(RoundedCornerShape(14.dp)).background(YH.ink), contentAlignment = Alignment.Center) {
                Icon(Icons.Rounded.Contactless, null, tint = YH.lime, modifier = Modifier.size(26.dp))
            }
            Column(Modifier.weight(1f)) {
                Text("Payments", style = YHType.title3, color = YH.ink)
                Text("Collect dues or run a Tap to Pay sale.", style = YHType.subheadline, color = YH.muted)
            }
            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
        }
    }
}

@Composable
private fun TodayBand(p: DashboardPayload) {
    val endOfDay = LocalDate.now().plusDays(1).atStartOfDay(ZoneId.systemDefault()).toInstant()
    val today = p.upcomingEvents.filter { (it.eventDate ?: Instant.MIN) < endOfDay }.take(2)
    if (today.isEmpty()) return
    YHBand {
        Text("TODAY", style = YHType.captionMed, letterSpacing = 0.8.sp, color = YH.ink)
        Text(today.first().title, style = YHType.title3, color = YH.ink, modifier = Modifier.padding(top = 6.dp))
        if (today.size > 1) Text("+ ${today.size - 1} more", style = YHType.caption, color = YH.ink.copy(alpha = 0.7f))
    }
}

@Composable
private fun EventsSection(events: List<DashboardEvent>, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader("Upcoming Events", trailing = "${events.size}", showsChevron = true)
            val items = events.take(3)
            items.forEachIndexed { i, e ->
                Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    e.eventDate?.let { YHDateChip(it, lime = true, size = 44.dp) }
                    Column(Modifier.weight(1f)) {
                        Text(e.title, style = YHType.bodyMedium, color = YH.ink)
                        e.eventDate?.let { Text(Fmt.time(it), style = YHType.caption, color = YH.muted) }
                    }
                    val going = e.rsvpGoing ?: 0
                    if (going > 0) YHPill("$going going", tint = YH.ink, background = YH.lime)
                }
                if (i < items.lastIndex) YHDivider()
            }
        }
    }
}

@Composable
private fun AnnouncementsSection(items: List<Announcement>, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader("Recent Announcements", showsChevron = true)
            val shown = items.take(3)
            shown.forEachIndexed { i, a ->
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        if (a.pinned == true) Icon(Icons.Rounded.PushPin, null, tint = YH.ink, modifier = Modifier.size(14.dp))
                        Text(a.title, style = YHType.bodyMedium, color = YH.ink)
                    }
                    Text(a.body, style = YHType.subheadline, color = YH.muted, maxLines = 2)
                    a.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.tertiary) }
                }
                if (i < shown.lastIndex) YHDivider()
            }
        }
    }
}

@Composable
private fun PhotosSection(photos: List<DashboardPhoto>, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader("Photo Wall", showsChevron = true)
            Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                photos.forEach { p ->
                    Box(Modifier.size(110.dp).clip(RoundedCornerShape(12.dp)).background(YH.surface), contentAlignment = Alignment.Center) {
                        Icon(Icons.Rounded.Photo, null, tint = YH.muted)
                        AsyncImage(AppEnvironment.mediaUrl(p.photoUrl), p.caption, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
                    }
                }
            }
        }
    }
}

// ---- Member ----------------------------------------------------------------------

/** Activity-feed dashboard for plot holders — no admin KPIs. */
@Composable
fun MemberDashboard(garden: Garden) {
    val nav = LocalNav.current
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = YH.Space.md, end = YH.Space.md, bottom = YH.Space.xl),
        verticalArrangement = Arrangement.spacedBy(YH.Space.md),
    ) {
        GardenCard(garden, height = 168.dp)
        MyDuesSummaryCard(garden) { nav.push(Dest.MyDues(garden)) }
        VolunteerOpportunitiesCard(garden) { nav.push(Dest.Shifts(garden)) }
        UpcomingEventsCard(garden) { nav.push(Dest.Events(garden)) }
        CommunityWallCard(garden) { nav.push(Dest.Community(garden)) }
        CheckedOutToolsCard(garden, onlyMine = true)
    }
}

/** Outstanding dues for the active garden; hidden once nothing is owed. */
@Composable
private fun MyDuesSummaryCard(garden: Garden, onClick: () -> Unit) {
    var dues by remember(garden.id) { mutableStateOf<List<DuesRecord>>(emptyList()) }
    var loaded by remember(garden.id) { mutableStateOf(false) }
    LaunchedEffect(garden.id) {
        dues = runCatching { ApiClient.myDues(garden.id) }.getOrDefault(emptyList())
        loaded = true
    }
    val unpaid = dues.filter { !it.isPaid && it.balance > 0 }
    if (loaded && unpaid.isEmpty()) return
    val outstanding = dues.sumOf { it.balance }
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                YHIconTile(Icons.Rounded.AttachMoney, background = YH.lime)
                Text("My Dues", style = YHType.headline, color = YH.ink, modifier = Modifier.weight(1f))
                Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
            }
            if (loaded) {
                Row(verticalAlignment = Alignment.Bottom, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(Fmt.money(outstanding), fontSize = 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, color = YH.ink)
                    Text("outstanding", style = YHType.subheadline, color = YH.muted, modifier = Modifier.weight(1f).padding(bottom = 3.dp))
                    YHPill("Pay Now", tint = YH.ink, background = YH.lime)
                }
            } else {
                YHSkeletonBlock(height = 22.dp)
            }
        }
    }
}

/** Volunteer shifts in the next two weeks. */
@Composable
fun VolunteerOpportunitiesCard(garden: Garden, onClick: () -> Unit) {
    var shifts by remember(garden.id) { mutableStateOf<List<VolunteerShift>>(emptyList()) }
    var loaded by remember(garden.id) { mutableStateOf(false) }
    LaunchedEffect(garden.id) {
        shifts = runCatching { ApiClient.listShifts(garden.id, "upcoming") }.getOrDefault(emptyList())
        loaded = true
    }
    val cutoff = Instant.now().plus(14, ChronoUnit.DAYS)
    val soon = shifts.filter { (it.shiftDate ?: Instant.MAX) <= cutoff }
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader("Volunteer Opportunities", icon = Icons.Rounded.Group, trailing = "Next 2 weeks")
            when {
                !loaded -> { YHSkeletonBlock(height = 12.dp); YHSkeletonBlock(height = 12.dp) }
                soon.isEmpty() -> Text("Nothing scheduled in the next two weeks.", style = YHType.subheadline, color = YH.muted)
                else -> {
                    val items = soon.take(4)
                    items.forEachIndexed { i, s ->
                        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            s.shiftDate?.let { YHDateChip(it, size = 40.dp) }
                            Column(Modifier.weight(1f)) {
                                Text(s.title, style = YHType.bodyMedium, color = YH.ink)
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    s.timeRange?.let { Text(it, style = YHType.caption, color = YH.muted) }
                                    Text("· ${s.signupCount}${s.maxVolunteers?.let { "/$it" } ?: ""} in", style = YHType.caption,
                                        color = if (s.isFull) YH.warning else YH.muted)
                                }
                            }
                        }
                        if (i < items.lastIndex) YHDivider()
                    }
                }
            }
        }
    }
}

@Composable
fun UpcomingEventsCard(garden: Garden, onClick: () -> Unit) {
    var events by remember(garden.id) { mutableStateOf<List<GardenEvent>>(emptyList()) }
    var loaded by remember(garden.id) { mutableStateOf(false) }
    LaunchedEffect(garden.id) {
        events = runCatching { ApiClient.listEvents(garden.id, "upcoming") }.getOrDefault(emptyList())
        loaded = true
    }
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader("Upcoming Events", icon = Icons.Rounded.CalendarMonth)
            when {
                !loaded -> { YHSkeletonBlock(height = 12.dp); YHSkeletonBlock(height = 12.dp) }
                events.isEmpty() -> Text("No upcoming events.", style = YHType.subheadline, color = YH.muted)
                else -> {
                    val items = events.take(4)
                    items.forEachIndexed { i, e ->
                        Column {
                            Text(e.title, style = YHType.bodyMedium, color = YH.ink)
                            Row {
                                e.eventDate?.let { Text(Fmt.dateTime(it), style = YHType.caption, color = YH.muted, modifier = Modifier.weight(1f)) }
                                if (e.rsvpGoing > 0) Text("${e.rsvpGoing} going", style = YHType.captionMed, color = YH.ink)
                            }
                        }
                        if (i < items.lastIndex) YHDivider()
                    }
                }
            }
        }
    }
}

/** Latest top-level wall posts, so the wall is discovered, not hunted for. */
@Composable
private fun CommunityWallCard(garden: Garden, onClick: () -> Unit) {
    var posts by remember(garden.id) { mutableStateOf<List<WallComment>>(emptyList()) }
    var loaded by remember(garden.id) { mutableStateOf(false) }
    LaunchedEffect(garden.id) {
        posts = runCatching { ApiClient.listWallComments(garden.id) }.getOrDefault(emptyList())
        loaded = true
    }
    val preview = posts.filter { it.parentId == null }.take(3)
    YHCard(onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                YHIconTile(Icons.Rounded.Forum, background = YH.lime)
                Text("Community", style = YHType.headline, color = YH.ink, modifier = Modifier.weight(1f))
                Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
            }
            when {
                !loaded -> YHSkeletonBlock(height = 44.dp)
                preview.isEmpty() -> Text("Nothing on the wall yet — be the first to say hello.", style = YHType.subheadline, color = YH.muted)
                else -> preview.forEachIndexed { i, post ->
                    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        YHAvatar(post.authorName, size = 28.dp)
                        Column(Modifier.weight(1f)) {
                            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(post.authorName, style = YHType.captionMed, color = YH.ink)
                                post.createdAt?.let { Text(Fmt.relative(it), style = YHType.caption, color = YH.muted) }
                            }
                            Text(post.body, style = YHType.subheadline, color = YH.ink, maxLines = 2)
                        }
                    }
                    if (i < preview.lastIndex) YHDivider()
                }
            }
        }
    }
}

/** Checked-out tools; tapping one opens the same sheet the scanner uses. */
@Composable
fun CheckedOutToolsCard(garden: Garden, onlyMine: Boolean) {
    var resources by remember(garden.id) { mutableStateOf<List<GardenResource>>(emptyList()) }
    var loaded by remember(garden.id) { mutableStateOf(false) }
    var selected by remember { mutableStateOf<GardenResource?>(null) }
    val scope = rememberCoroutineScope()
    val me = AuthManager.currentUser?.id
    suspend fun load() {
        resources = runCatching { ApiClient.listResources(garden.id) }.getOrDefault(emptyList())
        loaded = true
    }
    LaunchedEffect(garden.id) { load() }
    val out = resources.filter { it.isCheckedOut && (!onlyMine || it.checkedOutToId == me) }
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionHeader(if (onlyMine) "My Checked-Out Tools" else "Checked-Out Tools", icon = Icons.Rounded.Handyman)
            when {
                !loaded -> YHSkeletonBlock(height = 12.dp)
                out.isEmpty() -> Text(if (onlyMine) "You have no tools checked out." else "No tools are out.", style = YHType.subheadline, color = YH.muted)
                else -> {
                    val items = out.take(5)
                    items.forEachIndexed { i, r ->
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable { selected = r }.padding(vertical = 2.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Column(Modifier.weight(1f)) {
                                Text(r.name, style = YHType.bodyMedium, color = YH.ink)
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    if (!onlyMine) r.checkedOutToName?.let { Text(it, style = YHType.caption, color = YH.muted) }
                                    r.dueDate?.let { Text("due ${Fmt.date(it)}", style = YHType.caption, color = YH.muted) }
                                }
                            }
                            if (r.isOverdue) YHPill("Overdue", tint = androidx.compose.ui.graphics.Color.White, background = YH.danger)
                            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                        }
                        if (i < items.lastIndex) YHDivider()
                    }
                }
            }
        }
    }
    selected?.let { r ->
        // "Return the rake from your couch."
        ResourceActionSheet(ResourceLookup(garden.id, garden.name, r.id, r), organizerId = garden.organizerId) { changed ->
            selected = null
            if (changed) scope.launch { load() }
        }
    }
}

/** Shown when the user isn't in any garden yet; drives them into discovery. */
@Composable
fun NoGardenWelcome() {
    val nav = LocalNav.current
    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md),
        verticalArrangement = Arrangement.spacedBy(YH.Space.lg),
    ) {
        YHBand {
            Text("Welcome!", style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.ink)
            Text("Let's get you", fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, color = YH.ink, modifier = Modifier.padding(top = 6.dp))
            Text("a plot to grow on.", fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, color = YH.ink)
            Text(
                "Browse community gardens nearby and reserve a plot or join a waitlist — it only takes a minute.",
                style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f), modifier = Modifier.padding(top = 4.dp),
            )
        }
        YHButton("Find a Garden", icon = Icons.Rounded.Search) { nav.push(Dest.BrowseGardens) }
        YHCard {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Icon(Icons.Rounded.Info, null, tint = YH.muted)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text("Running a garden yourself?", style = YHType.bodyMedium, color = YH.ink)
                    Text("Garden organizers register their garden at yardharvest.app.", style = YHType.subheadline, color = YH.muted)
                }
            }
        }
    }
}
