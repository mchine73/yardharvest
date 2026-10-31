package app.yardharvest.manager.ui.admin

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.slideOutVertically
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.Assignment
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.GroupOff
import androidx.compose.material.icons.rounded.Inbox
import androidx.compose.material.icons.rounded.Straighten
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import app.yardharvest.manager.api.WaitlistApproveResponse
import app.yardharvest.manager.api.adminListPlots
import app.yardharvest.manager.api.adminListWaitlist
import app.yardharvest.manager.api.approveWaitlistEntry
import app.yardharvest.manager.api.confirmReservation
import app.yardharvest.manager.api.declineReservation
import app.yardharvest.manager.api.declineWaitlistEntry
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.Plot
import app.yardharvest.manager.model.WaitlistEntry
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHIconTile
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import java.time.Instant
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

/** A small lime confirmation that floats at the top of a list screen. */
@Composable
private fun ActionToast(text: String?) {
    Box(Modifier.fillMaxSize().padding(top = 8.dp), contentAlignment = Alignment.TopCenter) {
        AnimatedVisibility(text != null, enter = slideInVertically() + fadeIn(), exit = slideOutVertically() + fadeOut()) {
            Text(text ?: "", style = YHType.captionMed, color = YH.ink,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 14.dp, vertical = 8.dp))
        }
    }
}

private fun CoroutineScope.flash(set: (String?) -> Unit, text: String) = launch {
    set(text)
    delay(1800)
    set(null)
}

/**
 * The "Reviews" inbox: plot reservations awaiting the manager, with the wall
 * moderation entry pinned above — the dashboard tile's count includes flagged
 * posts, so they must never hide behind an "All caught up".
 */
@Composable
fun AdminReviewsScreen(garden: Garden) {
    val nav = LocalNav.current
    var plots by remember { mutableStateOf<List<Plot>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val working = remember { mutableStateListOf<Int>() }
    var toast by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { plots = ApiClient.adminListPlots(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }
    val reserved = plots.filter { it.status == "reserved" }.sortedBy { it.reservedAt ?: Instant.MIN }

    fun act(plot: Plot, approve: Boolean) {
        scope.launch {
            working += plot.id
            try {
                val updated = if (approve) ApiClient.confirmReservation(garden.id, plot.id) else ApiClient.declineReservation(garden.id, plot.id)
                plots = if (plots.any { it.id == updated.id }) plots.map { if (it.id == updated.id) updated else it } else plots + updated
                if (approve) Haptics.success() else Haptics.warning()
                flash({ toast = it }, if (approve) "Approved ${plot.displayLabel}." else "Released ${plot.displayLabel}.")
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                working -= plot.id
            }
        }
    }

    YHScreen("Reviews") {
        Box(Modifier.fillMaxSize()) {
            Column(Modifier.fillMaxSize()) {
                Box(Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = YH.Space.sm)) {
                    YHCard(onClick = { nav.push(Dest.Moderation(garden)) }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHIconTile(Icons.Rounded.VerifiedUser, size = 36.dp, background = YH.lime)
                            Column(Modifier.weight(1f)) {
                                Text("Community wall", style = YHType.bodyMedium, color = YH.ink)
                                Text("Flagged and auto-denied posts", style = YHType.caption, color = YH.muted)
                            }
                            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                        }
                    }
                }
                YHLoadable(loading, reserved.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3,
                    empty = { YHEmpty(Icons.Rounded.Verified, "All caught up", "No plot reservations are waiting on your approval.") }) {
                    YHRefreshable({ load(false) }) {
                        LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                            item {
                                YHBand {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                        YHIconTile(Icons.AutoMirrored.Rounded.Assignment, size = 48.dp, background = YH.ink, foreground = YH.lime)
                                        Column {
                                            Text("${reserved.size} reservation${if (reserved.size == 1) "" else "s"}", style = YHType.title3, color = YH.ink)
                                            Text("Each is a member waiting for your approval to take the plot.", style = YHType.caption, color = YH.ink.copy(alpha = 0.75f))
                                        }
                                    }
                                }
                            }
                            items(reserved, key = { it.id }) { plot ->
                                val busy = plot.id in working
                                YHCard {
                                    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                            YHAvatar(plot.reservedByName ?: "—", size = 44.dp)
                                            Column(Modifier.weight(1f)) {
                                                Text(plot.reservedByName ?: "Unknown member", style = YHType.bodyMedium, color = YH.ink)
                                                Text(listOfNotNull(plot.displayLabel, plot.reservedAt?.let { Fmt.relative(it) }).joinToString(" · "),
                                                    style = YHType.caption, color = YH.muted)
                                            }
                                            YHPill("Pending", tint = YH.ink, background = YH.surface)
                                        }
                                        if (!plot.size.isNullOrEmpty()) {
                                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                                                Icon(Icons.Rounded.Straighten, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                                                Text(plot.size.replaceFirstChar(Char::uppercase), style = YHType.caption, color = YH.muted)
                                            }
                                        }
                                        Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                                            YHButton("Decline", Modifier.weight(1f), icon = Icons.Rounded.Cancel, style = YHButtonStyle.Ghost, enabled = !busy) { act(plot, false) }
                                            YHButton("Approve", Modifier.weight(1f), icon = Icons.Rounded.Verified, style = YHButtonStyle.Lime, isLoading = busy, enabled = !busy) { act(plot, true) }
                                        }
                                    }
                                }
                            }
                            error?.takeIf { reserved.isNotEmpty() }?.let { item { YHInlineError(it) } }
                        }
                    }
                }
            }
            ActionToast(toast)
        }
    }
}

/**
 * The waitlist in request order, with Decline and Offer Plot — which asks
 * which available plot to assign them onto.
 */
@Composable
fun AdminWaitlistScreen(garden: Garden) {
    var entries by remember { mutableStateOf<List<WaitlistEntry>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val working = remember { mutableStateListOf<Int>() }
    var toast by remember { mutableStateOf<String?>(null) }
    var offerTarget by remember { mutableStateOf<WaitlistEntry?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { entries = ApiClient.adminListWaitlist(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }
    val waiting = entries.filter { it.status == "waiting" }.sortedBy { it.requestedAt ?: Instant.MIN }
    fun replace(updated: WaitlistEntry) { entries = entries.map { if (it.id == updated.id) updated else it } }

    YHScreen("Waitlist") {
        Box(Modifier.fillMaxSize()) {
            YHLoadable(loading, waiting.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3,
                empty = { YHEmpty(Icons.Rounded.GroupOff, "No one on the waitlist", "Members who join the waitlist will show up here.") }) {
                YHRefreshable({ load(false) }) {
                    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        item {
                            YHBand {
                                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                    YHIconTile(Icons.Rounded.Group, size = 48.dp, background = YH.ink, foreground = YH.lime)
                                    Column {
                                        Text("${waiting.size} waiting", style = YHType.title3, color = YH.ink)
                                        Text("Listed in the order they signed up. Offer a plot when one frees up.", style = YHType.caption, color = YH.ink.copy(alpha = 0.75f))
                                    }
                                }
                            }
                        }
                        itemsIndexed(waiting, key = { _, e -> e.id }) { index, entry ->
                            val busy = entry.id in working
                            YHCard {
                                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                        YHAvatar(entry.userName, size = 44.dp)
                                        Column(Modifier.weight(1f)) {
                                            Text(entry.userName, style = YHType.bodyMedium, color = YH.ink)
                                            Text(listOfNotNull("#${index + 1}", entry.requestedAt?.let { Fmt.relative(it) }).joinToString(" · "),
                                                style = YHType.caption, color = YH.muted)
                                        }
                                        if (!entry.plotSizePref.isNullOrEmpty()) YHPill(entry.plotSizePref.replaceFirstChar(Char::uppercase), tint = YH.ink, background = YH.surface)
                                    }
                                    if (!entry.notes.isNullOrEmpty()) Text(entry.notes, style = YHType.subheadline, color = YH.muted, maxLines = 3)
                                    Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                                        YHButton("Decline", Modifier.weight(1f), icon = Icons.Rounded.Cancel, style = YHButtonStyle.Ghost, enabled = !busy) {
                                            scope.launch {
                                                working += entry.id
                                                try {
                                                    replace(ApiClient.declineWaitlistEntry(garden.id, entry.id))
                                                    Haptics.warning()
                                                    flash({ toast = it }, "Declined ${entry.userName}.")
                                                } catch (e: Exception) { error = e.userMessage; Haptics.error() }
                                                finally { working -= entry.id }
                                            }
                                        }
                                        YHButton("Offer Plot", Modifier.weight(1f), icon = Icons.Rounded.Verified, style = YHButtonStyle.Lime, isLoading = busy, enabled = !busy) {
                                            offerTarget = entry
                                        }
                                    }
                                }
                            }
                        }
                        error?.takeIf { waiting.isNotEmpty() }?.let { item { YHInlineError(it) } }
                    }
                }
            }
            ActionToast(toast)
        }
    }
    offerTarget?.let { entry ->
        OfferPlotSheet(garden, entry, onDismiss = { offerTarget = null }) { result ->
            offerTarget = null
            replace(result.waitlistEntry)
            Haptics.success()
            scope.flash({ toast = it }, "Assigned ${entry.userName} to ${result.plot.displayLabel}.")
        }
    }
}

/** Which available plot to assign the waitlisted member onto. */
@Composable
private fun OfferPlotSheet(garden: Garden, entry: WaitlistEntry, onDismiss: () -> Unit, onAssigned: (WaitlistApproveResponse) -> Unit) {
    var plots by remember { mutableStateOf<List<Plot>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var assigningId by remember { mutableStateOf<Int?>(null) }
    val scope = rememberCoroutineScope()
    suspend fun load() {
        loading = true
        error = null
        try { plots = ApiClient.adminListPlots(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(Unit) { load() }
    // Natural order, so plot 2 sorts before plot 10.
    val available = plots.filter { it.status == "available" }.sortedWith(compareBy<Plot>({ it.plotNumber.filter(Char::isDigit).toIntOrNull() ?: Int.MAX_VALUE }, { it.plotNumber }))

    YHSheet(onDismiss, title = "Offer Plot", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        YHLoadable(loading, available.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 4,
            empty = { YHEmpty(Icons.Rounded.Inbox, "No available plots", "There's no open plot to offer right now. Free one up first, then come back.") }) {
            LazyColumn(contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                item {
                    YHCard {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHAvatar(entry.userName, size = 40.dp)
                            Column {
                                Text(entry.userName, style = YHType.bodyMedium, color = YH.ink)
                                Text("Pick a plot to assign them onto.", style = YHType.caption, color = YH.muted)
                            }
                        }
                    }
                }
                items(available, key = { it.id }) { plot ->
                    YHCard(onClick = if (assigningId == null) ({
                        scope.launch {
                            assigningId = plot.id
                            try { onAssigned(ApiClient.approveWaitlistEntry(garden.id, entry.id, plot.id)) }
                            catch (e: Exception) { error = e.userMessage; Haptics.error() }
                            finally { assigningId = null }
                        }
                    }) else null) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHIconTile(Icons.Rounded.GridView, background = YH.lime)
                            Column(Modifier.weight(1f)) {
                                Text(plot.displayLabel, style = YHType.bodyMedium, color = YH.ink)
                                if (!plot.size.isNullOrEmpty()) Text(plot.size.replaceFirstChar(Char::uppercase), style = YHType.caption, color = YH.muted)
                            }
                            if (assigningId == plot.id) CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                            else Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                        }
                    }
                }
                error?.let { item { YHInlineError(it) } }
            }
        }
    }
}
