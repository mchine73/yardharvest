package app.yardharvest.manager.ui.discover

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.ChatBubble
import androidx.compose.material.icons.rounded.Eco
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.rounded.HowToReg
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.PersonAdd
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.Search
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.VerticalDivider
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.browseGardens
import app.yardharvest.manager.api.gardenDetail
import app.yardharvest.manager.api.joinWaitlist
import app.yardharvest.manager.api.publicPlots
import app.yardharvest.manager.api.reservePlot
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenDetail
import app.yardharvest.manager.model.Plot
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHErrorState
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonBlock
import app.yardharvest.manager.ui.brand.YHSkeletonCard
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.GardenCard
import app.yardharvest.manager.ui.inbox.ComposeMessageSheet
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import kotlinx.coroutines.async
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** Discover gardens to join — paginated, searchable photo cards. */
@Composable
fun BrowseGardensScreen() {
    val nav = LocalNav.current
    var gardens by remember { mutableStateOf<List<Garden>>(emptyList()) }
    var search by rememberSaveable { mutableStateOf("") }
    var page by remember { mutableIntStateOf(1) }
    var totalPages by remember { mutableIntStateOf(1) }
    var loading by remember { mutableStateOf(false) }
    var pagingMore by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun reload() {
        loading = true
        error = null
        page = 1
        try {
            val p = ApiClient.browseGardens(1, search)
            gardens = p.gardens
            totalPages = p.pages
        } catch (e: Exception) {
            error = e.userMessage
        } finally {
            loading = false
        }
    }

    suspend fun loadMore() {
        if (pagingMore || page >= totalPages) return
        pagingMore = true
        try {
            val next = page + 1
            val p = ApiClient.browseGardens(next, search)
            gardens = gardens + p.gardens
            page = next
            totalPages = p.pages
        } catch (_: Exception) {
            // Quietly fail paging; pull to refresh recovers.
        } finally {
            pagingMore = false
        }
    }

    // Debounced search, like the iOS .searchable 320 ms debounce.
    LaunchedEffect(search) {
        if (gardens.isNotEmpty() || search.isNotEmpty()) delay(320)
        reload()
    }

    YHScreen("Find a Garden") {
        YHTextField(
            search, { search = it }, placeholder = "Search by name, city, or description",
            textStyle = YHType.body.copy(color = YH.ink),
            modifier = Modifier.padding(horizontal = YH.Space.md, vertical = 8.dp),
        )
        when {
            gardens.isEmpty() && loading -> Column(Modifier.padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                repeat(4) { YHSkeletonBlock(height = 116.dp, radius = YH.Radius.lg) }
            }
            gardens.isEmpty() && error != null -> YHErrorState(error!!) { scope.launch { reload() } }
            gardens.isEmpty() -> YHEmpty(
                Icons.Rounded.Search, "No gardens found",
                if (search.isEmpty()) "There are no public gardens to show right now." else "Nothing matched “$search”. Try a different search.",
            )
            else -> YHRefreshable({ reload() }) {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(YH.Space.md),
                    verticalArrangement = Arrangement.spacedBy(YH.Space.sm),
                ) {
                    items(gardens, key = { it.id }) { g ->
                        GardenCard(g, compact = true, onClick = { nav.push(Dest.GardenDetail(g.id)) })
                        if (g.id == gardens.last().id && page < totalPages) LaunchedEffect(g.id) { loadMore() }
                    }
                    if (pagingMore) item {
                        Box(Modifier.fillMaxWidth().padding(vertical = YH.Space.md), contentAlignment = Alignment.Center) {
                            CircularProgressIndicator(Modifier.size(22.dp), color = YH.ink, strokeWidth = 2.dp)
                        }
                    }
                }
            }
        }
    }
}

/** Public garden detail with a context-aware CTA: take a plot, your plot, or the waitlist. */
@Composable
fun GardenDetailScreen(gardenId: Int) {
    val gardenStore = LocalGardenStore.current
    var detail by remember { mutableStateOf<GardenDetail?>(null) }
    var plots by remember { mutableStateOf<List<Plot>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var showPlotPicker by remember { mutableStateOf(false) }
    var showWaitlist by remember { mutableStateOf(false) }
    var showMessage by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try {
            coroutineScope {
                val d = async { ApiClient.gardenDetail(gardenId) }
                val p = async { runCatching { ApiClient.publicPlots(gardenId) }.getOrDefault(emptyList()) }
                detail = d.await()
                plots = p.await()
            }
        } catch (e: Exception) {
            error = e.userMessage
        } finally {
            loading = false
        }
    }
    LaunchedEffect(gardenId) { load() }

    YHScreen("") {
        YHRefreshable({ load(false) }) {
            Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
                val d = detail
                when {
                    d != null -> {
                        GardenCard(d.asGarden, height = 200.dp)
                        StatsCard(d)
                        MembershipCta(d, onTakePlot = {
                            scope.launch {
                                plots = runCatching { ApiClient.publicPlots(gardenId) }.getOrDefault(emptyList())
                                showPlotPicker = true
                            }
                        }, onWaitlist = { showWaitlist = true })
                        if (d.organizerId != null && d.organizerName != null && !d.userIsOrganizer) {
                            YHCard(onClick = { showMessage = true }) {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    YHAvatar(icon = Icons.Rounded.ChatBubble, size = 36.dp)
                                    Column(Modifier.weight(1f)) {
                                        Text("Message the organizer", style = YHType.bodyMedium, color = YH.ink)
                                        Text(d.organizerName, style = YHType.caption, color = YH.muted)
                                    }
                                    Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                                }
                            }
                        }
                        info?.let {
                            Text(it, style = YHType.subheadline, color = YH.ink,
                                modifier = Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.md)).background(YH.limeSoft).padding(YH.Space.md))
                        }
                        if (!d.description.isNullOrEmpty()) YHCard { Text(d.description, style = YHType.body, color = YH.ink.copy(alpha = 0.85f)) }
                        if (!d.rules.isNullOrEmpty()) YHCard {
                            Text("Garden Rules", style = YHType.headline, color = YH.ink)
                            Text(d.rules, style = YHType.body, color = YH.ink.copy(alpha = 0.85f), modifier = Modifier.padding(top = 6.dp))
                        }
                    }
                    loading -> { YHSkeletonBlock(height = 200.dp, radius = YH.Radius.lg); YHSkeletonCard(rows = 3) }
                    error != null -> Box(Modifier.heightIn(min = 240.dp)) { YHErrorState(error!!) { scope.launch { load() } } }
                }
            }
        }
    }

    if (showPlotPicker) PlotPickerSheet(gardenId, plots, onDismiss = { showPlotPicker = false }) {
        info = "Plot reserved! The organizer will confirm shortly."
        scope.launch { load(false); gardenStore.reload() }
    }
    if (showWaitlist) WaitlistJoinSheet(gardenId, onDismiss = { showWaitlist = false }) {
        info = "You're on the waitlist — we'll let you know when a plot opens up."
        scope.launch { load(false) }
    }
    val d = detail
    if (showMessage && d?.organizerId != null && d.organizerName != null) {
        ComposeMessageSheet(d.organizerId, d.organizerName, contextLabel = d.name, onDismiss = { showMessage = false }) {
            info = "Message sent to ${d.organizerName}."
        }
    }
}

@Composable
private fun StatsCard(d: GardenDetail) {
    YHCard {
        Row(Modifier.height(androidx.compose.foundation.layout.IntrinsicSize.Min)) {
            Stat("${d.availablePlots ?: 0}", "Open plots", Modifier.weight(1f))
            VerticalDivider(color = YH.border)
            Stat("${d.memberCount ?: 0}", "Members", Modifier.weight(1f))
            VerticalDivider(color = YH.border)
            Stat(d.plotFeeAnnual?.let { "$${it.toInt()}" } ?: "—", "Plot fee /yr", Modifier.weight(1f))
        }
    }
}

@Composable
private fun Stat(value: String, label: String, modifier: Modifier) {
    Column(modifier, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(2.dp)) {
        Text(value, fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, color = YH.ink)
        Text(label.uppercase(), style = YHType.caption, letterSpacing = 0.6.sp, color = YH.muted)
    }
}

@Composable
private fun MembershipCta(d: GardenDetail, onTakePlot: () -> Unit, onWaitlist: () -> Unit) {
    when {
        d.userIsOrganizer -> BandLabel(Icons.Rounded.HowToReg, "You organize this garden.")
        d.userHasPlot -> BandLabel(Icons.Rounded.Verified, "You have a plot here.")
        d.userHasReservation -> StatusCard(Icons.Rounded.Schedule, "Reservation pending", "The organizer will confirm your reservation soon.")
        d.userOnWaitlist -> StatusCard(Icons.Rounded.HourglassTop, "You're on the waitlist", "We'll notify you when a plot opens up.")
        else -> Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            if ((d.availablePlots ?: 0) > 0) {
                YHButton("Take a Plot", icon = Icons.Rounded.Eco, style = YHButtonStyle.Lime, onClick = onTakePlot)
            } else {
                YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Rounded.Info, null, tint = YH.muted)
                        Text("No plots open right now.", style = YHType.body, color = YH.muted)
                    }
                }
            }
            YHButton("Join the Waitlist", icon = Icons.Rounded.PersonAdd, style = YHButtonStyle.Ghost, onClick = onWaitlist)
        }
    }
}

@Composable
private fun BandLabel(icon: ImageVector, text: String) {
    YHBand {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, null, tint = YH.ink)
            Text(text, style = YHType.bodyMedium, color = YH.ink)
        }
    }
}

@Composable
private fun StatusCard(icon: ImageVector, title: String, body: String) {
    YHCard {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Icon(icon, null, tint = YH.ink)
            Text(title, style = YHType.headline, color = YH.ink)
        }
        Text(body, style = YHType.subheadline, color = YH.muted, modifier = Modifier.padding(top = 6.dp))
    }
}

/** Pick an available plot to reserve; the organizer confirms it. */
@Composable
fun PlotPickerSheet(gardenId: Int, plots: List<Plot>, onDismiss: () -> Unit, onReserved: () -> Unit) {
    var reservingId by remember { mutableStateOf<Int?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val available = plots.filter { it.status == "available" }

    YHSheet(onDismiss, title = "Take a Plot", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        if (available.isEmpty()) {
            YHEmpty(Icons.Rounded.Eco, "No available plots", "Try joining the waitlist instead.")
        } else {
            LazyColumn(contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                item { Text("Choose a plot to reserve. The organizer will confirm shortly.", style = YHType.subheadline, color = YH.muted) }
                items(available, key = { it.id }) { plot ->
                    YHCard(onClick = if (reservingId == null) ({
                        scope.launch {
                            reservingId = plot.id
                            error = null
                            try {
                                ApiClient.reservePlot(gardenId, plot.id)
                                Haptics.success()
                                onReserved()
                                onDismiss()
                            } catch (e: Exception) {
                                error = e.userMessage
                                Haptics.error()
                            } finally {
                                reservingId = null
                            }
                        }
                    }) else null) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            Box(Modifier.size(44.dp).clip(RoundedCornerShape(10.dp)).background(YH.lime), contentAlignment = Alignment.Center) {
                                Icon(Icons.Rounded.Eco, null, tint = YH.ink)
                            }
                            Column(Modifier.weight(1f)) {
                                Text(plot.displayLabel, style = YHType.bodyMedium, color = YH.ink)
                                val bits = listOfNotNull(
                                    plot.size?.takeIf { it.isNotEmpty() },
                                    plot.sunExposure?.takeIf { it.isNotEmpty() }?.let { "${it.replace('_', ' ').replaceFirstChar(Char::uppercase)} sun" },
                                )
                                if (bits.isNotEmpty()) Text(bits.joinToString(" · "), style = YHType.caption, color = YH.muted)
                            }
                            if (reservingId == plot.id) CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                            else Icon(Icons.AutoMirrored.Rounded.ArrowForward, null, tint = YH.muted)
                        }
                    }
                }
                error?.let { item { YHInlineError(it) } }
            }
        }
    }
}

/** Waitlist join — optional size preference and notes. */
@Composable
fun WaitlistJoinSheet(gardenId: Int, onDismiss: () -> Unit, onJoined: () -> Unit) {
    var sizePref by remember { mutableStateOf("") }
    var notes by remember { mutableStateOf("") }
    var submitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    YHSheet(onDismiss, title = "Join Waitlist", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    Text("Tell the organizer what you're looking for. Both fields are optional.", style = YHType.subheadline, color = YH.muted)
                    YHTextField(sizePref, { sizePref = it }, label = "Plot size preference", placeholder = "e.g. 4×8 ft or larger",
                        textStyle = YHType.body.copy(color = YH.ink))
                    YHTextField(notes, { notes = it }, label = "Notes for the organizer", placeholder = "Anything they should know?",
                        singleLine = false, minLines = 4, textStyle = YHType.body.copy(color = YH.ink), autoCorrect = true)
                }
            }
            error?.let { YHInlineError(it) }
            YHButton("Join Waitlist", icon = Icons.Rounded.PersonAdd, isLoading = submitting) {
                scope.launch {
                    submitting = true
                    error = null
                    try {
                        ApiClient.joinWaitlist(gardenId, sizePref.trim(), notes.trim())
                        Haptics.success()
                        onJoined()
                        onDismiss()
                    } catch (e: Exception) {
                        error = e.userMessage
                        Haptics.error()
                    } finally {
                        submitting = false
                    }
                }
            }
        }
    }
}
