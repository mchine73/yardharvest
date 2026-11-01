package app.yardharvest.manager.ui.admintools

import android.Manifest
import android.content.ClipData
import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Paint
import android.graphics.Typeface
import android.os.Build
import android.text.TextPaint
import android.text.TextUtils
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.AddCircle
import androidx.compose.material.icons.rounded.BluetoothDisabled
import androidx.compose.material.icons.rounded.ContentCopy
import androidx.compose.material.icons.rounded.Handyman
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Print
import androidx.compose.material.icons.rounded.QrCode2
import androidx.compose.material.icons.rounded.Quiz
import androidx.compose.material.icons.rounded.Sync
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
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
import androidx.compose.ui.graphics.FilterQuality
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.graphics.createBitmap
import app.yardharvest.manager.api.createResource
import app.yardharvest.manager.api.listResources
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.PhomemoModel
import app.yardharvest.manager.core.PhomemoPrinterManager
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenResource
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDivider
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHIconTile
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPickerRow
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSegmented
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSwitch
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.tools.ResourceStatusPill
import app.yardharvest.manager.ui.tools.resourceIcon
import com.google.zxing.BarcodeFormat
import com.google.zxing.EncodeHintType
import com.google.zxing.qrcode.QRCodeWriter
import com.google.zxing.qrcode.decoder.ErrorCorrectionLevel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Manager tool inventory: add tools, and print a QR label for any of them. */
@Composable
fun AdminToolsScreen(garden: Garden) {
    var resources by remember { mutableStateOf<List<GardenResource>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var showAdd by remember { mutableStateOf(false) }
    var labelTarget by remember { mutableStateOf<GardenResource?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { resources = ApiClient.listResources(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    YHScreen("Manage Tools", actions = { YHBarIcon(Icons.Rounded.AddCircle, "Add tool", tint = YH.ink) { showAdd = true } }) {
        YHLoadable(loading, resources.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 4,
            empty = { YHEmpty(Icons.Rounded.Handyman, "No tools yet", "Add a tool to start tracking checkouts and printing QR labels.", actionTitle = "Add a tool") { showAdd = true } }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item {
                        YHBand {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                YHIconTile(Icons.Rounded.QrCode2, size = 48.dp, background = YH.ink, foreground = YH.lime)
                                Column {
                                    Text("${resources.size} tool${if (resources.size == 1) "" else "s"}", style = YHType.title3, color = YH.ink)
                                    Text("Tap any tool to print a QR label. Gardeners scan it to check out.", style = YHType.caption, color = YH.ink.copy(alpha = 0.75f))
                                }
                            }
                        }
                    }
                    items(resources, key = { it.id }) { r ->
                        YHCard(onClick = { labelTarget = r }) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                YHIconTile(resourceIcon(r.resourceType), size = 44.dp)
                                Column(Modifier.weight(1f)) {
                                    Text(r.name, style = YHType.bodyMedium, color = YH.ink)
                                    val meta = listOfNotNull(r.resourceType?.replaceFirstChar(Char::uppercase), r.checkedOutToName?.let { "out to $it" })
                                    if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = YHType.caption, color = YH.muted)
                                }
                                if (r.status in setOf("available", "checked_out", "overdue", "out_of_service")) ResourceStatusPill(r.status)
                                Icon(Icons.Rounded.QrCode2, null, tint = YH.ink, modifier = Modifier.padding(start = 4.dp))
                            }
                        }
                    }
                }
            }
        }
    }
    if (showAdd) AddToolSheet(garden, onDismiss = { showAdd = false }) { created ->
        resources = listOf(created) + resources
        // Open the label sheet for the new tool so it prints without an extra tap.
        labelTarget = created
    }
    labelTarget?.let { r -> ToolQrLabelSheet(garden, r) { labelTarget = null } }
}

private val kinds = listOf("tool", "equipment", "supply", "seed")
private val conditions = listOf("new" to "New", "good" to "Good", "fair" to "Fair", "needs_repair" to "Needs repair")

@Composable
private fun AddToolSheet(garden: Garden, onDismiss: () -> Unit, onCreate: (GardenResource) -> Unit) {
    var name by remember { mutableStateOf("") }
    var kind by remember { mutableStateOf("tool") }
    var description by remember { mutableStateOf("") }
    var quantity by remember { mutableStateOf("1") }
    var condition by remember { mutableStateOf("good") }
    var saving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val canSave = name.isNotBlank() && !saving

    YHSheet(onDismiss, title = "New Tool", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                YHSectionLabel("Name", Modifier.padding(start = 0.dp, bottom = 8.dp))
                YHTextField(name, { name = it }, placeholder = "e.g. Cordless drill", capitalization = KeyboardCapitalization.Words, textStyle = YHType.body.copy(color = YH.ink))
            }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Type", Modifier.padding(start = 0.dp))
                    YHSegmented(kinds, kind, { it.replaceFirstChar(Char::uppercase) }) { kind = it }
                    YHSectionLabel("Condition", Modifier.padding(start = 0.dp))
                    Box(Modifier.clip(RoundedCornerShape(YH.Radius.md)).border(1.dp, YH.border, RoundedCornerShape(YH.Radius.md))) {
                        YHPickerRow("Condition", conditions, conditions.first { it.first == condition }, { it.second }) { condition = it.first }
                    }
                    YHSectionLabel("Quantity", Modifier.padding(start = 0.dp))
                    YHTextField(quantity, { quantity = it.filter(Char::isDigit) }, placeholder = "1", keyboardType = KeyboardType.Number, textStyle = YHType.body.copy(color = YH.ink))
                }
            }
            YHCard {
                YHSectionLabel("Description (optional)", Modifier.padding(start = 0.dp, bottom = 8.dp))
                YHTextField(description, { description = it }, placeholder = "Brief notes that show up on the tool's detail page", singleLine = false,
                    textStyle = YHType.body.copy(color = YH.ink), autoCorrect = true)
            }
            error?.let { YHInlineError(it) }
            YHButton("Add Tool & Print QR", icon = Icons.Rounded.AddCircle, style = YHButtonStyle.Lime, isLoading = saving, enabled = canSave) {
                scope.launch {
                    saving = true
                    error = null
                    try {
                        val created = ApiClient.createResource(garden.id, name.trim(), kind, description.trim(), maxOf(1, quantity.toIntOrNull() ?: 1), condition)
                        Haptics.success()
                        onCreate(created)
                        onDismiss()
                    } catch (e: Exception) {
                        error = e.userMessage
                        Haptics.error()
                    } finally {
                        saving = false
                    }
                }
            }
        }
    }
}

// ---- Bluetooth permission helper ---------------------------------------------------------

private val bluetoothPermissions: Array<String>
    get() = if (Build.VERSION.SDK_INT >= 31) arrayOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
    else arrayOf(Manifest.permission.ACCESS_FINE_LOCATION)

/** Run an action once the Bluetooth runtime permissions are granted, asking first if needed. */
@Composable
private fun rememberWithBluetooth(printer: PhomemoPrinterManager, onDenied: () -> Unit): (() -> Unit) -> Unit {
    var pending by remember { mutableStateOf<(() -> Unit)?>(null) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        val action = pending
        pending = null
        if (grants.values.all { it }) action?.invoke() else onDenied()
    }
    return { action -> if (printer.hasPermissions()) action() else { pending = action; launcher.launch(bluetoothPermissions) } }
}

// ---- Label sheet -------------------------------------------------------------------------

/**
 * A printable QR label for one tool, and the native print flow. The QR
 * encodes the tool's scannable URL, so any QR-aware app lands in checkout.
 */
@Composable
private fun ToolQrLabelSheet(garden: Garden, resource: GardenResource, onDismiss: () -> Unit) {
    val context = LocalContext.current
    val printer = remember { PhomemoPrinterManager(context) }
    var showPicker by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf<String?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    var printing by remember { mutableStateOf(false) }
    var label by remember { mutableStateOf<Bitmap?>(null) }
    val scope = rememberCoroutineScope()
    val payload = (resource.qrCodeUrl ?: resource.qrCodeToken ?: "").trim()
    // A backend without qr_code_url/token would print a QR that decodes to "".
    val hasPayload = payload.isNotEmpty()
    val withBluetooth = rememberWithBluetooth(printer) { error = "YardHarvest needs Nearby devices permission to find your printer." }
    DisposableEffect(Unit) { onDispose { printer.disconnect() } }

    // Compose at the model's head width and label height (M110: 320 × 240).
    LaunchedEffect(printer.model) {
        label = withContext(Dispatchers.Default) {
            ToolLabelComposer.compose(resource.name, garden.name, payload, printer.model.defaultPrintWidth, printer.model.defaultLabelHeight)
        }
    }

    suspend fun ensureConnectedAndPrint() {
        if (printer.state !is PhomemoPrinterManager.State.Ready) {
            try { printer.reconnectSaved() } catch (e: Exception) { error = e.userMessage; showPicker = true; return }
        }
        val img = label ?: run { error = "Label hasn't rendered yet — try again."; return }
        printing = true
        try {
            printer.printImage(img)
            status = "Sent as ${printer.model.detailedLabel}."
            Haptics.success()
        } catch (e: Exception) {
            error = e.userMessage
            Haptics.error()
        } finally {
            printing = false
        }
    }

    YHSheet(onDismiss, title = "Print Label", leading = { YHBarButton("Close", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    val img = label
                    if (img != null) {
                        Image(img.asImageBitmap(), "Label preview", contentScale = ContentScale.Fit, filterQuality = FilterQuality.None,
                            modifier = Modifier.widthIn(max = 240.dp).clip(RoundedCornerShape(8.dp)).background(Color.White)
                                .border(1.dp, YH.border, RoundedCornerShape(8.dp)).padding(8.dp))
                    } else {
                        Box(Modifier.height(240.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = YH.ink) }
                    }
                    Text("Preview", style = YHType.caption, color = YH.muted)
                }
            }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    YHSectionLabel("Tool", Modifier.padding(start = 0.dp))
                    Text(resource.name, style = YHType.title3, color = YH.ink)
                    resource.resourceType?.let { Text(it.replaceFirstChar(Char::uppercase), style = YHType.caption, color = YH.muted) }
                    YHDivider()
                    YHSectionLabel("Encodes", Modifier.padding(start = 0.dp))
                    Text(payload.ifEmpty { "—" }, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = YH.muted, maxLines = 2, overflow = TextOverflow.Ellipsis)
                }
            }
            PrinterStatusCard(printer.state)
            if (!hasPayload) {
                YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Icon(Icons.Rounded.WarningAmber, null, tint = YH.danger)
                        Text("Can't print yet", style = YHType.bodyMedium, color = YH.danger)
                    }
                    Text("This tool has no QR token from the backend. Redeploy the YardHarvest backend so the resource API returns qr_code_url + qr_code_token, then come back here.",
                        style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 4.dp))
                }
            }
            YHButton(
                if (printer.savedPrinterId == null) "Pair Printer & Print" else if (printer.state == PhomemoPrinterManager.State.Printing) "Printing…" else "Print Label",
                icon = Icons.Rounded.Print, style = YHButtonStyle.Lime, isLoading = printing, enabled = label != null && !printing && hasPayload,
            ) {
                error = null
                status = null
                withBluetooth {
                    if (printer.savedPrinterId == null) showPicker = true else scope.launch { ensureConnectedAndPrint() }
                }
            }
            YHButton("Pair a different printer", icon = Icons.Rounded.Sync, style = YHButtonStyle.Ghost) {
                printer.disconnect()
                withBluetooth { showPicker = true }
            }
            error?.let { YHInlineError(it) }
            status?.let { Text(it, style = YHType.subheadline, color = YH.ink) }
            YHCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Rounded.Info, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                    Text("How it works", style = YHType.captionMed, color = YH.muted)
                }
                Text(
                    "YardHarvest talks to your Phomemo printer directly over Bluetooth — no third-party app required. The QR encodes a yardharvest.app link that scans into the checkout flow on any device. Pair the printer once; we'll remember it for future labels.",
                    style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
    if (showPicker) PrinterPickerSheet(printer, onDismiss = { showPicker = false }) { scope.launch { ensureConnectedAndPrint() } }
}

@Composable
private fun PrinterStatusCard(state: PhomemoPrinterManager.State) {
    when (state) {
        is PhomemoPrinterManager.State.Ready -> YHCard {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                YHIconTile(Icons.Rounded.Print, background = YH.lime)
                Column {
                    Text("Connected", style = YHType.bodyMedium, color = YH.ink)
                    Text(state.name, style = YHType.caption, color = YH.muted)
                }
            }
        }
        PhomemoPrinterManager.State.Printing -> YHBand {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                Text("Printing…", style = YHType.bodyMedium, color = YH.ink)
            }
        }
        is PhomemoPrinterManager.State.Connecting -> YHCard {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                Text("Connecting to ${state.name}…", style = YHType.subheadline, color = YH.muted)
            }
        }
        is PhomemoPrinterManager.State.Failed -> YHCard { YHInlineError(state.message) }
        PhomemoPrinterManager.State.PoweredOff -> YHCard {
            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Icon(Icons.Rounded.BluetoothDisabled, null, tint = YH.warning)
                Text("Turn on Bluetooth to print.", style = YHType.subheadline, color = YH.warning)
            }
        }
        PhomemoPrinterManager.State.Unauthorized -> YHCard {
            Text("Allow Nearby devices for YardHarvest in Settings to print.", style = YHType.subheadline, color = YH.warning)
        }
        else -> {}
    }
}

// ---- Printer picker ----------------------------------------------------------------------

/**
 * One-time pairing: scan, pick, then a test print and a protocol sweep to
 * prove the bytes actually fire the print head. The chosen printer is
 * remembered so later prints reconnect silently.
 */
@Composable
private fun PrinterPickerSheet(printer: PhomemoPrinterManager, onDismiss: () -> Unit, onPaired: () -> Unit) {
    val clipboard = LocalClipboard.current
    var connectingId by remember { mutableStateOf<String?>(null) }
    var testStatus by remember { mutableStateOf<String?>(null) }
    var testError by remember { mutableStateOf<String?>(null) }
    var testPrinting by remember { mutableStateOf(false) }
    var sweeping by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val isConnected = printer.state is PhomemoPrinterManager.State.Ready
    val isScanning = printer.state == PhomemoPrinterManager.State.Scanning

    fun scan() { runCatching { printer.startScan() } }
    LaunchedEffect(Unit) { scan() }
    DisposableEffect(Unit) { onDispose { printer.stopScan() } }

    YHSheet(
        onDismiss, title = "Pair Printer",
        leading = { YHBarButton("Close", bold = false, color = YH.muted, onClick = onDismiss) },
        trailing = { if (isConnected) YHBarButton("Done", onClick = onDismiss) else YHBarButton("Scan", enabled = !isScanning) { scan() } },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHBand {
                Text("PHOMEMO", style = YHType.captionMed, letterSpacing = 0.8.sp, color = YH.ink)
                Text("Pair your label printer.", fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, color = YH.ink, modifier = Modifier.padding(top = 6.dp))
                Text("Power on the printer, hold it within a few feet of this phone, and pick it from the list below. We'll remember it for next time.",
                    style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f), modifier = Modifier.padding(top = 2.dp))
            }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Printer model", Modifier.padding(start = 0.dp))
                    YHSegmented(PhomemoModel.entries, printer.model, { it.label }) { printer.model = it }
                    Text(modelHelp(printer.model), style = YHType.caption, color = YH.muted)
                    YHDivider()
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Column(Modifier.weight(1f)) {
                            Text("Show all Bluetooth devices", style = YHType.bodyMedium, color = YH.ink)
                            Text(if (printer.showAllDevices) "Showing every nearby BLE device. Phomemo-recognized ones are tagged."
                                else "Only printers we recognize. Flip on if yours isn't appearing.", style = YHType.caption, color = YH.muted)
                        }
                        YHSwitch(printer.showAllDevices, { printer.setShowAll(it) })
                    }
                }
            }
            if (printer.discovered.isEmpty()) {
                YHCard {
                    if (isScanning) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                            CircularProgressIndicator(Modifier.size(18.dp), color = YH.ink, strokeWidth = 2.dp)
                            Text("Scanning for nearby printers…", style = YHType.subheadline, color = YH.muted)
                        }
                    } else {
                        Text("No printers yet", style = YHType.bodyMedium, color = YH.ink)
                        Text("Tap Scan in the top-right to look again. Phomemo printers usually advertise as M02, M02 PRO, T02, or similar.",
                            style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 4.dp))
                    }
                }
            }
            printer.discovered.forEach { p ->
                YHCard(onClick = if (connectingId == null) ({
                    scope.launch {
                        connectingId = p.id
                        try {
                            printer.connect(p)
                            Haptics.success()
                            onPaired()
                            // No auto-dismiss: the test card appears so the protocol
                            // can be verified before moving on.
                        } catch (_: Exception) {
                            Haptics.error()
                        } finally {
                            connectingId = null
                        }
                    }
                }) else null) {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        YHIconTile(Icons.Rounded.Print, size = 40.dp, background = if (p.isLikelyPhomemo) YH.lime else YH.surface)
                        Column(Modifier.weight(1f)) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                Text(p.name.ifEmpty { "Bluetooth printer" }, style = YHType.bodyMedium, color = YH.ink)
                                if (p.isLikelyPhomemo) Text("Phomemo", fontSize = 10.sp, fontWeight = FontWeight.Bold, color = YH.ink,
                                    modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 6.dp, vertical = 2.dp))
                            }
                            Text(p.id.lowercase(), fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = YH.muted)
                        }
                        if (connectingId == p.id) CircularProgressIndicator(Modifier.size(20.dp), color = YH.ink, strokeWidth = 2.dp)
                        else Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
                    }
                }
            }
            if (isScanning && printer.discovered.isNotEmpty()) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    CircularProgressIndicator(Modifier.size(14.dp), color = YH.muted, strokeWidth = 2.dp)
                    Text("Still scanning…", style = YHType.caption, color = YH.muted)
                }
            }
            if (isConnected) {
                YHCard {
                    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                            Icon(Icons.Rounded.Verified, null, tint = YH.ink)
                            Text("Test print", style = YHType.bodyMedium, color = YH.ink)
                        }
                        if (printer.model == PhomemoModel.M110) {
                            // The commonest cause of "connects but doesn't print".
                            Column(Modifier.clip(RoundedCornerShape(8.dp)).background(YH.warning.copy(alpha = 0.08f)).padding(8.dp),
                                verticalArrangement = Arrangement.spacedBy(4.dp)) {
                                Text("Calibrate the label gap first", style = YHType.captionMed, color = YH.warning)
                                Text("If you haven't already: power-cycle the M110 while HOLDING the feed button until it beeps and feeds 2–3 labels. That teaches it where the gaps are. Without this it accepts data over Bluetooth but never fires.",
                                    style = YHType.caption, color = YH.muted)
                            }
                        }
                        Text("Prints a small black bar to verify the connection drives the heating elements. If nothing comes out, see Diagnostics below — that'll tell us where it's failing.",
                            style = YHType.caption, color = YH.muted)
                        YHButton("Print test page", icon = Icons.Rounded.Print, isLoading = testPrinting) {
                            scope.launch {
                                testStatus = null; testError = null; testPrinting = true
                                try { printer.printTestPage(); testStatus = "Test page sent. Did a black bar come out?"; Haptics.success() }
                                catch (e: Exception) { testError = e.userMessage; Haptics.error() }
                                finally { testPrinting = false }
                            }
                        }
                        // For a silent printer: try every dialect and let the paper answer.
                        YHButton("Try every protocol", icon = Icons.Rounded.Quiz, style = YHButtonStyle.Ghost, isLoading = sweeping) {
                            scope.launch {
                                testStatus = null; testError = null; sweeping = true
                                try {
                                    printer.runProtocolSweep()
                                    testStatus = "Sweep done — 4 jobs sent, ~3s apart: 1 TSPL text, 2 short band, 3 TALL band, 4 medium band. Whichever printed, pick that model above: text→JADENS, short→M02, tall→M110, medium→Generic."
                                    Haptics.success()
                                } catch (e: Exception) { testError = e.userMessage; Haptics.error() }
                                finally { sweeping = false }
                            }
                        }
                        testStatus?.let { Text(it, style = YHType.caption, color = YH.ink) }
                        testError?.let { Text(it, style = YHType.caption, color = YH.danger) }
                        Diagnostics(printer) {
                            scope.launch {
                                clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("YardHarvest printer diagnostics", printer.diagnosticsExport())))
                                Haptics.tap()
                            }
                        }
                    }
                }
            }
            when (val s = printer.state) {
                is PhomemoPrinterManager.State.Failed -> YHCard { Text(s.message, style = YHType.subheadline, color = YH.danger) }
                PhomemoPrinterManager.State.PoweredOff -> YHCard { Text("Bluetooth is off. Turn it on from Quick Settings to find your printer.", style = YHType.subheadline, color = YH.warning) }
                PhomemoPrinterManager.State.Unauthorized -> YHCard { Text("YardHarvest needs Nearby devices permission. Allow it in Settings → Apps → YardHarvest → Permissions.", style = YHType.subheadline, color = YH.warning) }
                else -> {}
            }
        }
    }
}

private fun modelHelp(m: PhomemoModel) = when (m) {
    PhomemoModel.M110 -> "Phomemo M110 — 40 mm labels with a peeler. Needs label-gap calibration before first print (see below)."
    PhomemoModel.M02 -> "Phomemo M02 — 80 mm thermal receipt printer."
    PhomemoModel.Generic -> "Any cheap 58 mm BLE thermal receipt printer that speaks ESC/POS — Munbyn, NETUM, GOOJPRT, Rongta, MTP/MPT receipt models, etc. Continuous paper; no label-gap calibration needed."
    PhomemoModel.Jadens -> "JADENS BT-series sticker printer (BT203 / BT460 / BT420), TSPL protocol. Heads-up: boards advertising as “jd-2x…_BLE” only accept the JADENS app's proprietary protocol and can't be driven by third-party apps — if “Try every protocol” prints nothing, that's your board; use a Phomemo M110/D110 instead."
}

/** What the BLE handshake produced — "paste me the diagnostics" in one tap. */
@Composable
private fun Diagnostics(printer: PhomemoPrinterManager, onCopy: () -> Unit) {
    val d = printer.diagnostics
    Column(verticalArrangement = Arrangement.spacedBy(4.dp), modifier = Modifier.padding(top = 4.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            YHSectionLabel("Diagnostics", Modifier.weight(1f).padding(start = 0.dp))
            Row(Modifier.clip(RoundedCornerShape(6.dp)).clickable(onClick = onCopy).padding(4.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                Icon(Icons.Rounded.ContentCopy, null, tint = YH.ink, modifier = Modifier.size(14.dp))
                Text("Copy", style = YHType.caption, color = YH.ink)
            }
        }
        DiagRow("Service", d.serviceUuid ?: "—")
        DiagRow("Write char", d.writeCharUuid ?: "—")
        DiagRow("Write modes", listOfNotNull("with-response".takeIf { d.supportsWrite }, "without-response".takeIf { d.supportsWriteWithoutResponse }).joinToString(" + "))
        DiagRow("Notify char", d.notifyCharUuid ?: "(none)")
        DiagRow("Notify subscribed", if (d.notificationsSubscribed) "yes" else "no")
        if (d.bytesTotal > 0) DiagRow("Bytes sent", "${d.bytesSent} / ${d.bytesTotal}")
        d.lastNotification?.let { DiagRow("Last reply", it) }
        if (d.log.isNotEmpty()) {
            YHSectionLabel("Log", Modifier.padding(start = 0.dp, top = 4.dp))
            d.log.forEach { Text("• $it", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = YH.muted) }
        }
    }
}

@Composable
private fun DiagRow(label: String, value: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(label, style = YHType.caption, color = YH.muted, modifier = Modifier.widthIn(min = 110.dp, max = 110.dp))
        Text(value, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = YH.ink, maxLines = 2, overflow = TextOverflow.Ellipsis)
    }
}

// ---- Label compositor ---------------------------------------------------------------------

/**
 * A print-ready label: the tool name, a high-density QR, and the garden name
 * under it. Short labels (M110 40 × 30 mm) get a compact stack; taller ones
 * add a "Scan to check out" hint. Same layout as the iOS compositor.
 */
object ToolLabelComposer {
    fun compose(toolName: String, gardenName: String, qrPayload: String, width: Int, height: Int): Bitmap? {
        if (qrPayload.isEmpty()) return null
        val isShort = height < width * 0.85
        val titleHeight = if (isShort) 26f else 36f
        val footerHeight = if (isShort) 20f else 24f
        val hintHeight = if (isShort) 0f else 20f
        val topPadding = 6f
        val bottomPadding = if (isShort) 4f else 8f
        val gap = 4f
        val consumed = topPadding + titleHeight + gap + footerHeight + (if (hintHeight > 0) gap + hintHeight else 0f) + bottomPadding
        val available = maxOf(40f, height - consumed)
        val qrSide = minOf(width * 0.92f, available).toInt()

        val bmp = createBitmap(width, height)
        val canvas = Canvas(bmp)
        canvas.drawColor(android.graphics.Color.WHITE)

        fun text(s: String, sizePx: Float, bold: Boolean, y: Float, boxHeight: Float, color: Int = android.graphics.Color.BLACK) {
            val paint = TextPaint(Paint.ANTI_ALIAS_FLAG).apply {
                textSize = sizePx
                this.color = color
                typeface = Typeface.create(Typeface.DEFAULT, if (bold) Typeface.BOLD else Typeface.NORMAL)
                textAlign = Paint.Align.CENTER
            }
            val fitted = TextUtils.ellipsize(s, paint, width - 12f, TextUtils.TruncateAt.END).toString()
            val baseline = y + (boxHeight - (paint.descent() + paint.ascent())) / 2
            canvas.drawText(fitted, width / 2f, baseline, paint)
        }

        text(toolName, if (isShort) 20f else 28f, bold = true, y = topPadding, boxHeight = titleHeight)

        // Error correction H, so labels survive being scuffed or curled; a
        // one-module quiet zone keeps the code as large as the label allows.
        val matrix = QRCodeWriter().encode(qrPayload, BarcodeFormat.QR_CODE, qrSide, qrSide,
            mapOf(EncodeHintType.ERROR_CORRECTION to ErrorCorrectionLevel.H, EncodeHintType.MARGIN to 1))
        val qrLeft = (width - qrSide) / 2
        val qrTop = (topPadding + titleHeight + gap).toInt()
        val black = Paint().apply { color = android.graphics.Color.BLACK }
        for (y in 0 until matrix.height) for (x in 0 until matrix.width) {
            if (matrix[x, y]) canvas.drawRect((qrLeft + x).toFloat(), (qrTop + y).toFloat(), (qrLeft + x + 1).toFloat(), (qrTop + y + 1).toFloat(), black)
        }

        val footerY = qrTop + qrSide + gap
        text(gardenName, if (isShort) 14f else 18f, bold = false, y = footerY, boxHeight = footerHeight)
        if (hintHeight > 0) text("Scan to check out", 13f, bold = false, y = footerY + footerHeight + 2, boxHeight = hintHeight, color = android.graphics.Color.DKGRAY)
        return bmp
    }
}
