package app.yardharvest.manager.ui.brand

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Add
import androidx.compose.material.icons.rounded.ExpandMore
import androidx.compose.material.icons.rounded.Remove
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DatePickerDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TimePicker
import androidx.compose.material3.TimePickerDefaults
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.material3.rememberTimePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import app.yardharvest.manager.core.Haptics
import java.time.Instant
import java.time.LocalDate
import java.time.LocalTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle

// Branded stand-ins for the SwiftUI Form controls the iOS sheets use:
// sections, pickers, steppers, toggles, date and time pickers.

/** A titled card holding form rows — `Section("…") { … }` inside a Form. */
@Composable
fun YHFormSection(title: String?, content: @Composable ColumnScope.() -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        if (title != null) YHSectionLabel(title)
        YHCard(padding = 0.dp) {
            Column(content = content)
        }
    }
}

/** A plain label/value row inside a form section. */
@Composable
fun YHFormRow(
    label: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    onClick: (() -> Unit)? = null,
    trailing: @Composable () -> Unit = {},
) {
    Row(
        modifier
            .fillMaxWidth()
            .then(if (onClick != null) Modifier.clickable { Haptics.tap(); onClick() } else Modifier)
            .padding(horizontal = YH.Space.md, vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (icon != null) Icon(icon, null, tint = YH.ink, modifier = Modifier.size(20.dp))
        Text(label, style = YHType.body, color = YH.ink, modifier = Modifier.weight(1f))
        trailing()
    }
}

/** Hairline between rows in a form section, inset like iOS grouped lists. */
@Composable
fun YHFormDivider() = androidx.compose.material3.HorizontalDivider(Modifier.padding(start = YH.Space.md), thickness = 1.dp, color = YH.border)

/** Toggle row — `Toggle(isOn:) { Label(...) }`. */
@Composable
fun YHToggleRow(label: String, checked: Boolean, icon: ImageVector? = null, subtitle: String? = null, onCheckedChange: (Boolean) -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = YH.Space.md, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (icon != null) Icon(icon, null, tint = YH.ink, modifier = Modifier.size(20.dp))
        Column(Modifier.weight(1f)) {
            Text(label, style = YHType.bodyMedium, color = YH.ink)
            if (subtitle != null) Text(subtitle, style = YHType.caption, color = YH.muted)
        }
        YHSwitch(checked, onCheckedChange)
    }
}

/** Menu picker row — `Picker(...)` in `.menu` style. */
@Composable
fun <T> YHPickerRow(label: String, options: List<T>, selected: T, optionLabel: (T) -> String, onSelect: (T) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        YHFormRow(label, onClick = { open = true }) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(optionLabel(selected), style = YHType.body, color = YH.muted)
                Icon(Icons.Rounded.ExpandMore, null, tint = YH.muted, modifier = Modifier.size(18.dp))
            }
        }
        DropdownMenu(open, onDismissRequest = { open = false }, modifier = Modifier.background(YH.canvas)) {
            options.forEach { opt ->
                DropdownMenuItem(
                    text = { Text(optionLabel(opt), color = YH.ink, fontWeight = if (opt == selected) FontWeight.SemiBold else FontWeight.Normal) },
                    onClick = { Haptics.selection(); open = false; onSelect(opt) },
                )
            }
        }
    }
}

/** Stepper row — label on the left, − value + on the right. */
@Composable
fun YHStepperRow(label: String, valueLabel: String, canDecrement: Boolean, canIncrement: Boolean, onDecrement: () -> Unit, onIncrement: () -> Unit) {
    YHFormRow(label) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(valueLabel, style = YHType.body, color = YH.muted)
            StepButton(Icons.Rounded.Remove, canDecrement, onDecrement)
            StepButton(Icons.Rounded.Add, canIncrement, onIncrement)
        }
    }
}

@Composable
private fun StepButton(icon: ImageVector, enabled: Boolean, onClick: () -> Unit) {
    Box(
        Modifier.size(34.dp).clip(CircleShape).background(YH.surface).alpha(if (enabled) 1f else 0.4f)
            .clickable(enabled = enabled) { Haptics.selection(); onClick() },
        contentAlignment = Alignment.Center,
    ) { Icon(icon, null, tint = YH.ink, modifier = Modifier.size(18.dp)) }
}

private val dateFmt = DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM)
private val timeFmt = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT)

/** Date row that opens the Material date picker — `DatePicker(displayedComponents: .date)`. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YHDateRow(label: String, date: LocalDate, onChange: (LocalDate) -> Unit) {
    var open by remember { mutableStateOf(false) }
    YHFormRow(label, onClick = { open = true }) { ValueChip(dateFmt.format(date)) }
    if (open) {
        val state = rememberDatePickerState(initialSelectedDateMillis = date.atStartOfDay(ZoneOffset.UTC).toInstant().toEpochMilli())
        DatePickerDialog(
            onDismissRequest = { open = false },
            confirmButton = {
                TextButton(onClick = {
                    state.selectedDateMillis?.let { onChange(Instant.ofEpochMilli(it).atZone(ZoneOffset.UTC).toLocalDate()) }
                    open = false
                }) { Text("OK", color = YH.ink, fontWeight = FontWeight.SemiBold) }
            },
            dismissButton = { TextButton(onClick = { open = false }) { Text("Cancel", color = YH.muted) } },
            colors = DatePickerDefaults.colors(containerColor = YH.canvas),
        ) {
            DatePicker(
                state,
                colors = DatePickerDefaults.colors(
                    containerColor = YH.canvas, selectedDayContainerColor = YH.ink, selectedDayContentColor = Color.White,
                    todayDateBorderColor = YH.ink, todayContentColor = YH.ink,
                ),
            )
        }
    }
}

/** Time row that opens the Material time picker — `DatePicker(displayedComponents: .hourAndMinute)`. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YHTimeRow(label: String, time: LocalTime, onChange: (LocalTime) -> Unit) {
    var open by remember { mutableStateOf(false) }
    YHFormRow(label, onClick = { open = true }) { ValueChip(timeFmt.format(time)) }
    if (open) {
        val state = rememberTimePickerState(time.hour, time.minute)
        Dialog(onDismissRequest = { open = false }) {
            Column(
                Modifier.clip(RoundedCornerShape(24.dp)).background(YH.canvas).padding(20.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(label, style = YHType.headline, color = YH.ink, modifier = Modifier.padding(bottom = 16.dp))
                TimePicker(
                    state,
                    colors = TimePickerDefaults.colors(
                        clockDialColor = YH.surface, selectorColor = YH.ink,
                        timeSelectorSelectedContainerColor = YH.lime, timeSelectorSelectedContentColor = YH.ink,
                        periodSelectorSelectedContainerColor = YH.lime, periodSelectorSelectedContentColor = YH.ink,
                    ),
                )
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                    TextButton(onClick = { open = false }) { Text("Cancel", color = YH.muted) }
                    TextButton(onClick = { onChange(LocalTime.of(state.hour, state.minute)); open = false }) {
                        Text("OK", color = YH.ink, fontWeight = FontWeight.SemiBold)
                    }
                }
            }
        }
    }
}

@Composable
private fun ValueChip(text: String) {
    Text(
        text, color = YH.ink, fontSize = 15.sp,
        modifier = Modifier.clip(RoundedCornerShape(8.dp)).background(YH.surface).padding(horizontal = 10.dp, vertical = 6.dp),
    )
}

/** Segmented control — `Picker(...).pickerStyle(.segmented)`. */
@Composable
fun <T> YHSegmented(options: List<T>, selected: T, label: (T) -> String, onSelect: (T) -> Unit) {
    val shape = RoundedCornerShape(10.dp)
    Row(Modifier.fillMaxWidth().clip(shape).background(YH.surface).border(1.dp, YH.border, shape).padding(2.dp)) {
        options.forEach { opt ->
            val on = opt == selected
            Text(
                label(opt),
                fontSize = 13.sp,
                fontWeight = if (on) FontWeight.SemiBold else FontWeight.Medium,
                color = YH.ink,
                textAlign = androidx.compose.ui.text.style.TextAlign.Center,
                modifier = Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(8.dp))
                    .background(if (on) YH.canvas else Color.Transparent)
                    .clickable { Haptics.selection(); onSelect(opt) }
                    .padding(vertical = 7.dp),
            )
        }
    }
}

/** A borderless text field for use inside a form section. */
@Composable
fun YHFormTextField(value: String, onValueChange: (String) -> Unit, placeholder: String, singleLine: Boolean = true, minLines: Int = 1,
                    keyboardType: androidx.compose.ui.text.input.KeyboardType = androidx.compose.ui.text.input.KeyboardType.Text,
                    capitalization: androidx.compose.ui.text.input.KeyboardCapitalization = androidx.compose.ui.text.input.KeyboardCapitalization.Sentences) {
    androidx.compose.foundation.text.BasicTextField(
        value = value,
        onValueChange = onValueChange,
        singleLine = singleLine,
        minLines = minLines,
        textStyle = YHType.body.copy(color = YH.ink),
        cursorBrush = androidx.compose.ui.graphics.SolidColor(YH.ink),
        keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(capitalization = capitalization, keyboardType = keyboardType),
        modifier = Modifier.fillMaxWidth().padding(horizontal = YH.Space.md, vertical = 14.dp),
        decorationBox = { inner ->
            Box {
                if (value.isEmpty()) Text(placeholder, style = YHType.body, color = YH.muted.copy(alpha = 0.7f))
                inner()
            }
        },
    )
}
