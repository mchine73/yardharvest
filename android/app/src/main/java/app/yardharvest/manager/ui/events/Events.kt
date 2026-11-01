package app.yardharvest.manager.ui.events

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
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
import androidx.compose.material.icons.rounded.AddCircle
import androidx.compose.material.icons.rounded.CalendarMonth
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableDoubleStateOf
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.CreateEventBody
import app.yardharvest.manager.api.cancelRsvp
import app.yardharvest.manager.api.createEvent
import app.yardharvest.manager.api.listEvents
import app.yardharvest.manager.api.rsvpEvent
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenEvent
import app.yardharvest.manager.model.RsvpStatus
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDateChip
import app.yardharvest.manager.ui.brand.YHDateRow
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHFilterChips
import app.yardharvest.manager.ui.brand.YHFormDivider
import app.yardharvest.manager.ui.brand.YHFormSection
import app.yardharvest.manager.ui.brand.YHFormTextField
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPickerRow
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHStepperRow
import app.yardharvest.manager.ui.brand.YHTimeRow
import app.yardharvest.manager.ui.brand.YHToggleRow
import app.yardharvest.manager.ui.brand.YHType
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.launch

private enum class EventFilter(val raw: String, val label: String) { Upcoming("upcoming", "Upcoming"), Past("past", "Past"), All("all", "All") }

@Composable
fun EventsScreen(garden: Garden) {
    var events by remember { mutableStateOf<List<GardenEvent>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(EventFilter.Upcoming) }
    var showCreate by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    // EVENTS capability — organizer, co-organizer, volunteer lead. Identity
    // fallback covers payloads that predate roles; the backend enforces either way.
    val canCreate = garden.can("events") || (AuthManager.currentUser?.id?.let { it == garden.organizerId } ?: false)

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { events = ApiClient.listEvents(garden.id, filter.raw) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id, filter) { load() }

    fun replace(updated: GardenEvent) { events = events.map { if (it.id == updated.id) updated else it } }

    YHScreen("Events", actions = { if (canCreate) YHBarIcon(Icons.Rounded.AddCircle, "Create", tint = YH.ink) { showCreate = true } }) {
        YHLoadable(loading, events.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3,
            empty = {
                Column {
                    Row(Modifier.padding(YH.Space.md)) { YHFilterChips(filter, EventFilter.entries, { it.label }) { filter = it } }
                    YHEmpty(Icons.Rounded.CalendarMonth, "No events yet", "Volunteer workdays and meetings will show up here.")
                }
            }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item { YHFilterChips(filter, EventFilter.entries, { it.label }) { filter = it } }
                    items(events, key = { it.id }) { e ->
                        EventCard(
                            e,
                            onRsvp = { status ->
                                scope.launch {
                                    try {
                                        replace(ApiClient.rsvpEvent(garden.id, e.id, status))
                                        Haptics.success()
                                    } catch (ex: Exception) { error = ex.userMessage; Haptics.error() }
                                }
                            },
                            onCancel = {
                                scope.launch {
                                    try { replace(ApiClient.cancelRsvp(garden.id, e.id)) } catch (ex: Exception) { error = ex.userMessage }
                                }
                            },
                        )
                    }
                    error?.let { item { YHInlineError(it) } }
                }
            }
        }
    }
    if (showCreate) CreateEventSheet(garden, onDismiss = { showCreate = false }) { scope.launch { load(false) } }
}

@Composable
private fun EventCard(event: GardenEvent, onRsvp: (RsvpStatus) -> Unit, onCancel: () -> Unit) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                event.eventDate?.let { YHDateChip(it, lime = true, size = 50.dp) }
                Column(Modifier.weight(1f)) {
                    Text(event.title, style = YHType.bodyMedium, color = YH.ink)
                    event.eventDate?.let { Text(Fmt.time(it), style = YHType.caption, color = YH.muted) }
                }
            }
            if (!event.description.isNullOrEmpty()) Text(event.description, style = YHType.subheadline, color = YH.muted, maxLines = 2)
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Rounded.Group, null, tint = YH.ink, modifier = Modifier.size(14.dp))
                Text("${event.rsvpGoing} going", style = YHType.caption, color = YH.ink, modifier = Modifier.weight(1f))
                RsvpButton("Going", event.userRsvp == "going") { onRsvp(RsvpStatus.Going) }
                RsvpButton("Maybe", event.userRsvp == "maybe") { onRsvp(RsvpStatus.Maybe) }
                if (event.userRsvp != null) {
                    Icon(Icons.Rounded.Cancel, "Clear RSVP", tint = YH.muted,
                        modifier = Modifier.size(26.dp).clip(RoundedCornerShape(50)).clickable { Haptics.tap(); onCancel() })
                }
            }
        }
    }
}

@Composable
private fun RsvpButton(label: String, selected: Boolean, onClick: () -> Unit) {
    Text(
        label, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = if (selected) YH.ink else YH.muted,
        modifier = Modifier.clip(RoundedCornerShape(50)).background(if (selected) YH.lime else YH.surface)
            .clickable { Haptics.tap(); onClick() }.padding(horizontal = 12.dp, vertical = 6.dp),
    )
}

private val eventTypes = listOf("workday" to "Workday", "workshop" to "Workshop", "social" to "Social", "meeting" to "Meeting", "harvest_day" to "Harvest Day")
val repeatOptions = listOf("none" to "One-time", "weekly" to "Weekly", "biweekly" to "Every 2 weeks", "monthly" to "Monthly")

/** Create an event from the phone — the web's event form, field-for-field. */
@Composable
private fun CreateEventSheet(garden: Garden, onDismiss: () -> Unit, onCreated: () -> Unit) {
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var type by remember { mutableStateOf("workday") }
    // Next 9:00 AM, like the iOS default.
    val nine = LocalTime.of(9, 0)
    var date by remember { mutableStateOf(if (LocalTime.now() < nine) LocalDate.now() else LocalDate.now().plusDays(1)) }
    var time by remember { mutableStateOf(nine) }
    var duration by remember { mutableDoubleStateOf(2.0) }
    var hasCap by remember { mutableStateOf(false) }
    var maxVolunteers by remember { mutableIntStateOf(10) }
    var recurring by remember { mutableStateOf("none") }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun save() {
        scope.launch {
            saving = true
            error = null
            try {
                // Naive local datetime — the backend stores garden-local time.
                val stamp = LocalDateTime.of(date, time).format(DateTimeFormatter.ofPattern("yyyy-MM-dd'T'HH:mm:ss"))
                ApiClient.createEvent(
                    garden.id,
                    CreateEventBody(title.trim(), description.trim(), type, stamp, duration, if (hasCap) maxVolunteers else null, recurring),
                )
                Haptics.success()
                onCreated()
                onDismiss()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                saving = false
            }
        }
    }

    YHSheet(
        { if (!saving) onDismiss() }, title = "New Event",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, enabled = !saving, onClick = onDismiss) },
        trailing = {
            if (saving) CircularProgressIndicator(Modifier.size(20.dp).padding(end = 4.dp), color = YH.ink, strokeWidth = 2.dp)
            else YHBarButton("Create", enabled = title.isNotBlank()) { save() }
        },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHFormSection("What") {
                YHFormTextField(title, { title = it }, "Title (e.g. Spring planting day)")
                YHFormDivider()
                YHPickerRow("Type", eventTypes, eventTypes.first { it.first == type }, { it.second }) { type = it.first }
                YHFormDivider()
                YHFormTextField(description, { description = it }, "Description (optional)", singleLine = false, minLines = 2)
            }
            YHFormSection("When") {
                YHDateRow("Date", date) { date = it }
                YHFormDivider()
                YHTimeRow("Starts", time) { time = it }
                YHFormDivider()
                YHStepperRow(
                    "Duration",
                    if (duration == Math.rint(duration)) "${duration.toInt()}h" else "%.1fh".format(duration),
                    canDecrement = duration > 0.5, canIncrement = duration < 12,
                    onDecrement = { duration = (duration - 0.5).coerceAtLeast(0.5) },
                    onIncrement = { duration = (duration + 0.5).coerceAtMost(12.0) },
                )
                YHFormDivider()
                YHPickerRow("Repeats", repeatOptions, repeatOptions.first { it.first == recurring }, { it.second }) { recurring = it.first }
                if (recurring != "none") {
                    Text("Creates this event plus the next 8 occurrences.", style = YHType.caption, color = YH.muted,
                        modifier = Modifier.padding(horizontal = YH.Space.md, vertical = 8.dp))
                }
            }
            YHFormSection("Volunteers") {
                YHToggleRow("Limit spots", hasCap) { hasCap = it }
                if (hasCap) {
                    YHFormDivider()
                    YHStepperRow("Max $maxVolunteers people", "", maxVolunteers > 1, maxVolunteers < 500,
                        { maxVolunteers-- }, { maxVolunteers++ })
                }
            }
            error?.let { YHInlineError(it) }
        }
    }
}
