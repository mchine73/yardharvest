package app.yardharvest.manager.core

import android.Manifest
import android.annotation.SuppressLint
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothGatt
import android.bluetooth.BluetoothGattCallback
import android.bluetooth.BluetoothGattCharacteristic
import android.bluetooth.BluetoothGattDescriptor
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothProfile
import android.bluetooth.BluetoothStatusCodes
import android.bluetooth.le.ScanCallback
import android.bluetooth.le.ScanResult
import android.bluetooth.le.ScanSettings
import android.content.Context
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.os.Build
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.core.content.ContextCompat
import androidx.core.content.edit
import java.util.UUID
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.CancellableContinuation
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.TimeoutCancellationException
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withTimeout

/** Failures phrased for the person holding the printer. */
class PhomemoException(message: String) : Exception(message) {
    companion object {
        val bluetoothOff get() = PhomemoException("Bluetooth is off. Turn it on from Quick Settings, then try again.")
        val unauthorized get() = PhomemoException("YardHarvest doesn't have Bluetooth permission. Allow Nearby devices for YardHarvest in Settings.")
        val unsupported get() = PhomemoException("This phone doesn't support Bluetooth LE.")
        val busy get() = PhomemoException("A print job is already in progress — wait for it to finish.")
        val notFound get() = PhomemoException("Couldn't find that printer. Make sure it's powered on and in range.")
        val noSaved get() = PhomemoException("No printer paired yet.")
        val connectFailed get() = PhomemoException("Couldn't connect to the printer.")
        val noServices get() = PhomemoException("Connected, but the printer didn't expose any services. Power-cycle the printer and try again.")
        val noWritable get() = PhomemoException("Couldn't find a writable channel on this printer. It might be a model we don't speak yet — tell us the exact model and we'll add support.")
        val notConnected get() = PhomemoException("Not connected to a printer.")
    }
}

/** BLE UUIDs across the supported printer families, and the name heuristic. */
object PhomemoUuids {
    private fun short(s: String) = UUID.fromString("0000$s-0000-1000-8000-00805F9B34FB")

    val candidateServices: List<UUID> = listOf(
        short("FF00"),                                          // Phomemo M02/M110, most cheap BLE thermal printers
        short("18F0"),                                          // some Phomemo + generic ESC/POS variants
        UUID.fromString("E7810A71-73AE-499D-8C15-FAA9AEF0C3F2"), // older Phomemo PR02 firmware
        UUID.fromString("6E400001-B5A3-F393-E0A9-E50E24DCCA9E"), // Nordic UART
        UUID.fromString("49535343-FE7D-4AE5-8FA9-9FAFD205E455"), // Microchip RN4870 BLE-SPP bridge
    )
    val candidateWriteChars: List<UUID> = listOf(
        short("FF02"),
        short("2AF1"),
        UUID.fromString("BEF8910B-7BB9-4F8D-9D6E-7C8FE74E27AA"),
        UUID.fromString("6E400002-B5A3-F393-E0A9-E50E24DCCA9E"), // Nordic UART RX
        UUID.fromString("49535343-8841-43F4-A8D4-ECBE34729BB3"), // RN4870 transparent UART
    )
    val cccd: UUID = short("2902")

    fun looksLikePhomemo(name: String): Boolean {
        val upper = name.uppercase()
        if (upper.isEmpty()) return false
        val needles = listOf(
            "PHOMEMO", "M02", "M03", "M04", "M110", "M120", "M200", "M220",
            "T02", "PR02", "PR-", "P12", "D30", "D35", "Q20",
            "JADENS", "BT460", "BT420", "BT203", "BT201", "BT-", "JD-",
            "MUNBYN", "NETUM", "GOOJPRT", "RONGTA", "POS-MATE",
            "MPT-", "MTP-", "BIXOLON", "POS58", "POS80",
            "PRINTER", "PRT", "PT-",
        )
        return needles.any { upper.contains(it) }
    }

    fun shortName(uuid: UUID): String {
        val s = uuid.toString().uppercase()
        return if (s.startsWith("0000") && s.endsWith("-0000-1000-8000-00805F9B34FB")) s.substring(4, 8) else s
    }
}

/**
 * Native BLE driver for Phomemo-family thermal label printers — the Android
 * port of the iOS `PhomemoPrinterManager`. Same handshake: connect, discover
 * every service, rank the writable characteristics, subscribe to the notify
 * channel, then stream the model's command set in MTU-sized chunks.
 *
 * The caller holds the Bluetooth runtime permissions before scanning or
 * connecting; [hasPermissions] says whether it does.
 */
@SuppressLint("MissingPermission") // every entry point checks hasPermissions first
class PhomemoPrinterManager(context: Context) {

    sealed interface State {
        data object PoweredOff : State
        data object Unauthorized : State
        data object Idle : State
        data object Scanning : State
        data class Connecting(val name: String) : State
        data class Ready(val name: String) : State
        data object Printing : State
        data class Failed(val message: String) : State
    }

    data class DiscoveredPrinter(val id: String, val name: String, val isLikelyPhomemo: Boolean)

    data class Diagnostics(
        val serviceUuid: String? = null,
        val writeCharUuid: String? = null,
        val notifyCharUuid: String? = null,
        val supportsWrite: Boolean = false,
        val supportsWriteWithoutResponse: Boolean = false,
        val notificationsSubscribed: Boolean = false,
        val bytesSent: Int = 0,
        val bytesTotal: Int = 0,
        val lastNotification: String? = null,
        val log: List<String> = emptyList(),
    ) {
        fun append(line: String) = copy(log = (log + line).takeLast(12))
    }

    private val appContext = context.applicationContext
    private val manager = appContext.getSystemService(BluetoothManager::class.java)
    private val adapter get() = manager?.adapter
    private val prefs = AppEnvironment.prefs
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)

    var state: State by mutableStateOf(State.Idle)
        private set
    var discovered: List<DiscoveredPrinter> by mutableStateOf(emptyList())
        private set
    var diagnostics: Diagnostics by mutableStateOf(Diagnostics())
        private set

    /** When false, only printers matching the name/service heuristics are listed. */
    var showAllDevices: Boolean by mutableStateOf(false)
        private set

    fun setShowAll(on: Boolean) {
        showAllDevices = on
        rebuildDiscovered()
    }

    private var _model by mutableStateOf(
        PhomemoModel.entries.firstOrNull { it.name == prefs.getString(MODEL_KEY, null) } ?: PhomemoModel.M110,
    )
    /** Which family to target. Defaults to M110, the confirmed hardware for tool labels. */
    var model: PhomemoModel
        get() = _model
        set(value) {
            _model = value
            prefs.edit { putString(MODEL_KEY, value.name) }
        }

    /** MAC address of the most recently paired printer, so the next print reconnects silently. */
    var savedPrinterId: String?
        get() = prefs.getString(SAVED_KEY, null)
        private set(value) { prefs.edit { if (value == null) remove(SAVED_KEY) else putString(SAVED_KEY, value) } }

    // Every device seen is retained with its hints, keyed by address.
    private data class Record(val device: BluetoothDevice, val name: String, val isLikely: Boolean)
    private val retained = linkedMapOf<String, Record>()

    private var gatt: BluetoothGatt? = null
    private var writeChar: BluetoothGattCharacteristic? = null
    private var alternateWriteChars: List<BluetoothGattCharacteristic> = emptyList()
    private var mtu = 23

    // One continuation per GATT op; Android serializes GATT, so one at a time.
    private var connectCont: CancellableContinuation<Unit>? = null
    private var mtuCont: CancellableContinuation<Unit>? = null
    private var servicesCont: CancellableContinuation<Unit>? = null
    private var writeCont: CancellableContinuation<Unit>? = null
    private var descriptorCont: CancellableContinuation<Unit>? = null

    fun hasPermissions(): Boolean {
        val needed = if (Build.VERSION.SDK_INT >= 31) {
            listOf(Manifest.permission.BLUETOOTH_SCAN, Manifest.permission.BLUETOOTH_CONNECT)
        } else {
            listOf(Manifest.permission.ACCESS_FINE_LOCATION)
        }
        return needed.all { ContextCompat.checkSelfPermission(appContext, it) == PackageManager.PERMISSION_GRANTED }
    }

    private fun ensureReady() {
        val a = adapter ?: run { state = State.Failed(PhomemoException.unsupported.message!!); throw PhomemoException.unsupported }
        if (!hasPermissions()) { state = State.Unauthorized; throw PhomemoException.unauthorized }
        if (!a.isEnabled) { state = State.PoweredOff; throw PhomemoException.bluetoothOff }
    }

    // ---- Discovery ---------------------------------------------------------------

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult) {
            val record = result.scanRecord
            val resolved = record?.deviceName?.takeIf { it.isNotEmpty() } ?: safeName(result.device)
            val services = record?.serviceUuids?.map { it.uuid } ?: emptyList()
            val serviceMatch = services.any { it in PhomemoUuids.candidateServices }
            val isLikely = serviceMatch || PhomemoUuids.looksLikePhomemo(resolved)
            // Skip anonymous peripherals that don't even self-identify.
            if (resolved.isEmpty() && !isLikely) return
            scope.launch { retain(result.device, resolved.ifEmpty { "Bluetooth printer" }, isLikely) }
        }

        override fun onScanFailed(errorCode: Int) {
            scope.launch { state = State.Failed("Bluetooth scan failed (code $errorCode). Try again.") }
        }
    }

    private fun safeName(device: BluetoothDevice): String = try { device.name ?: "" } catch (_: SecurityException) { "" }

    /**
     * Begin scanning; [discovered] fills as printers advertise. Also seeds from
     * devices the system already has connected over GATT or bonded — a scan
     * often misses those.
     */
    fun startScan() {
        ensureReady()
        seedFromSystem()
        state = State.Scanning
        val settings = ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build()
        adapter?.bluetoothLeScanner?.startScan(null, settings, scanCallback)
    }

    fun stopScan() {
        if (hasPermissions()) {
            try { adapter?.bluetoothLeScanner?.stopScan(scanCallback) } catch (_: Exception) {}
        }
        if (state == State.Scanning) state = State.Idle
    }

    private fun seedFromSystem() {
        val connected = try { manager?.getConnectedDevices(BluetoothProfile.GATT).orEmpty() } catch (_: SecurityException) { emptyList() }
        connected.forEach { retain(it, safeName(it).ifEmpty { "Bluetooth printer" }, true) }
        val bonded = try { adapter?.bondedDevices.orEmpty() } catch (_: SecurityException) { emptySet() }
        bonded.forEach { d ->
            val n = safeName(d)
            if (PhomemoUuids.looksLikePhomemo(n)) retain(d, n, true)
        }
    }

    private fun retain(device: BluetoothDevice, name: String, isLikely: Boolean) {
        val existing = retained[device.address]
        val merged = when {
            name.isNotEmpty() && name != "Bluetooth printer" -> name
            existing != null && existing.name.isNotEmpty() && existing.name != "Bluetooth printer" -> existing.name
            else -> name.ifEmpty { "Bluetooth printer" }
        }
        retained[device.address] = Record(device, merged, isLikely || (existing?.isLikely ?: false))
        rebuildDiscovered()
    }

    private fun rebuildDiscovered() {
        discovered = retained.values
            .filter { showAllDevices || it.isLikely }
            .map { DiscoveredPrinter(it.device.address, it.name, it.isLikely) }
            .sortedWith(compareBy<DiscoveredPrinter> { !it.isLikelyPhomemo }.thenBy { it.name.lowercase() })
    }

    // ---- Connection --------------------------------------------------------------

    suspend fun connect(printer: DiscoveredPrinter) {
        ensureReady()
        val device = retained[printer.id]?.device
            ?: runCatching { adapter?.getRemoteDevice(printer.id) }.getOrNull()
            ?: throw PhomemoException.notFound
        connect(device, printer.name)
    }

    /** Silently reconnect to the saved printer; throws so the caller can fall back to the picker. */
    suspend fun reconnectSaved() {
        val saved = savedPrinterId ?: throw PhomemoException.noSaved
        ensureReady()
        val device = retained[saved]?.device
            ?: runCatching { adapter?.getRemoteDevice(saved) }.getOrNull()
            ?: throw PhomemoException.notFound
        val name = retained[saved]?.name ?: safeName(device).ifEmpty { "Phomemo printer" }
        connect(device, name)
    }

    fun disconnect() {
        try { gatt?.disconnect(); gatt?.close() } catch (_: SecurityException) {}
        gatt = null
        writeChar = null
        state = State.Idle
    }

    fun forgetPaired() {
        savedPrinterId = null
        disconnect()
    }

    private suspend fun connect(device: BluetoothDevice, name: String) {
        stopScan()
        disconnectQuietly()
        state = State.Connecting(name)
        diagnostics = Diagnostics().append("Connecting to “$name”…")

        // The advertised name usually identifies the family; set the model from
        // it so pairing a JADENS never streams Phomemo binary by default.
        PhomemoModel.detect(name)?.let { detected ->
            if (detected != model) {
                model = detected
                log("Model auto-set to ${detected.label} from “$name”.")
            }
        }

        try {
            withTimeout(15_000) {
                suspendCancellableCoroutine<Unit> { cont ->
                    connectCont = cont
                    gatt = device.connectGatt(appContext, false, gattCallback, BluetoothDevice.TRANSPORT_LE)
                }
            }
        } catch (e: TimeoutCancellationException) {
            disconnectQuietly()
            state = State.Failed(PhomemoException.notFound.message!!)
            throw PhomemoException.notFound
        }
        log("Link up.")
        val g = gatt ?: throw PhomemoException.connectFailed

        // A bigger MTU means fewer, larger chunks; failure just keeps 23.
        runCatching {
            withTimeout(3_000) { suspendCancellableCoroutine<Unit> { cont -> mtuCont = cont; g.requestMtu(185) } }
        }

        withTimeout(10_000) {
            suspendCancellableCoroutine<Unit> { cont -> servicesCont = cont; g.discoverServices() }
        }
        val services = g.services.orEmpty()
        if (services.isEmpty()) {
            state = State.Failed(PhomemoException.noServices.message!!)
            throw PhomemoException.noServices
        }
        log("Found ${services.size} service${if (services.size == 1) "" else "s"}.")

        // Walk EVERY service and rank writable characteristics: a known data
        // channel in a known service beats any writable one, because on
        // multi-service printers the first writable can be a config/OTA
        // mailbox where bytes vanish without an error.
        var best: Triple<Int, BluetoothGattCharacteristic, UUID>? = null
        var notify: BluetoothGattCharacteristic? = null
        val allWritable = mutableListOf<BluetoothGattCharacteristic>()
        for (svc in services) {
            val svcKnown = svc.uuid in PhomemoUuids.candidateServices
            for (c in svc.characteristics) {
                val p = c.properties
                val props = listOfNotNull(
                    "write".takeIf { p and BluetoothGattCharacteristic.PROPERTY_WRITE != 0 },
                    "writeNR".takeIf { p and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0 },
                    "notify".takeIf { p and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0 },
                    "read".takeIf { p and BluetoothGattCharacteristic.PROPERTY_READ != 0 },
                )
                log("svc ${PhomemoUuids.shortName(svc.uuid)} → ${PhomemoUuids.shortName(c.uuid)} [${props.joinToString(",")}]")
                if (notify == null && p and BluetoothGattCharacteristic.PROPERTY_NOTIFY != 0) notify = c
                if (!writable(c)) continue
                allWritable += c
                val charKnown = c.uuid in PhomemoUuids.candidateWriteChars
                val score = when {
                    charKnown && svcKnown -> 4
                    charKnown -> 3
                    svcKnown -> 2
                    else -> 1
                }
                if (score > (best?.first ?: 0)) best = Triple(score, c, svc.uuid)
            }
        }
        val picked = best ?: run {
            state = State.Failed(PhomemoException.noWritable.message!!)
            throw PhomemoException.noWritable
        }
        val wc = picked.second
        writeChar = wc
        alternateWriteChars = allWritable.filter { it.uuid != wc.uuid }
        diagnostics = diagnostics.copy(
            serviceUuid = PhomemoUuids.shortName(picked.third),
            writeCharUuid = PhomemoUuids.shortName(wc.uuid),
            supportsWrite = wc.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0,
            supportsWriteWithoutResponse = wc.properties and BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE != 0,
        )
        log("Picked ${PhomemoUuids.shortName(wc.uuid)} (rank ${picked.first}/4).")

        // Some M110 firmware silently drops writes unless a client is
        // subscribed for status notifications.
        val n = notify
        if (n != null) {
            subscribe(g, n)
            diagnostics = diagnostics.copy(notifyCharUuid = PhomemoUuids.shortName(n.uuid), notificationsSubscribed = true)
            log("Notify char: ${PhomemoUuids.shortName(n.uuid)}")
        } else {
            log("No notify channel available.")
        }

        savedPrinterId = device.address
        retain(device, name, true)
        state = State.Ready(name)
        log("Ready.")
    }

    private fun disconnectQuietly() {
        try { gatt?.close() } catch (_: SecurityException) {}
        gatt = null
        writeChar = null
    }

    private fun writable(c: BluetoothGattCharacteristic) =
        c.properties and (BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE) != 0

    private suspend fun subscribe(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
        g.setCharacteristicNotification(c, true)
        val d = c.getDescriptor(PhomemoUuids.cccd) ?: return
        runCatching {
            withTimeout(3_000) {
                suspendCancellableCoroutine<Unit> { cont ->
                    descriptorCont = cont
                    if (Build.VERSION.SDK_INT >= 33) {
                        g.writeDescriptor(d, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE)
                    } else {
                        @Suppress("DEPRECATION")
                        d.value = BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE
                        @Suppress("DEPRECATION")
                        g.writeDescriptor(d)
                    }
                }
            }
        }
    }

    // ---- Printing ----------------------------------------------------------------

    private fun requireConnected(): Pair<BluetoothGatt, BluetoothGattCharacteristic> {
        // One job at a time: two concurrent print paths interleave BLE chunks
        // into mid-bitmap garbage.
        if (state == State.Printing) throw PhomemoException.busy
        val g = gatt ?: throw PhomemoException.notConnected
        val c = writeChar ?: throw PhomemoException.notConnected
        return g to c
    }

    private val readyName: String get() = (state as? State.Ready)?.name ?: "Printer"

    /** Render [image] as a 1-bit raster in the model's dialect and send it. */
    suspend fun printImage(image: Bitmap, printWidth: Int? = null) {
        val (g, c) = requireConnected()
        val name = readyName
        val width = printWidth ?: model.defaultPrintWidth
        state = State.Printing
        try {
            val raster = PhomemoRaster.encode(image, width)
            writeChunks(g, c, PhomemoRaster.commandStream(raster, width, model))
            state = State.Ready(name)
        } catch (e: Exception) {
            state = State.Failed("Print failed: ${e.userMessage}")
            throw e
        }
    }

    /** A solid black bar: if this prints and the label doesn't, the bug is in the compositor. */
    suspend fun printTestPage() {
        val (g, c) = requireConnected()
        val name = readyName
        state = State.Printing
        try {
            writeChunks(g, c, PhomemoRaster.testPagePayload(model.defaultPrintWidth, model))
            state = State.Ready(name)
        } catch (e: Exception) {
            state = State.Failed("Test print failed: ${e.userMessage}")
            throw e
        }
    }

    /**
     * Field bisect for a silent printer: one visibly different test in every
     * dialect — TSPL text, a short M02 band, a tall M110 band, a medium
     * ESC/POS band — so whichever prints names the protocol.
     */
    suspend fun runProtocolSweep() {
        val (g, c) = requireConnected()
        val name = readyName
        state = State.Printing
        try {
            val jobs = listOf(
                "TSPL (text)" to PhomemoRaster.testPagePayload(PhomemoModel.Jadens.defaultPrintWidth, PhomemoModel.Jadens),
                "M02 (short band)" to PhomemoRaster.band(32, PhomemoModel.M02.defaultPrintWidth, PhomemoModel.M02),
                "M110 (tall band)" to PhomemoRaster.band(128, PhomemoModel.M110.defaultPrintWidth, PhomemoModel.M110),
                "ESC/POS (medium band)" to PhomemoRaster.band(64, PhomemoModel.Generic.defaultPrintWidth, PhomemoModel.Generic),
            )
            jobs.forEachIndexed { i, (label, payload) ->
                log("Sweep ${i + 1}/${jobs.size}: $label, ${payload.size} bytes → ${PhomemoUuids.shortName(c.uuid)}")
                writeChunks(g, c, payload)
                delay(2_500)
            }
            // The ranked pick can be a writable-but-dead mailbox: repeat the two
            // likeliest dialects on every other writable characteristic.
            for (alt in alternateWriteChars) {
                for ((label, payload) in listOf(jobs[0], jobs[3])) {
                    log("Sweep alt: $label, ${payload.size} bytes → ${PhomemoUuids.shortName(alt.uuid)}")
                    writeChunks(g, alt, payload)
                    delay(2_500)
                }
            }
            log("Sweep complete — whichever sticker printed names the protocol (and the channel).")
        } finally {
            state = State.Ready(name)
        }
    }

    private suspend fun writeChunks(g: BluetoothGatt, c: BluetoothGattCharacteristic, data: ByteArray) {
        val withResponse = c.properties and BluetoothGattCharacteristic.PROPERTY_WRITE != 0
        val type = if (withResponse) BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT else BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
        val chunkSize = minOf(96, maxOf(20, mtu - 3))
        diagnostics = diagnostics.copy(bytesTotal = data.size, bytesSent = 0)
        log("Writing ${data.size} bytes…")
        var offset = 0
        while (offset < data.size) {
            val end = minOf(offset + chunkSize, data.size)
            val chunk = data.copyOfRange(offset, end)
            // Android reports completion for both write types, which is the
            // flow control: wait for it, then pace like the iOS driver.
            withTimeout(5_000) {
                suspendCancellableCoroutine<Unit> { cont ->
                    writeCont = cont
                    val started = if (Build.VERSION.SDK_INT >= 33) {
                        g.writeCharacteristic(c, chunk, type) == BluetoothStatusCodes.SUCCESS
                    } else {
                        @Suppress("DEPRECATION")
                        c.writeType = type
                        @Suppress("DEPRECATION")
                        c.value = chunk
                        @Suppress("DEPRECATION")
                        g.writeCharacteristic(c)
                    }
                    if (!started) {
                        writeCont = null
                        cont.resumeWithException(PhomemoException("The printer refused a write. Move closer and try again."))
                    }
                }
            }
            delay(if (withResponse) 8 else 25)
            offset = end
            diagnostics = diagnostics.copy(bytesSent = offset)
        }
        log("Wrote ${data.size} bytes OK.")
    }

    private fun log(line: String) { diagnostics = diagnostics.append(line) }

    /** Everything the diagnostics card shows, as one pasteable block. */
    fun diagnosticsExport(): String = buildString {
        val d = diagnostics
        appendLine("YardHarvest printer diagnostics")
        appendLine("model: ${model.detailedLabel}")
        appendLine("service: ${d.serviceUuid ?: "—"}")
        appendLine("writeChar: ${d.writeCharUuid ?: "—"} (write=${d.supportsWrite} writeNR=${d.supportsWriteWithoutResponse})")
        appendLine("notifyChar: ${d.notifyCharUuid ?: "none"} subscribed=${d.notificationsSubscribed}")
        appendLine("bytes: ${d.bytesSent}/${d.bytesTotal}")
        d.lastNotification?.let { appendLine("lastReply: $it") }
        appendLine("log:")
        d.log.forEach { appendLine("  $it") }
    }

    // ---- GATT callbacks (binder threads → main) ---------------------------------------

    private val gattCallback = object : BluetoothGattCallback() {
        override fun onConnectionStateChange(g: BluetoothGatt, status: Int, newState: Int) {
            scope.launch {
                if (newState == BluetoothProfile.STATE_CONNECTED && status == BluetoothGatt.GATT_SUCCESS) {
                    connectCont?.takeIf { it.isActive }?.resume(Unit)
                    connectCont = null
                } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                    connectCont?.takeIf { it.isActive }?.resumeWithException(PhomemoException.connectFailed)
                    connectCont = null
                    writeCont?.takeIf { it.isActive }?.resumeWithException(PhomemoException.notConnected)
                    writeCont = null
                    if (state is State.Ready) state = State.Idle
                    writeChar = null
                }
            }
        }

        override fun onMtuChanged(g: BluetoothGatt, newMtu: Int, status: Int) {
            scope.launch {
                if (status == BluetoothGatt.GATT_SUCCESS) mtu = newMtu
                mtuCont?.takeIf { it.isActive }?.resume(Unit)
                mtuCont = null
            }
        }

        override fun onServicesDiscovered(g: BluetoothGatt, status: Int) {
            scope.launch {
                val cont = servicesCont ?: return@launch
                servicesCont = null
                if (!cont.isActive) return@launch
                if (status == BluetoothGatt.GATT_SUCCESS) cont.resume(Unit)
                else cont.resumeWithException(PhomemoException.noServices)
            }
        }

        override fun onCharacteristicWrite(g: BluetoothGatt, c: BluetoothGattCharacteristic, status: Int) {
            scope.launch {
                val cont = writeCont ?: return@launch
                writeCont = null
                if (!cont.isActive) return@launch
                if (status == BluetoothGatt.GATT_SUCCESS) cont.resume(Unit)
                else cont.resumeWithException(PhomemoException("The printer rejected a write (status $status)."))
            }
        }

        override fun onDescriptorWrite(g: BluetoothGatt, d: BluetoothGattDescriptor, status: Int) {
            scope.launch {
                descriptorCont?.takeIf { it.isActive }?.resume(Unit)
                descriptorCont = null
            }
        }

        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic, value: ByteArray) {
            notification(value)
        }

        /** Pre-Android 13 delivery of the same notification. */
        @Suppress("OVERRIDE_DEPRECATION")
        override fun onCharacteristicChanged(g: BluetoothGatt, c: BluetoothGattCharacteristic) {
            @Suppress("DEPRECATION")
            if (Build.VERSION.SDK_INT < 33) c.value?.let { notification(it) }
        }

        /** Status bytes the firmware pushes — paper out, cover open, job acks. */
        private fun notification(value: ByteArray) {
            val hex = value.joinToString(" ") { "%02X".format(it) }
            scope.launch {
                diagnostics = diagnostics.copy(lastNotification = hex)
                log("Notify: $hex")
            }
        }
    }

    companion object {
        private const val MODEL_KEY = "yh.phomemo.model"
        private const val SAVED_KEY = "yh.phomemo.savedPrinterID"
    }
}
