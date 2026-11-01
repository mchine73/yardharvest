package app.yardharvest.manager.ui.shifts

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
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Group
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.CreateShiftBody
import app.yardharvest.manager.api.cancelShiftSignup
import app.yardharvest.manager.api.createShift
import app.yardharvest.manager.api.listShifts
import app.yardharvest.manager.api.signUpForShift
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Dates
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.VolunteerShift
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDateChip
import app.yardharvest.manager.ui.brand.YHDateRow
import app.yardharvest.manager.ui.brand.YHEmpty
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
import app.yardharvest.manager.ui.events.repeatOptions
import java.time.LocalDate
import java.time.LocalTime
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.launch

@Composable
fun ShiftsScreen(garden: Garden) {
    var shifts by remember { mutableStateOf<List<VolunteerShift>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showCreate by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    // SHIFTS capability, with the identity fallback for pre-roles payloads.
    val canCreate = garden.can("shifts") || (AuthManager.currentUser?.id?.let { it == garden.organizerId } ?: false)

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { shifts = ApiClient.listShifts(garden.id, "upcoming") } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    YHScreen("Volunteer Shifts", actions = { if (canCreate) YHBarIcon(Icons.Rounded.AddCircle, "Create", tint = YH.ink) { showCreate = true } }) {
        YHLoadable(loading, shifts.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3,
            empty = { YHEmpty(Icons.Rounded.Group, "No shifts scheduled", "Check back when shifts are posted.") }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    items(shifts, key = { it.id }) { s ->
                        ShiftCard(
                            s,
                            onSignup = {
                                scope.launch {
                                    try { ApiClient.signUpForShift(garden.id, s.id); load(false); Haptics.success() }
                                    catch (e: Exception) { error = e.userMessage; Haptics.error() }
                                }
                            },
                            onCancel = {
                                scope.launch {
                                    try { ApiClient.cancelShiftSignup(garden.id, s.id); load(false) }
                                    catch (e: Exception) { error = e.userMessage }
                                }
                            },
                        )
                    }
                    error?.let { item { YHInlineError(it) } }
                }
            }
        }
    }
    if (showCreate) CreateShiftSheet(garden, onDismiss = { showCreate = false }) { scope.launch { load(false) } }
}

@Composable
private fun ShiftCard(shift: VolunteerShift, onSignup: () -> Unit, onCancel: () -> Unit) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                shift.shiftDate?.let { YHDateChip(it, size = 50.dp) }
                Column(Modifier.weight(1f)) {
                    Text(shift.title, style = YHType.bodyMedium, color = YH.ink)
                    shift.timeRange?.let { Text(it, style = YHType.caption, color = YH.muted) }
                }
            }
            if (!shift.description.isNullOrEmpty()) Text(shift.description, style = YHType.subheadline, color = YH.muted, maxLines = 2)
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Rounded.Group, null, tint = YH.ink, modifier = Modifier.size(14.dp))
                Text(" ${shift.signupCount}${shift.maxVolunteers?.let { "/$it" } ?: ""} signed up", style = YHType.caption, color = YH.ink, modifier = Modifier.weight(1f))
                if (shift.userSignedUp == true) {
                    Pill("Cancel", Icons.Rounded.Close, YH.surface, YH.muted) { Haptics.tap(); onCancel() }
                } else {
                    Pill("Sign Up", Icons.Rounded.Check, YH.lime, YH.ink, enabled = !shift.isFull) { Haptics.confirm(); onSignup() }
                }
            }
        }
    }
}

@Composable
private fun Pill(label: String, icon: androidx.compose.ui.graphics.vector.ImageVector, bg: androidx.compose.ui.graphics.Color,
                 fg: androidx.compose.ui.graphics.Color, enabled: Boolean = true, onClick: () -> Unit) {
    Row(
        Modifier.alpha(if (enabled) 1f else 0.45f).clip(RoundedCornerShape(50)).background(bg)
            .clickable(enabled = enabled, onClick = onClick).padding(horizontal = 12.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Icon(icon, null, tint = fg, modifier = Modifier.size(14.dp))
        Text(label, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = fg)
    }
}

/** Create a volunteer shift (SHIFTS capability; Garden Pro server-side). */
@Composable
private fun CreateShiftSheet(garden: Garden, onDismiss: () -> Unit, onCreated: () -> Unit) {
    var title by remember { mutableStateOf("") }
    var description by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(LocalDate.now().plusDays(1)) }
    var start by remember { mutableStateOf(LocalTime.of(9, 0)) }
    var end by remember { mutableStateOf(LocalTime.of(11, 0)) }
    var hasCap by remember { mutableStateOf(true) }
    var maxVolunteers by remember { mutableIntStateOf(6) }
    var recurring by remember { mutableStateOf("none") }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val timesValid = end > start
    val clock = DateTimeFormatter.ofPattern("HH:mm")

    fun save() {
        scope.launch {
            saving = true
            error = null
            try {
                ApiClient.createShift(
                    garden.id,
                    CreateShiftBody(title.trim(), description.trim(), Dates.ymd(date), start.format(clock), end.format(clock),
                        if (hasCap) maxVolunteers else null, recurring),
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
        { if (!saving) onDismiss() }, title = "New Shift",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, enabled = !saving, onClick = onDismiss) },
        trailing = {
            if (saving) CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
            else YHBarButton("Create", enabled = title.isNotBlank() && timesValid) { save() }
        },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHFormSection("What") {
                YHFormTextField(title, { title = it }, "Title (e.g. Watering & weeding)")
                YHFormDivider()
                YHFormTextField(description, { description = it }, "Description (optional)", singleLine = false, minLines = 2)
            }
            YHFormSection("When") {
                YHDateRow("Date", date) { date = it }
                YHFormDivider()
                YHTimeRow("Starts", start) { start = it }
                YHFormDivider()
                YHTimeRow("Ends", end) { end = it }
                if (!timesValid) {
                    Text("The shift has to end after it starts.", style = YHType.caption, color = YH.danger,
                        modifier = Modifier.padding(horizontal = YH.Space.md, vertical = 6.dp))
                }
                YHFormDivider()
                YHPickerRow("Repeats", repeatOptions, repeatOptions.first { it.first == recurring }, { it.second }) { recurring = it.first }
                if (recurring != "none") {
                    Text("Creates this shift plus the next 8 occurrences.", style = YHType.caption, color = YH.muted,
                        modifier = Modifier.padding(horizontal = YH.Space.md, vertical = 8.dp))
                }
            }
            YHFormSection("Volunteers") {
                YHToggleRow("Limit spots", hasCap) { hasCap = it }
                if (hasCap) {
                    YHFormDivider()
                    YHStepperRow("Max $maxVolunteers people", "", maxVolunteers > 1, maxVolunteers < 100, { maxVolunteers-- }, { maxVolunteers++ })
                }
            }
            error?.let { YHInlineError(it) }
        }
    }
}
