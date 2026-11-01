package app.yardharvest.manager.ui.tools

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ExperimentalGetImage
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.ArrowCircleDown
import androidx.compose.material.icons.rounded.ArrowCircleUp
import androidx.compose.material.icons.rounded.Build
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Construction
import androidx.compose.material.icons.rounded.Eco
import androidx.compose.material.icons.rounded.Handyman
import androidx.compose.material.icons.rounded.Inventory2
import androidx.compose.material.icons.rounded.PersonOff
import androidx.compose.material.icons.rounded.PhotoCamera
import androidx.compose.material.icons.rounded.QrCodeScanner
import androidx.compose.material.icons.rounded.SwapVert
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.CompositingStrategy
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import app.yardharvest.manager.api.checkoutResource
import app.yardharvest.manager.api.listResources
import app.yardharvest.manager.api.resourceLookup
import app.yardharvest.manager.api.returnResource
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenResource
import app.yardharvest.manager.model.ResourceLookup
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHContentReveal
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHFilterChips
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHNoticeDialog
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSegmented
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonCard
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.GardenPickerSheet
import com.google.mlkit.vision.barcode.BarcodeScannerOptions
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import java.util.concurrent.Executors
import kotlinx.coroutines.launch

/** "Scan a tool" launcher shortcut → open the scanner on the Tools tab. */
object ScanRequests {
    var count by mutableIntStateOf(0)
        private set
    fun request() { count++ }
}

/** Tools tab: the inventory, with the QR scanner one tap away. */
@Composable
fun ToolsTab() {
    val store = LocalGardenStore.current
    var showPicker by remember { mutableStateOf(false) }
    var showScanner by remember { mutableStateOf(false) }
    var handledScans by remember { mutableIntStateOf(ScanRequests.count) }
    LaunchedEffect(ScanRequests.count) {
        if (ScanRequests.count != handledScans) { handledScans = ScanRequests.count; showScanner = true }
    }
    val garden = store.selectedGarden
    YHScreen(
        "Tools", showBack = false,
        leading = { YHBarIcon(Icons.Rounded.QrCodeScanner, "Scan a tool QR", tint = YH.ink) { showScanner = true } },
        actions = { YHBarIcon(Icons.Rounded.SwapVert, "Switch garden") { showPicker = true } },
    ) {
        when {
            garden != null -> ToolsList(garden)
            store.isLoading -> androidx.compose.foundation.layout.Box(Modifier.padding(16.dp)) { YHSkeletonCard() }
            else -> YHEmpty(Icons.Rounded.Handyman, "No garden selected", "Pick a garden to view its tools.")
        }
    }
    if (showPicker) GardenPickerSheet { showPicker = false }
    if (showScanner) ScannerScreen { showScanner = false }
}

private enum class ToolFilter(val label: String, val status: String?) {
    All("All", null), Available("Available", "available"), Out("Out", "checked_out"), Overdue("Overdue", "overdue"), Service("Service", "out_of_service"),
}

@Composable
private fun ToolsList(garden: Garden) {
    var resources by remember(garden.id) { mutableStateOf<List<GardenResource>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(ToolFilter.All) }
    var selected by remember { mutableStateOf<GardenResource?>(null) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { resources = ApiClient.listResources(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }
    val filtered = filter.status?.let { s -> resources.filter { it.status == s } } ?: resources

    YHLoadable(loading, resources.isEmpty(), error, { scope.launch { load() } },
        empty = { YHEmpty(Icons.Rounded.Handyman, "No tools yet", "Tools added on the web will appear here.") }) {
        YHContentReveal(Icons.Rounded.Handyman, id = "tools-${garden.id}", caption = "Your toolbox") {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item { YHFilterChips(filter, ToolFilter.entries, { it.label }) { filter = it } }
                    items(filtered, key = { it.id }) { r -> ToolRow(r) { selected = r } }
                }
            }
        }
    }
    // The row is a scan you didn't have to point a camera at.
    selected?.let { r ->
        ResourceActionSheet(ResourceLookup(garden.id, garden.name, r.id, r), organizerId = garden.organizerId) { changed ->
            selected = null
            if (changed) scope.launch { load(false) }
        }
    }
}

fun resourceIcon(type: String?): ImageVector = when ((type ?: "tool").lowercase()) {
    "tool" -> Icons.Rounded.Build
    "equipment" -> Icons.Rounded.Construction
    "supply" -> Icons.Rounded.Inventory2
    "seed" -> Icons.Rounded.Eco
    else -> Icons.Rounded.Handyman
}

@Composable
fun ResourceStatusPill(status: String) {
    when (status) {
        "available" -> YHPill("Available", tint = YH.ink, background = YH.lime)
        "checked_out" -> YHPill("Out", tint = YH.muted, background = YH.surface)
        "overdue" -> YHPill("Overdue", tint = Color.White, background = YH.danger)
        "out_of_service" -> YHPill("Service", tint = Color.White, background = YH.warning)
        else -> YHPill(status.replaceFirstChar(Char::uppercase), tint = YH.muted, background = YH.surface)
    }
}

@Composable
private fun ToolRow(r: GardenResource, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(44.dp).clip(RoundedCornerShape(10.dp)).background(YH.surface), contentAlignment = Alignment.Center) {
                Icon(resourceIcon(r.resourceType), null, tint = YH.ink)
            }
            Column(Modifier.weight(1f)) {
                Text(r.name, style = YHType.bodyMedium, color = YH.ink)
                val meta = listOfNotNull(r.resourceType?.replaceFirstChar(Char::uppercase), r.checkedOutToName)
                if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = YHType.caption, color = YH.muted)
            }
            ResourceStatusPill(r.status)
        }
    }
}

/**
 * Shown after scanning or tapping a tool: adapts to its state and offers the
 * right action. Returns are allowed for the borrower or the organizer only —
 * the same rule as the backend, so nobody taps Return and reads a 403.
 */
@Composable
fun ResourceActionSheet(lookup: ResourceLookup, organizerId: Int? = null, onDismiss: (Boolean) -> Unit) {
    var resource by remember { mutableStateOf(lookup.resource) }
    var duration by remember { mutableIntStateOf(3) }
    var condition by remember { mutableStateOf("good") }
    var working by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var changed by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val me = AuthManager.currentUser?.id
    val canReturn = me != null && (resource.checkedOutToId == me || organizerId == me)

    fun act(work: suspend () -> GardenResource) {
        scope.launch {
            working = true
            error = null
            try {
                resource = work()
                changed = true
                Haptics.success()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                working = false
            }
        }
    }

    YHSheet({ if (!working) onDismiss(changed) }, title = resource.name,
        leading = { YHBarButton("Close", bold = false, color = YH.muted, enabled = !working) { onDismiss(changed) } }) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    YHSectionLabel(lookup.gardenName, Modifier.padding(start = 0.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(resource.name, style = YHType.title2, color = YH.ink, modifier = Modifier.weight(1f))
                        ResourceStatusPill(resource.status)
                    }
                    resource.resourceType?.let { Text(it.replaceFirstChar(Char::uppercase), style = YHType.subheadline, color = YH.muted) }
                    resource.condition?.let {
                        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                            Icon(Icons.Rounded.Verified, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                            Text("Condition: ${it.replace('_', ' ').replaceFirstChar(Char::uppercase)}", style = YHType.caption, color = YH.muted)
                        }
                    }
                }
            }
            when {
                resource.outOfService -> YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        Icon(Icons.Rounded.Build, null, tint = YH.warning)
                        Text("Out of service", style = YHType.headline, color = YH.warning)
                    }
                    Text(resource.serviceNote?.takeIf { it.isNotEmpty() } ?: "This tool isn't available right now.",
                        style = YHType.subheadline, color = YH.muted, modifier = Modifier.padding(top = 6.dp))
                }
                resource.isAvailable -> YHCard {
                    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        Text("Check Out", style = YHType.headline, color = YH.ink)
                        YHSegmented(listOf(1, 3, 7), duration, { if (it == 1) "1 day" else "$it days" }) { duration = it }
                        YHButton("Check Out", icon = Icons.Rounded.ArrowCircleDown, style = YHButtonStyle.Lime, isLoading = working) {
                            act { ApiClient.checkoutResource(lookup.gardenId, resource.id, duration) }
                        }
                    }
                }
                resource.isCheckedOut -> YHCard {
                    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        resource.dueDate?.let { due ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Text("Due ${Fmt.dateTime(due)}", style = YHType.subheadline, color = YH.muted, modifier = Modifier.weight(1f))
                                if (resource.isOverdue) YHPill("Overdue", tint = Color.White, background = YH.danger)
                            }
                        }
                        if (canReturn) {
                            Text("Condition on return", style = YHType.captionMed, color = YH.muted)
                            YHSegmented(listOf("good", "fair", "needs_repair"), condition,
                                { when (it) { "good" -> "Good"; "fair" -> "Fair"; else -> "Needs repair" } }) { condition = it }
                            YHButton("Return", icon = Icons.Rounded.ArrowCircleUp, isLoading = working) {
                                act { ApiClient.returnResource(lookup.gardenId, resource.id, condition) }
                            }
                        } else {
                            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Icon(Icons.Rounded.PersonOff, null, tint = YH.muted)
                                Text("Checked out to ${resource.checkedOutToName ?: "another member"} — only they or the garden organizer can return it.",
                                    style = YHType.subheadline, color = YH.muted)
                            }
                        }
                    }
                }
            }
            error?.let { YHInlineError(it) }
        }
    }
}

// ---- Scanner ------------------------------------------------------------------------

/** Full-screen scanner with a viewfinder and a Done button. */
@Composable
fun ScannerScreen(onDismiss: () -> Unit) {
    val context = LocalContext.current
    var hasCamera by remember {
        mutableStateOf(ContextCompat.checkSelfPermission(context, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED)
    }
    var denied by remember { mutableStateOf(false) }
    var scanned by remember { mutableStateOf<String?>(null) }
    var lookup by remember { mutableStateOf<ResourceLookup?>(null) }
    var resolving by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { granted ->
        hasCamera = granted
        denied = !granted
    }
    LaunchedEffect(Unit) { if (!hasCamera) permission.launch(Manifest.permission.CAMERA) }

    fun resolve(token: String) {
        scope.launch {
            resolving = true
            try { lookup = ApiClient.resourceLookup(token) } catch (e: Exception) { error = e.userMessage } finally { resolving = false }
        }
    }

    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false, decorFitsSystemWindows = false)) {
        Box(Modifier.fillMaxSize().background(Color.Black)) {
            when {
                denied -> YHEmpty(Icons.Rounded.PhotoCamera, "Camera access needed",
                    "Allow camera access for YardHarvest in Settings to scan tool QR codes.", modifier = Modifier.background(YH.canvas))
                hasCamera -> {
                    QrCameraView(active = scanned == null, onCode = { code ->
                        if (scanned != null) return@QrCameraView
                        // A degenerate label decodes to blank: say so rather than
                        // sending an empty token to the lookup endpoint.
                        if (code.isBlank()) {
                            scanned = code
                            error = "This QR code is blank. Reprint the label so the tool has a fresh token."
                        } else {
                            scanned = code
                            Haptics.success()
                            resolve(code.trim())
                        }
                    })
                    Viewfinder()
                }
            }
            if (resolving) {
                Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = 0.5f)), contentAlignment = Alignment.Center) {
                    Column(Modifier.clip(RoundedCornerShape(14.dp)).background(YH.canvas).padding(20.dp),
                        horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        CircularProgressIndicator(Modifier.size(24.dp), color = YH.ink, strokeWidth = 2.dp)
                        Text("Resolving…", style = YHType.bodyMedium, color = YH.ink)
                    }
                }
            }
            Row(
                Modifier.windowInsetsPadding(WindowInsets.statusBars).padding(16.dp).clip(RoundedCornerShape(50))
                    .background(Color.Black.copy(alpha = 0.45f)).clickable { Haptics.tap(); onDismiss() }.padding(horizontal = 14.dp, vertical = 8.dp),
                verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp),
            ) {
                Icon(Icons.Rounded.Close, null, tint = Color.White, modifier = Modifier.size(16.dp))
                Text("Done", color = Color.White, fontSize = 14.sp, fontWeight = FontWeight.SemiBold)
            }
        }
    }

    lookup?.let { l ->
        ResourceActionSheet(l) { changed ->
            lookup = null
            scanned = null
            if (changed) onDismiss()
        }
    }
    error?.let { YHNoticeDialog("Scan Error", it) { error = null; scanned = null } }
}

/** The dimmed surround with a lime-bordered cut-out, and the guidance pill. */
@Composable
private fun Viewfinder() {
    Box(Modifier.fillMaxSize()) {
        Canvas(Modifier.fillMaxSize().graphicsLayer { compositingStrategy = CompositingStrategy.Offscreen }) {
            val side = minOf(size.width, size.height) * 0.7f
            val topLeft = Offset((size.width - side) / 2, (size.height - side) / 2)
            drawRect(Color.Black.copy(alpha = 0.35f))
            drawRoundRect(Color.Transparent, topLeft, Size(side, side), CornerRadius(24.dp.toPx()), blendMode = BlendMode.Clear)
            drawRoundRect(YH.lime, topLeft, Size(side, side), CornerRadius(24.dp.toPx()), style = Stroke(3.dp.toPx()))
        }
        Text("Point at a tool's QR code", style = YHType.bodyMedium, color = YH.ink,
            modifier = Modifier.align(Alignment.BottomCenter).padding(bottom = 80.dp).clip(RoundedCornerShape(50))
                .background(YH.lime).padding(horizontal = 14.dp, vertical = 8.dp))
    }
}

/**
 * CameraX preview + ML Kit QR detection. Decodes are accepted only after a
 * 1.3 s settle, so the first, still-focusing frames can't lock onto a blurry
 * or stale read — the same guard as the iOS scanner.
 */
@androidx.annotation.OptIn(ExperimentalGetImage::class)
@Composable
private fun QrCameraView(active: Boolean, onCode: (String) -> Unit) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val previewView = remember { PreviewView(context).apply { scaleType = PreviewView.ScaleType.FILL_CENTER } }
    val analyzerExecutor = remember { Executors.newSingleThreadExecutor() }
    val scanner = remember {
        BarcodeScanning.getClient(BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build())
    }
    val currentActive by androidx.compose.runtime.rememberUpdatedState(active)
    val currentOnCode by androidx.compose.runtime.rememberUpdatedState(onCode)

    DisposableEffect(lifecycleOwner) {
        val acceptAfter = System.currentTimeMillis() + 1300
        val future = ProcessCameraProvider.getInstance(context)
        var provider: ProcessCameraProvider? = null
        future.addListener({
            val p = future.get()
            provider = p
            val preview = Preview.Builder().build().also { it.surfaceProvider = previewView.surfaceProvider }
            val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(analyzerExecutor) { proxy ->
                val media = proxy.image
                if (media == null || !currentActive || System.currentTimeMillis() < acceptAfter) {
                    proxy.close()
                    return@setAnalyzer
                }
                scanner.process(InputImage.fromMediaImage(media, proxy.imageInfo.rotationDegrees))
                    .addOnSuccessListener { codes ->
                        val value = codes.firstOrNull()?.rawValue
                        if (value != null && currentActive) currentOnCode(value)
                    }
                    .addOnCompleteListener { proxy.close() }
            }
            try {
                p.unbindAll()
                p.bindToLifecycle(lifecycleOwner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            } catch (_: Exception) {
            }
        }, ContextCompat.getMainExecutor(context))
        onDispose {
            provider?.unbindAll()
            analyzerExecutor.shutdown()
            scanner.close()
        }
    }
    AndroidView({ previewView }, Modifier.fillMaxSize())
}
