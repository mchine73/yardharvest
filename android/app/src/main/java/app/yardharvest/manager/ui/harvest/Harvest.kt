package app.yardharvest.manager.ui.harvest

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AddCircle
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.ShoppingBasket
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.listHarvests
import app.yardharvest.manager.api.logHarvest
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.HarvestDestination
import app.yardharvest.manager.model.HarvestLog
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDateRow
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPickerRow
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import java.time.LocalDate
import java.time.ZoneId
import kotlinx.coroutines.launch

/**
 * The garden's harvest log. [autoCompose] opens the quick-add sheet straight
 * away — the "Log harvest" launcher shortcut, Android's counterpart of the iOS
 * Siri/Shortcuts App Intent.
 */
@Composable
fun HarvestLogScreen(garden: Garden, autoCompose: Boolean = false) {
    var logs by remember { mutableStateOf<List<HarvestLog>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showAdd by rememberSaveable { mutableStateOf(autoCompose) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { logs = ApiClient.listHarvests(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    YHScreen("Harvest Log", actions = { YHBarIcon(Icons.Rounded.AddCircle, "Log harvest", tint = YH.ink) { showAdd = true } }) {
        YHLoadable(loading, logs.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 3,
            empty = { YHEmpty(Icons.Rounded.ShoppingBasket, "No harvests yet", "Log your first harvest to start tracking impact.", actionTitle = "Log Harvest") { showAdd = true } }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item {
                        YHBand {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                    Text("THIS SEASON", style = YHType.captionMed, letterSpacing = 0.8.sp, color = YH.ink)
                                    Text("${Fmt.pounds(logs.sumOf { it.quantityLbs })} lb", fontSize = 32.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.6).sp, color = YH.ink)
                                    Text("${logs.size} logged", style = YHType.caption, color = YH.ink.copy(alpha = 0.7f))
                                }
                                Icon(Icons.Rounded.ShoppingBasket, null, tint = YH.ink.copy(alpha = 0.18f), modifier = Modifier.size(52.dp))
                            }
                        }
                    }
                    items(logs, key = { it.id }) { log -> HarvestRow(log) }
                }
            }
        }
    }
    if (showAdd) HarvestQuickAddSheet(garden, onDismiss = { showAdd = false }) { logs = listOf(it) + logs }
}

@Composable
private fun HarvestRow(log: HarvestLog) {
    YHCard {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Column(Modifier.weight(1f)) {
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(log.category.replaceFirstChar(Char::uppercase), style = YHType.bodyMedium, color = YH.ink)
                    if (!log.variety.isNullOrEmpty()) Text("· ${log.variety}", style = YHType.subheadline, color = YH.muted)
                }
                val meta = listOfNotNull(log.userName, log.harvestDate?.let { Fmt.date(it) })
                if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = YHType.caption, color = YH.muted)
            }
            Text("${Fmt.pounds(log.quantityLbs)} lb", style = YHType.title3, color = YH.ink)
        }
    }
}

private val suggested = listOf("Tomatoes", "Greens", "Squash", "Cucumbers", "Beans", "Peppers", "Herbs", "Fruit")

@Composable
fun HarvestQuickAddSheet(garden: Garden, onDismiss: () -> Unit, onCreate: (HarvestLog) -> Unit) {
    var category by remember { mutableStateOf("") }
    var variety by remember { mutableStateOf("") }
    var quantity by remember { mutableStateOf("") }
    var date by remember { mutableStateOf(LocalDate.now()) }
    var destination by remember { mutableStateOf(HarvestDestination.Personal) }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val qty = quantity.replace(',', '.').toDoubleOrNull()
    val canSubmit = category.isNotEmpty() && (qty ?: 0.0) > 0

    YHSheet(onDismiss, title = "Log Harvest", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Crop", Modifier.padding(start = 0.dp))
                    YHTextField(category, { category = it }, placeholder = "Category (e.g. Tomatoes)",
                        capitalization = KeyboardCapitalization.Words, textStyle = YHType.body.copy(color = YH.ink))
                    if (category.isEmpty()) {
                        Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            suggested.forEach { name ->
                                Text(name, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, color = YH.ink,
                                    modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.surface)
                                        .clickable { Haptics.selection(); category = name }.padding(horizontal = 12.dp, vertical = 6.dp))
                            }
                        }
                    }
                    YHTextField(variety, { variety = it }, placeholder = "Variety (optional, e.g. Sungold)",
                        capitalization = KeyboardCapitalization.Words, textStyle = YHType.body.copy(color = YH.ink))
                }
            }
            YHCard(padding = 0.dp) {
                Column(Modifier.padding(start = YH.Space.md, end = YH.Space.md, top = YH.Space.md)) {
                    YHSectionLabel("Amount", Modifier.padding(start = 0.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        BasicTextField(
                            quantity, { quantity = it.filter { c -> c.isDigit() || c == '.' || c == ',' } },
                            singleLine = true,
                            textStyle = TextStyle(fontSize = 28.sp, fontWeight = FontWeight.Bold, color = YH.ink),
                            cursorBrush = SolidColor(YH.ink),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.weight(1f).padding(vertical = 8.dp),
                            decorationBox = { inner ->
                                if (quantity.isEmpty()) Text("0.0", fontSize = 28.sp, fontWeight = FontWeight.Bold, color = YH.muted.copy(alpha = 0.5f))
                                inner()
                            },
                        )
                        Text("lb", style = YHType.title3, color = YH.muted)
                    }
                }
                YHDateRow("Date", date) { date = it }
            }
            YHCard(padding = 0.dp) {
                Column(Modifier.padding(start = YH.Space.md, top = YH.Space.md)) { YHSectionLabel("Destination", Modifier.padding(start = 0.dp)) }
                YHPickerRow("Where it went", HarvestDestination.entries, destination, { it.label }) { destination = it }
            }
            error?.let { YHInlineError(it) }
            YHButton("Log Harvest", icon = Icons.Rounded.Check, style = YHButtonStyle.Lime, isLoading = working, enabled = canSubmit) {
                val pounds = qty ?: return@YHButton
                scope.launch {
                    working = true
                    error = null
                    try {
                        val created = ApiClient.logHarvest(
                            garden.id, category, variety, pounds,
                            date.atStartOfDay(ZoneId.systemDefault()).toInstant(), destination, null,
                        )
                        onCreate(created)
                        Haptics.success()
                        onDismiss()
                    } catch (e: Exception) {
                        error = e.userMessage
                        Haptics.error()
                    } finally {
                        working = false
                    }
                }
            }
        }
    }
}
