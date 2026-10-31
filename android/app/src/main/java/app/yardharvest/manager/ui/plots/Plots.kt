package app.yardharvest.manager.ui.plots

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
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.Build
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Edit
import androidx.compose.material.icons.rounded.GridView
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material.icons.rounded.ManageAccounts
import androidx.compose.material.icons.rounded.PendingActions
import androidx.compose.material.icons.rounded.PersonAdd
import androidx.compose.material.icons.rounded.ShoppingBasket
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.EditPlotBody
import app.yardharvest.manager.api.adminEditPlot
import app.yardharvest.manager.api.adminListPlots
import app.yardharvest.manager.api.assignPlot
import app.yardharvest.manager.api.confirmReservation
import app.yardharvest.manager.api.declineReservation
import app.yardharvest.manager.api.listGardenMembers
import app.yardharvest.manager.api.releasePlot
import app.yardharvest.manager.api.toggleMaintenance
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Dates
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenMember
import app.yardharvest.manager.model.Plot
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHConfirmDialog
import app.yardharvest.manager.ui.brand.YHDateRow
import app.yardharvest.manager.ui.brand.YHDivider
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHFilterChips
import app.yardharvest.manager.ui.brand.YHFormDivider
import app.yardharvest.manager.ui.brand.YHFormSection
import app.yardharvest.manager.ui.brand.YHFormTextField
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPickerRow
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHToggleRow
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import java.time.LocalDate
import java.time.ZoneId
import kotlinx.coroutines.launch

private enum class PlotFilter(val raw: String, val label: String) {
    All("all", "All"), Available("available", "Available"), Assigned("assigned", "Assigned"),
    Reserved("reserved", "Pending"), Maintenance("maintenance", "Maintenance"),
}

/**
 * Manager-side plot roster. Tapping a plot pushes the detail screen with the
 * full action set. The drag-and-drop designer stays a website feature.
 */
@Composable
fun PlotsScreen(garden: Garden) {
    val nav = LocalNav.current
    var plots by remember { mutableStateOf<List<Plot>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(PlotFilter.All) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { plots = ApiClient.adminListPlots(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }
    val filtered = if (filter == PlotFilter.All) plots else plots.filter { it.status == filter.raw }
    val pending = plots.count { it.status == "reserved" }

    // The waitlist lives here (it lost its dashboard tile to Community), the
    // same pairing as the web's Plots tab.
    YHScreen("Plots", actions = { YHBarIcon(Icons.Rounded.ManageAccounts, "Waitlist", tint = YH.ink) { nav.push(Dest.Waitlist(garden)) } }) {
        YHLoadable(loading, plots.isEmpty(), error, { scope.launch { load() } },
            empty = { YHEmpty(Icons.Rounded.GridView, "No plots yet", "Design your garden layout on the website to create plots, then manage them here.") }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    if (pending > 0) item {
                        YHBand {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                Icon(Icons.Rounded.PendingActions, null, tint = YH.ink, modifier = Modifier.size(26.dp))
                                Column {
                                    Text(if (pending == 1) "1 reservation waiting" else "$pending reservations waiting", style = YHType.title3, color = YH.ink)
                                    Text("Members reserved specific plots from your garden page. Confirm or decline them below.",
                                        style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f))
                                }
                            }
                        }
                    }
                    item { YHFilterChips(filter, PlotFilter.entries, { it.label }) { filter = it } }
                    items(filtered, key = { it.id }) { plot ->
                        PlotRow(plot) { nav.push(Dest.PlotDetail(garden, plot) { scope.launch { load(false) } }) }
                    }
                    if (filtered.isEmpty()) item {
                        YHCard { Text("No ${filter.label.lowercase()} plots to show.", style = YHType.subheadline, color = YH.muted) }
                    }
                }
            }
        }
    }
}

@Composable
fun PlotRow(plot: Plot, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            NumberTile(plot, 46)
            Column(Modifier.weight(1f)) {
                Text(plot.displayLabel, style = YHType.bodyMedium, color = YH.ink)
                val parts = buildList {
                    plot.size?.takeIf { it.isNotEmpty() }?.let { add(it) }
                    when {
                        plot.assignedToName != null -> add(plot.assignedToName)
                        plot.reservedByName != null -> add("Reserved by ${plot.reservedByName}")
                    }
                    if (isEmpty()) add("Unassigned")
                }
                Text(parts.joinToString(" · "), style = YHType.caption, color = YH.muted, maxLines = 1)
            }
            PlotStatusPill(plot.status)
        }
    }
}

/** Square number chip — echoes the web layout grid without pretending to be one. */
@Composable
private fun NumberTile(plot: Plot, size: Int) {
    Box(
        Modifier.size(size.dp).clip(RoundedCornerShape(YH.Radius.md)).background(if (plot.status == "assigned") YH.lime else YH.surface),
        contentAlignment = Alignment.Center,
    ) { Text("#${plot.plotNumber}", fontSize = if (size > 50) 20.sp else 15.sp, fontWeight = FontWeight.Bold, color = YH.ink, maxLines = 1) }
}

/** One source of truth for plot status colors. */
@Composable
fun PlotStatusPill(status: String) {
    when (status) {
        "available" -> YHPill("Available", tint = YH.ink, background = YH.lime)
        "assigned" -> YHPill("Assigned", tint = YH.ink, background = YH.surface)
        "reserved" -> YHPill("Pending", tint = Color.White, background = YH.warning)
        "maintenance" -> YHPill("Maintenance", tint = Color.White, background = YH.muted)
        else -> YHPill(status.replaceFirstChar(Char::uppercase), tint = YH.ink, background = YH.surface)
    }
}

private fun sunLabel(raw: String?): String? = when (raw) {
    "full_sun" -> "Full Sun"
    "partial_shade" -> "Partial Shade"
    "full_shade" -> "Full Shade"
    else -> null
}

/**
 * One plot with every manager action the web dashboard offers: confirm or
 * decline a reservation, assign, release, toggle maintenance, edit details.
 */
@Composable
fun PlotDetailScreen(garden: Garden, initial: Plot, onChange: () -> Unit) {
    var plot by remember { mutableStateOf(initial) }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var confirmRelease by remember { mutableStateOf(false) }
    var confirmDecline by remember { mutableStateOf(false) }
    var showAssign by remember { mutableStateOf(false) }
    var showEdit by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    /** Partial responses (edit) lack occupant fields — merge rather than trust every null. */
    fun merged(new: Plot, old: Plot) = new.copy(
        size = new.size ?: old.size,
        locationNotes = new.locationNotes ?: old.locationNotes,
        assignedToEmail = new.assignedToEmail ?: old.assignedToEmail,
        harvestTotalLbs = new.harvestTotalLbs ?: old.harvestTotalLbs,
        harvestCount = new.harvestCount ?: old.harvestCount,
        gridRow = new.gridRow ?: old.gridRow,
        gridCol = new.gridCol ?: old.gridCol,
        customName = new.customName ?: old.customName,
        soilType = new.soilType ?: old.soilType,
        sunExposure = new.sunExposure ?: old.sunExposure,
    )

    fun run(label: String, work: suspend () -> Plot) {
        if (working) return
        scope.launch {
            working = true
            error = null
            info = null
            try {
                plot = merged(work(), plot)
                info = label
                Haptics.success()
                onChange()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                working = false
            }
        }
    }

    YHScreen(plot.displayLabel) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                    NumberTile(plot, 56)
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(plot.displayLabel, style = YHType.title3, color = YH.ink)
                        PlotStatusPill(plot.status)
                    }
                }
            }
            if (plot.status == "reserved") PersonCard("PENDING RESERVATION", plot.reservedByName, plot.reservedAt?.let { "Requested ${Fmt.date(it)}" })
            if (plot.assignedToId != null) {
                YHCard {
                    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        YHSectionLabel("Assigned to", Modifier.padding(start = 0.dp))
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHAvatar(plot.assignedToName ?: "?", size = 42.dp)
                            Column {
                                Text(plot.assignedToName ?: "Member", style = YHType.bodyMedium, color = YH.ink)
                                plot.assignedDate?.let { Text("Since ${Fmt.date(it)}", style = YHType.caption, color = YH.muted) }
                            }
                        }
                        val lbs = plot.harvestTotalLbs ?: 0.0
                        if (lbs > 0) {
                            YHDivider()
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Icon(Icons.Rounded.ShoppingBasket, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                                Text("%.1f lb harvested".format(lbs), style = YHType.caption, color = YH.muted, modifier = Modifier.weight(1f))
                                Text("${plot.harvestCount ?: 0} logs", style = YHType.caption, color = YH.muted)
                            }
                        }
                    }
                }
            }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Details", Modifier.padding(start = 0.dp))
                    DetailRow("Size", plot.size)
                    DetailRow("Soil", plot.soilType?.takeIf { it.isNotEmpty() }?.replaceFirstChar(Char::uppercase))
                    DetailRow("Sun", sunLabel(plot.sunExposure))
                    DetailRow("Renews", plot.renewalDate?.let { Fmt.date(it) })
                    if (!plot.locationNotes.isNullOrEmpty()) {
                        YHDivider()
                        Text(plot.locationNotes!!, style = YHType.subheadline, color = YH.ink)
                    }
                }
            }
            Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                when (plot.status) {
                    "reserved" -> {
                        YHButton("Confirm Reservation", icon = Icons.Rounded.Check, style = YHButtonStyle.Lime, isLoading = working) {
                            run("Reservation confirmed — the member has been notified.") { ApiClient.confirmReservation(garden.id, plot.id) }
                        }
                        YHButton("Decline", icon = Icons.Rounded.Close, style = YHButtonStyle.Ghost) { confirmDecline = true }
                    }
                    "available" -> YHButton("Assign to Member", icon = Icons.Rounded.PersonAdd, isLoading = working) { showAssign = true }
                    "assigned" -> YHButton("Release Plot", icon = Icons.Rounded.Cancel, style = YHButtonStyle.Ghost, isLoading = working) { confirmRelease = true }
                }
                YHButton(
                    if (plot.status == "maintenance") "End Maintenance" else "Mark Under Maintenance",
                    icon = Icons.Rounded.Build, style = YHButtonStyle.Ghost, isLoading = working,
                ) {
                    if (!working) scope.launch {
                        working = true
                        error = null
                        info = null
                        try {
                            val resp = ApiClient.toggleMaintenance(garden.id, plot.id)
                            plot = plot.copy(status = resp.status)
                            info = resp.message
                            Haptics.success()
                            onChange()
                        } catch (e: Exception) {
                            error = e.userMessage
                            Haptics.error()
                        } finally {
                            working = false
                        }
                    }
                }
                YHButton("Edit Details", icon = Icons.Rounded.Edit, style = YHButtonStyle.Ghost) { showEdit = true }
            }
            info?.let { Text(it, style = YHType.subheadline, color = YH.ink) }
            error?.let { YHInlineError(it) }
        }
    }

    if (confirmRelease) YHConfirmDialog(
        "Release this plot?",
        "${plot.assignedToName ?: "The member"} loses the plot and it becomes available. This doesn't notify them — tell them first.",
        confirmText = "Release Plot", destructive = true,
        onConfirm = { run("Plot released — it's available again.") { ApiClient.releasePlot(garden.id, plot.id) } },
        onDismiss = { confirmRelease = false },
    )
    if (confirmDecline) YHConfirmDialog(
        "Decline this reservation?",
        "${plot.reservedByName ?: "The member"}'s request is declined and the plot becomes available again.",
        confirmText = "Decline Reservation", destructive = true,
        onConfirm = { run("Reservation declined.") { ApiClient.declineReservation(garden.id, plot.id) } },
        onDismiss = { confirmDecline = false },
    )
    if (showAssign) AssignMemberSheet(garden, onDismiss = { showAssign = false }) { member ->
        showAssign = false
        run("${plot.displayLabel} assigned to ${member.name}.") { ApiClient.assignPlot(garden.id, plot.id, member.userId) }
    }
    if (showEdit) EditPlotSheet(plot, onDismiss = { showEdit = false }) { body ->
        showEdit = false
        run("Plot updated.") { ApiClient.adminEditPlot(garden.id, plot.id, body) }
    }
}

@Composable
private fun PersonCard(label: String, name: String?, subtitle: String?) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSectionLabel(label, Modifier.padding(start = 0.dp))
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                YHAvatar(name ?: "?", size = 42.dp)
                Column {
                    Text(name ?: "Member", style = YHType.bodyMedium, color = YH.ink)
                    subtitle?.let { Text(it, style = YHType.caption, color = YH.muted) }
                }
            }
        }
    }
}

@Composable
private fun DetailRow(label: String, value: String?) {
    Row {
        Text(label, style = YHType.subheadline, color = YH.muted, modifier = Modifier.weight(1f))
        Text(value?.takeIf { it.isNotEmpty() } ?: "—", style = YHType.bodyMedium, color = YH.ink)
    }
}

/** Member picker for assigning an available plot — the garden's current roster. */
@Composable
private fun AssignMemberSheet(garden: Garden, onDismiss: () -> Unit, onPick: (GardenMember) -> Unit) {
    var members by remember { mutableStateOf<List<GardenMember>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    suspend fun load() {
        loading = true
        error = null
        try { members = ApiClient.listGardenMembers(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(Unit) { load() }
    YHSheet(onDismiss, title = "Assign to Member", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        YHLoadable(loading, members.isEmpty(), error, { scope.launch { load() } },
            empty = { YHEmpty(Icons.Rounded.Group, "No members yet", "Members appear here once they join your garden.") }) {
            LazyColumn(contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                items(members, key = { it.userId }) { m ->
                    YHCard(onClick = { onPick(m) }) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            YHAvatar(m.name, size = 42.dp)
                            Column(Modifier.weight(1f)) {
                                Text(m.name, style = YHType.bodyMedium, color = YH.ink)
                                Text(if (m.isOrganizer) "Organizer" else "Plot ${m.plotNumber ?: "—"}", style = YHType.caption, color = YH.muted)
                            }
                            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                        }
                    }
                }
            }
        }
    }
}

/** Field-for-field mirror of the web's inline plot editor. */
@Composable
private fun EditPlotSheet(plot: Plot, onDismiss: () -> Unit, onSave: (EditPlotBody) -> Unit) {
    var customName by remember { mutableStateOf(plot.customName ?: "") }
    var size by remember { mutableStateOf(plot.size ?: "") }
    var soil by remember { mutableStateOf(plot.soilType ?: "") }
    var sun by remember { mutableStateOf(plot.sunExposure ?: "") }
    var hasRenewal by remember { mutableStateOf(plot.renewalDate != null) }
    var renewal by remember { mutableStateOf(plot.renewalDate?.atZone(ZoneId.systemDefault())?.toLocalDate() ?: LocalDate.now()) }
    var notes by remember { mutableStateOf(plot.locationNotes ?: "") }
    val soilOptions = listOf("", "clay", "loam", "sandy", "silt", "mixed")
    val sunOptions = listOf("", "full_sun", "partial_shade", "full_shade")

    YHSheet(
        onDismiss, title = "Edit Plot",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) },
        trailing = {
            YHBarButton("Save") {
                onSave(
                    EditPlotBody(
                        custom_name = customName.trim(), size = size.trim(), soil_type = soil, sun_exposure = sun,
                        // An empty string clears the date server-side.
                        renewal_date = if (hasRenewal) Dates.ymd(renewal) else "",
                        location_notes = notes.trim(),
                    ),
                )
            }
        },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHFormSection("Name & size") {
                YHFormTextField(customName, { customName = it }, "Custom name (e.g. Sunny Corner)")
                YHFormDivider()
                YHFormTextField(size, { size = it }, "Size (e.g. 4x8 ft)")
            }
            YHFormSection("Growing conditions") {
                YHPickerRow("Soil type", soilOptions, soil, { if (it.isEmpty()) "—" else it.replaceFirstChar(Char::uppercase) }) { soil = it }
                YHFormDivider()
                YHPickerRow("Sun exposure", sunOptions, sun, { sunLabel(it) ?: "—" }) { sun = it }
            }
            YHFormSection("Renewal") {
                YHToggleRow("Has renewal date", hasRenewal) { hasRenewal = it }
                if (hasRenewal) {
                    YHFormDivider()
                    YHDateRow("Renews on", renewal) { renewal = it }
                }
            }
            YHFormSection("Location notes") {
                YHFormTextField(notes, { notes = it }, "e.g. NW corner, next to the shed", singleLine = false, minLines = 2)
            }
        }
    }
}
