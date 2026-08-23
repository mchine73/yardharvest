import Foundation
import CoreBluetooth
import Observation
import UIKit

/// Native Core Bluetooth driver for Phomemo thermal label printers — M02
/// family (M02, M02S, M02 Pro, T02, PR02 and siblings). Implements the
/// printer's ESC/POS-style raster protocol directly so the YardHarvest app
/// can print QR labels without depending on any third-party Phomemo iOS app.
///
/// Architecture:
///   • `PhomemoPrinterManager` owns the `CBCentralManager`, surfaces state
///     for SwiftUI (`@Observable`), and persists the last paired printer
///     UUID to UserDefaults so subsequent prints auto-reconnect.
///   • Discovery happens through THREE channels and the union is shown
///     in the picker:
///       1. Active BLE scan (catches printers currently advertising).
///       2. `retrieveConnectedPeripherals(withServices:)` — catches
///          printers already connected to the system via another app
///          or via the Phomemo's own service advertisement.
///       3. `retrievePeripherals(withIdentifiers:)` for the saved UUID,
///          used silently on auto-reconnect.
///     Critically, every discovered `CBPeripheral` is retained in a
///     `[UUID: CBPeripheral]` dictionary — without that, `central.connect`
///     fails because CB doesn't keep its own references.
///   • Connection: connect → discover ALL services (we don't pre-guess
///     the UUID, since it varies by Phomemo model) → walk services
///     looking for the first writable characteristic → ready.
///   • Printing: encode UIImage as a 1-bit packed raster 384 pixels wide
///     (M02-family native head width at 203 DPI), emit ESC/POS-style
///     command stream, chunk over BLE writes sized to the peripheral's
///     reported MTU.
///
/// If a different Phomemo model needs different commands or width, the
/// two knobs are `PhomemoRaster.commandStream` (init sequence) and the
/// `printWidth` parameter on `printImage`.

// MARK: - Public surface

/// Which printer family we're talking to. Different families speak
/// different command sets — sending M02 commands to an M110 (or vice
/// versa) lands the bytes in the buffer but never fires the heating
/// elements. The picker UI lets the admin choose; we persist the
/// selection so it sticks across prints.
enum PhomemoModel: String, CaseIterable, Identifiable, Hashable {
    /// Phomemo M02 family — 80 mm thermal receipt printer (M02, M02S,
    /// M02 Pro, T02, PR02). Pure-ish ESC/POS with one Phomemo flush byte.
    case m02
    /// Phomemo M110 family — 40 mm label printer with peeler (M110, M120,
    /// M200, M220, D110, D11). Phomemo proprietary protocol.
    case m110
    /// Generic ESC/POS BLE thermal printer (58 mm receipt-style, no
    /// label gap). Covers the long tail of cheap white-label thermal
    /// printers — NETUM, GOOJPRT, Rongta, POS-mate, MPT/MTP receipt
    /// printers, etc. — that implement a common ESC/POS subset
    /// (`ESC @` + `GS v 0` raster + `ESC d` feed) and expose
    /// `FF00`/`FF02` (or similar) BLE characteristics.
    case generic
    /// JADENS BT-series sticker / shipping-label printer (BT203, BT460,
    /// BT420, etc.). **Speaks TSPL2** (Taiwan Semiconductor Printer
    /// Language) — fundamentally different from ESC/POS. The default
    /// here is tuned for the BT203 with 40 × 30 mm sticker rolls (the
    /// cheap commodity sticker printer most likely to be bundled with
    /// an annual membership). BT460 / BT420 owners can swap to wider
    /// labels by adjusting the canvas size in the QR sheet — the TSPL
    /// SIZE command is derived from the raster dimensions.
    case jadens

    /// Best-effort family detection from the advertised BLE name. Returns
    /// nil when the name doesn't clearly identify a family, in which case
    /// the user's picker choice stands. Exists because the four families
    /// speak mutually unintelligible protocols: streaming Phomemo binary at
    /// a TSPL printer produces the most misleading failure there is —
    /// connects fine, accepts every byte, prints nothing.
    static func detect(fromName name: String) -> PhomemoModel? {
        let u = name.uppercased()
        if ["JADENS", "BT203", "BT201", "BT420", "BT460", "JD-"].contains(where: u.contains) {
            return .jadens
        }
        if ["M110", "M120", "M200", "M220", "D110", "D11 ", "D30", "D35"].contains(where: u.contains) {
            return .m110
        }
        if ["M02", "M03", "T02", "PR02"].contains(where: u.contains) {
            return .m02
        }
        return nil
    }

    var id: String { rawValue }
    var label: String {
        switch self {
        case .m02:     return "M02"
        case .m110:    return "M110"
        case .generic: return "Generic"
        case .jadens:  return "JADENS"
        }
    }

    /// Long form for the help text under the picker.
    var detailedLabel: String {
        switch self {
        case .m02:     return "Phomemo M02 (80 mm receipt)"
        case .m110:    return "Phomemo M110 (40 mm label)"
        case .generic: return "Generic ESC/POS (58 mm receipt)"
        case .jadens:  return "JADENS BT-series (40 × 30 mm sticker, TSPL)"
        }
    }

    /// Native print head width in pixels. M02 = 80 mm × 8 dpi/mm head.
    /// M110 = 40 mm × 8 dpi/mm. Generic 58 mm thermal printers also use
    /// a 384-dot head. JADENS BT203 uses a 48 mm head but the default
    /// sticker rolls are 40 mm, so we match the label width to keep the
    /// composition centered on the sticker (the extra 8 mm of head
    /// stays unprinted, which is the desired behavior for label media).
    var defaultPrintWidth: Int {
        switch self {
        case .m02: return 384
        case .m110: return 320
        case .generic: return 384
        case .jadens: return 320
        }
    }

    /// Default label height in pixels. M02 + generic use continuous
    /// paper so we match the width for a square label. M110 + JADENS
    /// ship with 40 × 30 mm labels by default.
    var defaultLabelHeight: Int {
        switch self {
        case .m02: return 384       // square, continuous paper
        case .m110: return 240      // 30 mm × 8 dpi/mm
        case .generic: return 384   // square, continuous paper
        case .jadens: return 240    // 30 mm × 8 dpi/mm
        }
    }
}

@MainActor
@Observable
final class PhomemoPrinterManager: NSObject {

    enum State: Equatable {
        case poweredOff
        case unauthorized
        case idle                       // ready, no scan in progress
        case scanning
        case connecting(name: String)
        case ready(name: String)        // connected + characteristic ready
        case printing
        case failed(String)
    }

    /// Which printer family to target. Defaults to M110 since that's
    /// what's confirmed working hardware for YardHarvest tool labels.
    /// Persisted to UserDefaults so the user doesn't re-pick each time.
    var model: PhomemoModel {
        get {
            let raw = UserDefaults.standard.string(forKey: Self.modelKey) ?? PhomemoModel.m110.rawValue
            return PhomemoModel(rawValue: raw) ?? .m110
        }
        set { UserDefaults.standard.set(newValue.rawValue, forKey: Self.modelKey) }
    }
    private static let modelKey = "yh.phomemo.model"

    /// One discovered printer surfaced to the picker UI. `isLikelyPhomemo`
    /// is a hint from the name/service heuristics — UI shows a "Phomemo"
    /// badge so the user can spot theirs quickly when "Show all devices"
    /// is enabled.
    struct DiscoveredPrinter: Identifiable, Hashable {
        let id: UUID
        let name: String
        let isLikelyPhomemo: Bool
    }

    private(set) var state: State = .idle
    private(set) var discovered: [DiscoveredPrinter] = []

    /// Toggled by the picker UI. When false (default) only printers whose
    /// name or advertised services match a Phomemo heuristic are shown.
    /// Flip on if the user's printer broadcasts an unfamiliar name.
    var showAllDevices: Bool = false {
        didSet { rebuildDiscoveredList() }
    }

    /// Identifier of the printer we most recently paired with. Persisted
    /// across launches so the next print auto-reconnects silently.
    var savedPrinterID: UUID? {
        get {
            guard let str = UserDefaults.standard.string(forKey: Self.savedKey) else { return nil }
            return UUID(uuidString: str)
        }
        set {
            if let uuid = newValue {
                UserDefaults.standard.set(uuid.uuidString, forKey: Self.savedKey)
            } else {
                UserDefaults.standard.removeObject(forKey: Self.savedKey)
            }
        }
    }
    private static let savedKey = "yh.phomemo.savedPrinterID"

    // MARK: - CB plumbing

    private var central: CBCentralManager!

    /// **The fix.** Every peripheral we see in `didDiscover` (and every
    /// retrieved peripheral) gets stored here keyed by its CB identifier.
    /// Without holding a strong reference, `central.connect(...)` can't
    /// find the peripheral later — CB doesn't keep its own. This was the
    /// root cause of "tapping a row does nothing" / `peripheralNotFound`.
    private var retained: [UUID: PeripheralRecord] = [:]

    /// One row in `retained`. Tracks the peripheral plus the hints we
    /// use to badge it as "likely Phomemo" in the UI.
    private struct PeripheralRecord {
        let peripheral: CBPeripheral
        var name: String
        var isLikelyPhomemo: Bool
    }

    private var pendingPeripheral: CBPeripheral?
    private var writeCharacteristic: CBCharacteristic?
    /// Other writable characteristics seen during the walk — the sweep tries
    /// these too, in case the ranked pick is a dead mailbox on this board.
    private var alternateWriteCharacteristics: [CBCharacteristic] = []
    private var notifyCharacteristic: CBCharacteristic?
    /// Continuations for the various async waits. Each is consumed once.
    private var centralReadyContinuation: CheckedContinuation<Void, Error>?
    private var connectContinuation: CheckedContinuation<CBPeripheral, Error>?
    private var servicesContinuation: CheckedContinuation<Void, Error>?
    private var characteristicsContinuation: CheckedContinuation<[CBCharacteristic], Error>?
    private var writeContinuation: CheckedContinuation<Void, Error>?

    // MARK: - Diagnostics surfaced to the picker UI

    /// Step-by-step status — picker overlays it so we can see exactly
    /// what's happening when "still doesn't print" comes up. Reset on
    /// each connect/print.
    private(set) var diagnostics: PrinterDiagnostics = .init()

    struct PrinterDiagnostics: Equatable {
        var serviceUUID: String?
        var writeCharUUID: String?
        var notifyCharUUID: String?
        var supportsWrite: Bool = false
        var supportsWriteWithoutResponse: Bool = false
        var notificationsSubscribed: Bool = false
        var bytesSent: Int = 0
        var bytesTotal: Int = 0
        var lastNotification: String?
        var log: [String] = []

        mutating func append(_ line: String) {
            log.append(line)
            if log.count > 12 { log.removeFirst(log.count - 12) }
        }
    }

    override init() {
        super.init()
        central = CBCentralManager(delegate: self, queue: .main, options: [
            CBCentralManagerOptionShowPowerAlertKey: true
        ])
    }

    // MARK: - Discovery

    /// Begins scanning. Populates `discovered` as nearby Phomemo printers
    /// (and, if `showAllDevices` is on, any other named BLE peripheral)
    /// advertise. Call `stopScan()` or `connect(...)` to stop.
    ///
    /// Also seeds the discovered list from
    /// `retrieveConnectedPeripherals(withServices:)` — that catches a
    /// printer already connected to the system via another app, or
    /// reachable via classic pairing routed through GATT.
    func startScan() async throws {
        try await ensurePoweredOn()
        // Don't clobber the existing discovered list — we want already-
        // surfaced peripherals (especially the saved one) to remain
        // tappable while a fresh scan layers in new finds.
        seedFromSystemConnectedPeripherals()
        state = .scanning
        // Scanning with `nil` services + filtering at display time. This
        // gives us the broadest catch — some Phomemo models advertise
        // their service UUID, others don't, and Apple's BLE stack will
        // drop name-only advertisements when filtered by service.
        central.scanForPeripherals(withServices: nil, options: [
            CBCentralManagerScanOptionAllowDuplicatesKey: false
        ])
    }

    func stopScan() {
        if central.isScanning { central.stopScan() }
        if case .scanning = state { state = .idle }
    }

    /// Asks the system for any peripherals already connected and exposing
    /// a Phomemo-family service UUID. This catches the case where the
    /// printer was paired through another app or where iOS has it
    /// connected at the system level — the BLE scan often misses these.
    private func seedFromSystemConnectedPeripherals() {
        let connected = central.retrieveConnectedPeripherals(
            withServices: PhomemoUUIDs.candidateServices)
        for peripheral in connected {
            let name = peripheral.name ?? "Bluetooth Printer"
            retainPeripheral(peripheral, name: name,
                             isLikelyPhomemo: true)
        }
    }

    /// Connects to a previously-discovered printer (or one returned by
    /// the system-connected seed). Drives the BLE handshake all the way
    /// to "ready to print".
    func connect(_ printer: DiscoveredPrinter) async throws {
        // The bug fix: prefer the peripheral we already retained from
        // `didDiscover`. Fall back to `retrievePeripherals(withIdentifiers:)`
        // (works only for previously-known peripherals) so we still
        // handle the saved-printer auto-reconnect path.
        let peripheral: CBPeripheral
        if let rec = retained[printer.id] {
            peripheral = rec.peripheral
        } else if let p = central.retrievePeripherals(withIdentifiers: [printer.id]).first {
            peripheral = p
            retainPeripheral(p, name: printer.name,
                             isLikelyPhomemo: printer.isLikelyPhomemo)
        } else {
            throw PhomemoError.peripheralNotFound
        }
        try await connect(peripheral: peripheral, name: printer.name)
    }

    /// Auto-reconnect: silently reconnects to the saved printer if it's
    /// reachable. Throws if we have no saved printer or it's not
    /// retrievable — caller falls back to the picker.
    func reconnectSaved() async throws {
        guard let saved = savedPrinterID else {
            throw PhomemoError.noSavedPrinter
        }
        try await ensurePoweredOn()
        let peripheral: CBPeripheral
        if let rec = retained[saved] {
            peripheral = rec.peripheral
        } else if let p = central.retrievePeripherals(withIdentifiers: [saved]).first {
            peripheral = p
            let name = p.name ?? "Phomemo printer"
            retainPeripheral(p, name: name, isLikelyPhomemo: true)
        } else {
            // The saved peripheral isn't immediately retrievable. Run a
            // brief scan and try again — covers the case where the
            // printer was off and just woke up.
            try await briefScan(forSavedID: saved)
            guard let rec = retained[saved] else {
                throw PhomemoError.peripheralNotFound
            }
            peripheral = rec.peripheral
        }
        let name = retained[saved]?.name ?? peripheral.name ?? "Phomemo printer"
        try await connect(peripheral: peripheral, name: name)
    }

    /// Runs a 3-second scan looking specifically for the saved printer.
    /// Used by `reconnectSaved` when the system has no cached copy.
    private func briefScan(forSavedID saved: UUID) async throws {
        state = .scanning
        central.scanForPeripherals(withServices: nil, options: [
            CBCentralManagerScanOptionAllowDuplicatesKey: false
        ])
        defer { stopScan() }
        // Poll up to 3s for the saved peripheral to show up.
        for _ in 0..<30 {
            try await Task.sleep(nanoseconds: 100_000_000)
            if retained[saved] != nil { return }
        }
    }

    func disconnect() {
        if let p = pendingPeripheral {
            central.cancelPeripheralConnection(p)
        }
        pendingPeripheral = nil
        writeCharacteristic = nil
        state = .idle
    }

    /// Clear pairing — forget the saved printer and drop retained refs.
    /// Useful for "pair a different printer" in the UI.
    func forgetPaired() {
        savedPrinterID = nil
        disconnect()
    }

    // MARK: - Print

    /// Renders the given image as a 1-bit raster and sends it to the
    /// already-connected printer. Image is composed onto a model-
    /// appropriate canvas (M110 = 320 px, M02 = 384 px). Caller can
    /// override `printWidth` for non-standard label sizes.
    func printImage(_ image: UIImage, printWidth: Int? = nil) async throws {
        // One job at a time. Two print paths ran concurrently in the field
        // and their BLE chunks interleaved — mid-BITMAP garbage to the
        // printer, and a "Bytes sent 9719/3092" display to us.
        if case .printing = state { throw PhomemoError.busyPrinting }

        guard let characteristic = writeCharacteristic,
              let peripheral = pendingPeripheral,
              peripheral.state == .connected else {
            throw PhomemoError.notConnected
        }
        let name: String
        if case .ready(let n) = state { name = n }
        else { name = peripheral.name ?? "Phomemo" }

        let width = printWidth ?? model.defaultPrintWidth
        state = .printing
        do {
            let raster = PhomemoRaster.encode(image: image, width: width)
            let stream = PhomemoRaster.commandStream(raster: raster,
                                                     widthPixels: width,
                                                     model: model)
            try await writeChunks(stream, to: characteristic, of: peripheral)
            state = .ready(name: name)
        } catch {
            state = .failed("Print failed: \(error.localizedDescription)")
            throw error
        }
    }

    /// Prints a tiny test page — a solid black bar — to verify the
    /// protocol layer end-to-end without relying on the QR composer
    /// having rendered correctly. Used by the picker's "Print test"
    /// button. If THIS prints but the real QR label doesn't, the bug is
    /// in the label compositor; if THIS doesn't print, it's the protocol
    /// stream and we need a different model setting.
    func printTestPage() async throws {
        // One job at a time. Two print paths ran concurrently in the field
        // and their BLE chunks interleaved — mid-BITMAP garbage to the
        // printer, and a "Bytes sent 9719/3092" display to us.
        if case .printing = state { throw PhomemoError.busyPrinting }

        guard let characteristic = writeCharacteristic,
              let peripheral = pendingPeripheral,
              peripheral.state == .connected else {
            throw PhomemoError.notConnected
        }
        let name: String
        if case .ready(let n) = state { name = n }
        else { name = peripheral.name ?? "Phomemo" }

        state = .printing
        do {
            let stream = PhomemoRaster.testPagePayload(
                widthPixels: model.defaultPrintWidth,
                model: model)
            try await writeChunks(stream, to: characteristic, of: peripheral)
            state = .ready(name: name)
        } catch {
            state = .failed("Test print failed: \(error.localizedDescription)")
            throw error
        }
    }

    /// Field bisect for a silent printer: fire a distinguishable test in
    /// every protocol we speak, pausing between them. Whichever sticker
    /// actually prints identifies the dialect the board accepts — no BLE
    /// sniffer, no diagnostics round-trip, the printer answers for itself.
    ///
    /// The four payloads are visually distinct on paper:
    ///   1. TSPL      — text: "YARDHARVEST / TSPL test OK"
    ///   2. M02       — a SHORT black band (32 rows)
    ///   3. M110      — a TALL black band (128 rows)
    ///   4. ESC/POS   — a MEDIUM black band (64 rows)
    /// so "which one printed?" is answerable at a glance. The chosen model
    /// is left untouched — the caller applies the user's answer.
    func runProtocolSweep() async throws {
        // One job at a time. Two print paths ran concurrently in the field
        // and their BLE chunks interleaved — mid-BITMAP garbage to the
        // printer, and a "Bytes sent 9719/3092" display to us.
        if case .printing = state { throw PhomemoError.busyPrinting }

        guard let characteristic = writeCharacteristic,
              let peripheral = pendingPeripheral,
              peripheral.state == .connected else {
            throw PhomemoError.notConnected
        }
        let name: String
        if case .ready(let n) = state { name = n }
        else { name = peripheral.name ?? "Printer" }

        state = .printing
        defer { state = .ready(name: name) }

        func band(_ rows: Int, width: Int, model: PhomemoModel) -> Data {
            let widthBytes = width / 8
            var raster = Data(count: widthBytes * rows)
            for i in 0..<raster.count { raster[i] = 0xFF }
            return PhomemoRaster.commandStream(
                raster: PhomemoRaster.Raster(width: width, height: rows, data: raster),
                widthPixels: width, model: model)
        }

        let jobs: [(label: String, payload: Data)] = [
            ("TSPL (text)", PhomemoRaster.testPagePayload(
                widthPixels: PhomemoModel.jadens.defaultPrintWidth, model: .jadens)),
            ("M02 (short band)", band(32, width: PhomemoModel.m02.defaultPrintWidth, model: .m02)),
            ("M110 (tall band)", band(128, width: PhomemoModel.m110.defaultPrintWidth, model: .m110)),
            ("ESC/POS (medium band)", band(64, width: PhomemoModel.generic.defaultPrintWidth, model: .generic)),
        ]
        for (i, job) in jobs.enumerated() {
            diagnostics.append("Sweep \(i + 1)/\(jobs.count): \(job.label), \(job.payload.count) bytes → \(characteristic.uuid.uuidString)")
            try await writeChunks(job.payload, to: characteristic, of: peripheral)
            // Give the printer time to act (or visibly not) before the next
            // dialect lands in its buffer.
            try await Task.sleep(nanoseconds: 2_500_000_000)
        }
        // Round two: the ranked pick can be a writable-but-dead mailbox.
        // Repeat the two most likely dialects on every other writable
        // characteristic the walk found.
        for alt in alternateWriteCharacteristics {
            for job in [jobs[0], jobs[3]] {
                diagnostics.append("Sweep alt: \(job.label), \(job.payload.count) bytes → \(alt.uuid.uuidString)")
                try await writeChunks(job.payload, to: alt, of: peripheral)
                try await Task.sleep(nanoseconds: 2_500_000_000)
            }
        }
        diagnostics.append("Sweep complete — whichever sticker printed names the protocol (and the channel).")
    }

    // MARK: - Internal helpers

    /// Retains a peripheral, updates its hints, and refreshes the public
    /// `discovered` list. Called from `didDiscover`,
    /// `seedFromSystemConnectedPeripherals`, and `connect`.
    private func retainPeripheral(_ peripheral: CBPeripheral,
                                  name: String,
                                  isLikelyPhomemo: Bool) {
        let id = peripheral.identifier
        let existing = retained[id]
        let mergedName: String = {
            // Prefer a non-empty new name over a fallback default.
            if !name.isEmpty && name != "Bluetooth Printer" { return name }
            if let existing, !existing.name.isEmpty,
               existing.name != "Bluetooth Printer" { return existing.name }
            return name.isEmpty ? "Bluetooth Printer" : name
        }()
        let mergedHint = isLikelyPhomemo || (existing?.isLikelyPhomemo ?? false)
        retained[id] = PeripheralRecord(peripheral: peripheral,
                                        name: mergedName,
                                        isLikelyPhomemo: mergedHint)
        rebuildDiscoveredList()
    }

    /// Recomputes `discovered` from `retained` honoring `showAllDevices`.
    /// Phomemo-likely entries always appear; everything else only when
    /// the user opts in to seeing the full BLE scan.
    private func rebuildDiscoveredList() {
        let rows = retained.values.compactMap { rec -> DiscoveredPrinter? in
            if !showAllDevices && !rec.isLikelyPhomemo { return nil }
            return DiscoveredPrinter(id: rec.peripheral.identifier,
                                     name: rec.name,
                                     isLikelyPhomemo: rec.isLikelyPhomemo)
        }
        // Stable sort: Phomemo-tagged first, then by name.
        discovered = rows.sorted { a, b in
            if a.isLikelyPhomemo != b.isLikelyPhomemo {
                return a.isLikelyPhomemo && !b.isLikelyPhomemo
            }
            return a.name.localizedCaseInsensitiveCompare(b.name) == .orderedAscending
        }
    }

    private func connect(peripheral: CBPeripheral, name: String) async throws {
        stopScan()
        state = .connecting(name: name)
        pendingPeripheral = peripheral
        peripheral.delegate = self
        diagnostics = PrinterDiagnostics()
        diagnostics.append("Connecting to “\(name)”…")

        // The advertised name usually identifies the printer family. Set the
        // model from it so pairing a JADENS never silently streams Phomemo
        // binary because the picker was left on its default. The picker can
        // still override afterwards; the next connect re-detects.
        if let detected = PhomemoModel.detect(fromName: name), detected != model {
            model = detected
            diagnostics.append("Model auto-set to \(detected.label) from “\(name)”.")
        }

        // Step 1: connect
        _ = try await withCheckedThrowingContinuation { (cont: CheckedContinuation<CBPeripheral, Error>) in
            connectContinuation = cont
            central.connect(peripheral, options: nil)
        }
        diagnostics.append("Link up.")

        // Step 2: discover ALL services
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
            servicesContinuation = cont
            peripheral.discoverServices(nil)
        }

        guard let services = peripheral.services, !services.isEmpty else {
            throw PhomemoError.serviceNotFound
        }
        diagnostics.append("Found \(services.count) service\(services.count == 1 ? "" : "s").")

        // Step 3: walk each service, discover its characteristics, and
        // pick a writable + a notify channel. The notify subscription is
        // critical for Phomemo M110 — some firmware revs silently drop
        // writes if no client is subscribed for status notifications.
        // Walk EVERY service before choosing. The old walk stopped at the
        // first writable characteristic in the first service that had one —
        // on multi-service printers that can be a config/OTA characteristic,
        // and bytes written there vanish without an error. Rank instead:
        //   1. a known data-channel characteristic inside a known service
        //   2. a known data-channel characteristic anywhere
        //   3. any writable characteristic in a known service
        //   4. any writable characteristic at all
        // …and log the full map so the diagnostics pane shows exactly what
        // the printer exposes and what got picked.
        var best: (score: Int, char: CBCharacteristic, svc: CBService)?
        var foundNotify: CBCharacteristic?
        var allWritable: [CBCharacteristic] = []
        for svc in services {
            let chars = try await discoverCharacteristics(for: svc, on: peripheral)
            let svcKnown = PhomemoUUIDs.candidateServices.contains(svc.uuid)
            for c in chars {
                var props: [String] = []
                if c.properties.contains(.write) { props.append("write") }
                if c.properties.contains(.writeWithoutResponse) { props.append("writeNR") }
                if c.properties.contains(.notify) { props.append("notify") }
                if c.properties.contains(.read) { props.append("read") }
                diagnostics.append("svc \(svc.uuid.uuidString) → \(c.uuid.uuidString) [\(props.joined(separator: ","))]")
                if foundNotify == nil, c.properties.contains(.notify) {
                    foundNotify = c
                }
                guard writable(c) else { continue }
                allWritable.append(c)
                let charKnown = PhomemoUUIDs.candidateWriteChars.contains(c.uuid)
                let score: Int
                switch (charKnown, svcKnown) {
                case (true, true):   score = 4
                case (true, false):  score = 3
                case (false, true):  score = 2
                case (false, false): score = 1
                }
                if score > (best?.score ?? 0) { best = (score, c, svc) }
            }
        }
        guard let picked = best else {
            throw PhomemoError.characteristicNotFound
        }
        let writeChar = picked.char
        alternateWriteCharacteristics = allWritable.filter { $0.uuid != picked.char.uuid }
        diagnostics.serviceUUID = picked.svc.uuid.uuidString
        diagnostics.append("Picked \(writeChar.uuid.uuidString) (rank \(picked.score)/4).")
        writeCharacteristic = writeChar
        diagnostics.writeCharUUID = writeChar.uuid.uuidString
        diagnostics.supportsWrite = writeChar.properties.contains(.write)
        diagnostics.supportsWriteWithoutResponse = writeChar.properties.contains(.writeWithoutResponse)
        diagnostics.append("Write char: \(writeChar.uuid.uuidString)")

        // Subscribe to notifications if available. The Phomemo firmware
        // pushes status bytes here (paper out, head temperature, print
        // job acknowledgements). Some models also require a subscriber
        // to be present before processing writes at all.
        if let notify = foundNotify {
            notifyCharacteristic = notify
            diagnostics.notifyCharUUID = notify.uuid.uuidString
            peripheral.setNotifyValue(true, for: notify)
            diagnostics.notificationsSubscribed = true
            diagnostics.append("Notify char: \(notify.uuid.uuidString)")
        } else {
            diagnostics.append("No notify channel available.")
        }

        savedPrinterID = peripheral.identifier
        retainPeripheral(peripheral, name: name, isLikelyPhomemo: true)
        state = .ready(name: name)
        diagnostics.append("Ready.")
    }

    /// Whether a characteristic supports the kind of write we use for
    /// the raster payload. We prefer `.write` (with response) so chunked
    /// flow control works, but `.writeWithoutResponse` is acceptable.
    private func writable(_ c: CBCharacteristic) -> Bool {
        c.properties.contains(.write) || c.properties.contains(.writeWithoutResponse)
    }

    private func discoverCharacteristics(for svc: CBService,
                                          on peripheral: CBPeripheral)
                                          async throws -> [CBCharacteristic] {
        try await withCheckedThrowingContinuation { (cont: CheckedContinuation<[CBCharacteristic], Error>) in
            characteristicsContinuation = cont
            peripheral.discoverCharacteristics(nil, for: svc)
        }
    }

    private func ensurePoweredOn() async throws {
        switch central.state {
        case .poweredOn:
            return
        case .unauthorized:
            state = .unauthorized
            throw PhomemoError.bluetoothUnauthorized
        case .poweredOff:
            state = .poweredOff
            throw PhomemoError.bluetoothOff
        case .unsupported:
            throw PhomemoError.bluetoothUnsupported
        default:
            try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
                centralReadyContinuation = cont
            }
        }
    }

    private func writeChunks(_ data: Data,
                             to characteristic: CBCharacteristic,
                             of peripheral: CBPeripheral) async throws {
        let writeWithResponse = characteristic.properties.contains(.write)
        let writeType: CBCharacteristicWriteType = writeWithResponse ? .withResponse : .withoutResponse
        let chunkSize = min(96, max(20, peripheral.maximumWriteValueLength(for: writeType) - 3))
        diagnostics.bytesTotal = data.count
        diagnostics.bytesSent = 0
        diagnostics.append("Writing \(data.count) bytes…")
        var offset = 0
        while offset < data.count {
            let end = min(offset + chunkSize, data.count)
            let chunk = data.subdata(in: offset..<end)
            if writeWithResponse {
                try await withCheckedThrowingContinuation { (cont: CheckedContinuation<Void, Error>) in
                    writeContinuation = cont
                    peripheral.writeValue(chunk, for: characteristic, type: .withResponse)
                }
                try await Task.sleep(nanoseconds: 8_000_000)
            } else {
                peripheral.writeValue(chunk, for: characteristic, type: .withoutResponse)
                try await Task.sleep(nanoseconds: 25_000_000)
            }
            offset = end
            diagnostics.bytesSent = offset
        }
        diagnostics.append("Wrote \(data.count) bytes OK.")
    }
}

// MARK: - CBCentralManagerDelegate

extension PhomemoPrinterManager: CBCentralManagerDelegate {
    nonisolated func centralManagerDidUpdateState(_ central: CBCentralManager) {
        Task { @MainActor in
            switch central.state {
            case .poweredOn:
                if case .poweredOff = state { state = .idle }
                if let cont = centralReadyContinuation {
                    centralReadyContinuation = nil
                    cont.resume()
                }
            case .poweredOff:
                state = .poweredOff
                centralReadyContinuation?.resume(throwing: PhomemoError.bluetoothOff)
                centralReadyContinuation = nil
            case .unauthorized:
                state = .unauthorized
                centralReadyContinuation?.resume(throwing: PhomemoError.bluetoothUnauthorized)
                centralReadyContinuation = nil
            case .unsupported:
                centralReadyContinuation?.resume(throwing: PhomemoError.bluetoothUnsupported)
                centralReadyContinuation = nil
            default:
                break
            }
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager,
                                    didDiscover peripheral: CBPeripheral,
                                    advertisementData: [String: Any],
                                    rssi RSSI: NSNumber) {
        // Read name first so we can decide whether to surface it.
        let advertisedName = advertisementData[CBAdvertisementDataLocalNameKey] as? String
        let resolvedName = advertisedName?.isEmpty == false
            ? advertisedName!
            : (peripheral.name ?? "")

        // Read advertised services for the Phomemo heuristic — many
        // Phomemo models advertise FF00 in the connectable advertisement
        // even when the name is generic ("BT Printer", "BLE-PRT", etc.).
        let advertisedServices = (advertisementData[CBAdvertisementDataServiceUUIDsKey] as? [CBUUID]) ?? []
        let serviceMatch = advertisedServices.contains { PhomemoUUIDs.candidateServices.contains($0) }
        let nameMatch = PhomemoUUIDs.looksLikePhomemo(name: resolvedName)
        let isLikely = serviceMatch || nameMatch

        // Skip truly anonymous peripherals (no name, no Phomemo service).
        // We'd just be cluttering the list with noise from headphones,
        // smart bulbs, etc. that don't even self-identify.
        if resolvedName.isEmpty && !isLikely { return }

        let displayName = resolvedName.isEmpty ? "Bluetooth printer" : resolvedName

        Task { @MainActor in
            retainPeripheral(peripheral,
                             name: displayName,
                             isLikelyPhomemo: isLikely)
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager,
                                    didConnect peripheral: CBPeripheral) {
        Task { @MainActor in
            connectContinuation?.resume(returning: peripheral)
            connectContinuation = nil
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager,
                                    didFailToConnect peripheral: CBPeripheral,
                                    error: Error?) {
        Task { @MainActor in
            let err = error ?? PhomemoError.connectFailed
            connectContinuation?.resume(throwing: err)
            connectContinuation = nil
            state = .failed(err.localizedDescription)
        }
    }

    nonisolated func centralManager(_ central: CBCentralManager,
                                    didDisconnectPeripheral peripheral: CBPeripheral,
                                    error: Error?) {
        Task { @MainActor in
            if case .ready = state { state = .idle }
            writeCharacteristic = nil
        }
    }
}

// MARK: - CBPeripheralDelegate

extension PhomemoPrinterManager: CBPeripheralDelegate {
    nonisolated func peripheral(_ peripheral: CBPeripheral, didDiscoverServices error: Error?) {
        Task { @MainActor in
            if let error {
                servicesContinuation?.resume(throwing: error)
            } else {
                servicesContinuation?.resume()
            }
            servicesContinuation = nil
        }
    }

    nonisolated func peripheral(_ peripheral: CBPeripheral,
                                didDiscoverCharacteristicsFor service: CBService,
                                error: Error?) {
        Task { @MainActor in
            if let error {
                characteristicsContinuation?.resume(throwing: error)
            } else {
                characteristicsContinuation?.resume(returning: service.characteristics ?? [])
            }
            characteristicsContinuation = nil
        }
    }

    nonisolated func peripheral(_ peripheral: CBPeripheral,
                                didWriteValueFor characteristic: CBCharacteristic,
                                error: Error?) {
        Task { @MainActor in
            if let error {
                writeContinuation?.resume(throwing: error)
            } else {
                writeContinuation?.resume()
            }
            writeContinuation = nil
        }
    }

    /// Notifications from the printer. Phomemo firmware pushes status
    /// bytes here when significant events happen (paper out, cover
    /// open, head over-temp, print buffer ack). We surface the hex in
    /// the diagnostics overlay so the user can tell us what the
    /// printer said when it refused to print.
    nonisolated func peripheral(_ peripheral: CBPeripheral,
                                didUpdateValueFor characteristic: CBCharacteristic,
                                error: Error?) {
        Task { @MainActor in
            guard let data = characteristic.value else { return }
            let hex = data.map { String(format: "%02X", $0) }.joined(separator: " ")
            diagnostics.lastNotification = hex
            diagnostics.append("Notify: \(hex)")
        }
    }
}

// MARK: - UUIDs / heuristics

/// BLE service / characteristic UUIDs across the printer families we
/// support. Phomemo M02 + M110 use the FF00/FF02 pair; generic ESC/POS
/// printers (Munbyn, NETUM, JADENS, etc.) are slightly less consistent
/// — most use FF00/FF02 too, but some use a Nordic UART–style RX/TX
/// pair, and a few use Microchip's SPP-over-BLE bridge. The candidate
/// list covers all three; the service-walk during connect picks whichever
/// one actually has a writable characteristic.
enum PhomemoUUIDs {
    static let candidateServices: [CBUUID] = [
        // Phomemo M02 / M110 / most cheap BLE thermal receipt printers
        CBUUID(string: "FF00"),
        // Some Phomemo + generic ESC/POS variants
        CBUUID(string: "18F0"),
        // Older Phomemo PR02 firmware
        CBUUID(string: "E7810A71-73AE-499D-8C15-FAA9AEF0C3F2"),
        // Nordic UART service — used by some generic BLE printers built
        // on Nordic nRF52-series chipsets
        CBUUID(string: "6E400001-B5A3-F393-E0A9-E50E24DCCA9E"),
        // Microchip "RN4870" BLE-SPP bridge — used by a handful of
        // generic printers that wrap classic SPP firmware in a BLE
        // shell
        CBUUID(string: "49535343-FE7D-4AE5-8FA9-9FAFD205E455"),
    ]
    static let candidateWriteChars: [CBUUID] = [
        CBUUID(string: "FF02"),
        CBUUID(string: "2AF1"),
        CBUUID(string: "BEF8910B-7BB9-4F8D-9D6E-7C8FE74E27AA"),
        // Nordic UART RX (we WRITE to the peripheral's RX)
        CBUUID(string: "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"),
        // Microchip RN4870 transparent UART
        CBUUID(string: "49535343-8841-43F4-A8D4-ECBE34729BB3"),
    ]

    /// Heuristic — checks the advertised name against known printer-
    /// model conventions. Hits Phomemo M02/M110 families, plus the
    /// common cheap-ESC/POS-printer name prefixes (Munbyn, NETUM,
    /// JADENS, GOOJPRT, MTP, PT, generic "Printer" labels). Returns
    /// false for empty names; the picker's "Show all devices" toggle
    /// still surfaces unmatched names so even a fully no-name OEM
    /// printer can be paired manually.
    static func looksLikePhomemo(name: String) -> Bool {
        let upper = name.uppercased()
        if upper.isEmpty { return false }
        let needles = [
            // Phomemo
            "PHOMEMO",
            "M02", "M03", "M04", "M110", "M120", "M200", "M220",
            "T02", "PR02", "PR-", "P12", "D30", "D35", "Q20",
            // JADENS BT-series (TSPL label printers)
            "JADENS", "BT460", "BT420", "BT203", "BT201", "BT-",
            "JD-",  // some JADENS BLE modules advertise with this prefix
            // Generic / common cheap BLE thermal printers
            "MUNBYN", "NETUM", "GOOJPRT", "RONGTA", "POS-MATE",
            "MPT-", "MTP-", "BIXOLON", "POS58", "POS80",
            // Generic name patterns
            "PRINTER",   // "BT Printer", "BLE-Printer"
            "PRT",       // "PRT-XXXX"
            "PT-",       // "PT-201", "PT-210" cheap models
        ]
        return needles.contains { upper.contains($0) }
    }
}

// MARK: - Errors

enum PhomemoError: LocalizedError {
    case bluetoothOff
    case bluetoothUnauthorized
    case bluetoothUnsupported
    case peripheralNotFound
    case noSavedPrinter
    case connectFailed
    case serviceNotFound
    case characteristicNotFound
    case notConnected
    case busyPrinting
    case rasterEncodingFailed

    var errorDescription: String? {
        switch self {
        case .bluetoothOff:
            return "Bluetooth is off. Turn it on in Control Center, then try again."
        case .bluetoothUnauthorized:
            return "YardHarvest doesn't have Bluetooth permission. Enable it in Settings → YardHarvest."
        case .bluetoothUnsupported:
            return "This device doesn't support Bluetooth LE."
        case .busyPrinting:
            return "A print job is already in progress — wait for it to finish."
        case .peripheralNotFound:
            return "Couldn't find that printer. Make sure it's powered on and in range."
        case .noSavedPrinter:
            return "No printer paired yet."
        case .connectFailed:
            return "Couldn't connect to the printer."
        case .serviceNotFound:
            return "Connected, but the printer didn't expose any services. Power-cycle the printer and try again."
        case .characteristicNotFound:
            return "Couldn't find a writable channel on this printer. It might be a model we don't speak yet — tell us the exact model and we'll add support."
        case .notConnected:
            return "Not connected to a printer."
        case .rasterEncodingFailed:
            return "Couldn't convert the label to a printable bitmap."
        }
    }
}

// MARK: - Raster encoder

/// Converts a `UIImage` to the Phomemo M02 family's wire format.
///
/// Wire format (small ESC/POS dialect):
///
///   ESC @                  → init printer (1B 40)
///   1F 11 02               → vendor "begin print" magic (M02 family)
///   1F 11 09               → quality command
///   1F 11 11               → density command
///   GS v 0 0               → raster bitmap start (1D 76 30 00)
///   widthBytes (LE u16)    → bytes per row (image_width / 8)
///   heightPixels (LE u16)  → row count
///   <raster data>          → 1-bit packed pixels, MSB-first, row-major
///   1B 4A NN               → feed paper NN dots (0x80 ≈ 16mm)
///
/// The image is rendered onto a square white canvas the print head's
/// width, then thresholded to 1-bit. Caller's QR + caption fits because
/// the compositor already targets 384px.
enum PhomemoRaster {

    struct Raster {
        let width: Int        // pixels (multiple of 8)
        let height: Int
        let data: Data
    }

    static func encode(image: UIImage, width: Int) -> Raster {
        let widthBytes = (width + 7) / 8
        let widthPixels = widthBytes * 8
        let srcSize = image.size
        let scale = CGFloat(widthPixels) / max(srcSize.width, 1)
        let scaledHeight = max(1, Int((srcSize.height * scale).rounded()))
        let canvasSize = CGSize(width: widthPixels, height: scaledHeight)

        let renderer = UIGraphicsImageRenderer(size: canvasSize, format: {
            let f = UIGraphicsImageRendererFormat()
            f.scale = 1
            f.opaque = true
            return f
        }())
        let rendered = renderer.image { ctx in
            UIColor.white.setFill()
            ctx.fill(CGRect(origin: .zero, size: canvasSize))
            image.draw(in: CGRect(origin: .zero, size: canvasSize))
        }

        guard let cg = rendered.cgImage else {
            return Raster(width: widthPixels, height: 0, data: Data())
        }
        let colorSpace = CGColorSpaceCreateDeviceGray()
        let bytesPerRow = widthPixels
        var greyPixels = [UInt8](repeating: 0, count: widthPixels * scaledHeight)
        guard let ctx = CGContext(
            data: &greyPixels,
            width: widthPixels,
            height: scaledHeight,
            bitsPerComponent: 8,
            bytesPerRow: bytesPerRow,
            space: colorSpace,
            bitmapInfo: CGImageAlphaInfo.none.rawValue
        ) else {
            return Raster(width: widthPixels, height: 0, data: Data())
        }
        ctx.draw(cg, in: CGRect(origin: .zero, size: canvasSize))

        var packed = Data(count: widthBytes * scaledHeight)
        packed.withUnsafeMutableBytes { (dest: UnsafeMutableRawBufferPointer) in
            guard let base = dest.baseAddress?.assumingMemoryBound(to: UInt8.self) else { return }
            for y in 0..<scaledHeight {
                for xByte in 0..<widthBytes {
                    var byte: UInt8 = 0
                    for bit in 0..<8 {
                        let x = xByte * 8 + bit
                        let grey = greyPixels[y * widthPixels + x]
                        if grey < 128 { byte |= (0x80 >> bit) }
                    }
                    base[y * widthBytes + xByte] = byte
                }
            }
        }
        return Raster(width: widthPixels, height: scaledHeight, data: packed)
    }

    /// Build the full wire-format byte stream for one print job, picking
    /// the model-appropriate command set. Three of the four families
    /// (M02 / M110 / Generic) use binary ESC/POS-derived streams; the
    /// fourth (JADENS) uses ASCII TSPL2.
    static func commandStream(raster: Raster, widthPixels: Int, model: PhomemoModel) -> Data {
        switch model {
        case .m02:     return m02Stream(raster: raster, widthPixels: widthPixels)
        case .m110:    return m110Stream(raster: raster, widthPixels: widthPixels)
        case .generic: return genericESCPOSStream(raster: raster, widthPixels: widthPixels)
        case .jadens:  return jadensTSPLStream(raster: raster, widthPixels: widthPixels)
        }
    }

    /// JADENS BT-series (BT203, BT460, BT420, etc.) speak **TSPL2** —
    /// the same ASCII-based label-printer language used by TSC and
    /// several other commodity label-printer brands. Completely
    /// different family from ESC/POS: setup commands are plain text
    /// terminated with CR/LF, and only the raster payload inside the
    /// BITMAP command is binary. Wire format:
    ///
    /// ```
    /// SIZE 40 mm,30 mm           — physical label dimensions
    /// GAP 2 mm,0 mm              — gap between labels for the sensor
    /// DENSITY 8                  — print darkness 0–15
    /// SPEED 4                    — print speed (3–6 typical)
    /// DIRECTION 0                — feed direction (0 = leading edge first)
    /// REFERENCE 0,0              — origin point on the label
    /// CLS                        — clear print buffer
    /// BITMAP x,y,wb,h,mode,<raw> — width is in BYTES not pixels;
    ///                              raster bytes packed MSB-first,
    ///                              1 = black, 0 = white (matches our
    ///                              encoder); mode 0 = overwrite.
    /// PRINT 1,1                  — fire heating elements + advance
    ///                              the sticker through the peeler.
    /// ```
    ///
    /// Every line except the BITMAP data is terminated with `\r\n`.
    /// The BITMAP command's argument list is terminated by a single
    /// `\r\n` after the binary payload — that boundary is how the
    /// firmware knows where the raster ends. This sequence is documented
    /// in the public TSPL2 spec; JADENS implements the relevant subset.
    private static func jadensTSPLStream(raster: Raster, widthPixels: Int) -> Data {
        let widthBytes = widthPixels / 8
        // Compute label size in mm from the raster. 8 dots/mm at 203
        // DPI. The width comes from the print width parameter (40 mm
        // default for BT203). The height matches the raster height so
        // SIZE + the BITMAP agree — keeps the gap sensor happy.
        let labelWidthMm = max(1, widthPixels / 8)        // 320 px = 40 mm
        let labelHeightMm = max(1, raster.height / 8)     // dynamic

        var bytes = Data()
        func appendASCII(_ s: String) {
            if let d = s.data(using: .ascii) { bytes.append(d) }
        }
        appendASCII("SIZE \(labelWidthMm) mm,\(labelHeightMm) mm\r\n")
        appendASCII("GAP 2 mm,0 mm\r\n")
        appendASCII("DENSITY 8\r\n")
        appendASCII("SPEED 4\r\n")
        appendASCII("DIRECTION 0\r\n")
        appendASCII("REFERENCE 0,0\r\n")
        appendASCII("CLS\r\n")
        // BITMAP — width is in BYTES, binary payload follows the
        // trailing comma immediately (no separator).
        //
        // TSPL's bitmap convention is the INVERSE of ESC/POS: bit 0 =
        // print (black), bit 1 = leave white. The shared raster encoder
        // packs 1 = black for the three ESC/POS-family streams, so every
        // byte must be inverted here. Without this, a label prints as its
        // own negative — and the solid-black test band comes out as a
        // blank feed, which reads as "the printer isn't working" when the
        // printer is doing exactly what it was told.
        appendASCII("BITMAP 0,0,\(widthBytes),\(raster.height),0,")
        bytes.append(Data(raster.data.map { ~$0 }))
        appendASCII("\r\n")
        appendASCII("PRINT 1,1\r\n")
        return bytes
    }

    /// Vanilla ESC/POS for generic 58 mm BLE thermal receipt printers.
    /// This is the M02 stream with the Phomemo-specific `1F 11 08`
    /// flush byte removed and the alignment/line-spacing commands kept
    /// because they're standardized.
    ///
    /// ```
    /// 1B 40                       ESC @     — init printer
    /// 1B 61 01                    ESC a 1   — center align
    /// 1B 33 00                    ESC 3 0   — line spacing = 0
    /// 1D 76 30 00                 GS v 0 0  — raster bit image
    /// xL xH yL yH                              LE dimensions
    /// <raster>                                 1-bit packed pixels
    /// 0A                          LF        — terminates the raster
    ///                                          line so cheap firmwares
    ///                                          flush the buffer
    /// 1B 64 06                    ESC d 6   — feed 6 lines past tear
    /// ```
    ///
    /// On any ESC/POS-compatible thermal printer in the 58 mm category,
    /// `GS v 0 0` fires the heating elements as soon as it receives the
    /// declared payload — no vendor-specific flush command needed. The
    /// trailing `ESC d 6` (or `LF` + `ESC d 6`) gets the paper past the
    /// tear bar so the user can rip off the printed receipt cleanly.
    ///
    /// Tested against the Phomemo M02 raster as a sanity check (the
    /// vendor byte the M02 needs is simply absent — the M02 happily
    /// prints without it on cheaper firmwares; this stream is the safe
    /// common-denominator).
    private static func genericESCPOSStream(raster: Raster, widthPixels: Int) -> Data {
        var bytes = Data()
        bytes.append(contentsOf: [0x1B, 0x40])              // init
        bytes.append(contentsOf: [0x1B, 0x61, 0x01])        // center align
        bytes.append(contentsOf: [0x1B, 0x33, 0x00])        // line spacing 0
        bytes.append(contentsOf: [0x1D, 0x76, 0x30, 0x00])  // GS v 0 0
        let widthBytes = widthPixels / 8
        bytes.append(UInt8(widthBytes & 0xFF))
        bytes.append(UInt8((widthBytes >> 8) & 0xFF))
        bytes.append(UInt8(raster.height & 0xFF))
        bytes.append(UInt8((raster.height >> 8) & 0xFF))
        bytes.append(raster.data)
        bytes.append(0x0A)                                  // LF
        bytes.append(contentsOf: [0x1B, 0x64, 0x06])        // feed 6 lines
        return bytes
    }

    /// M02 / M02S / M02 PRO / T02 / PR02 — 80 mm thermal receipt
    /// printer. Reverse-engineered protocol summary:
    ///
    /// ```
    /// 1B 40                       ESC @       — init
    /// 1B 61 01                    ESC a 1     — center alignment
    /// 1B 33 00                    ESC 3 0     — line spacing = 0
    /// 1D 76 30 00                 GS v 0 0    — raster bit image
    /// xL xH yL yH                              LE dimensions
    /// <raster>
    /// 1F 11 08                                — vendor END-OF-JOB (fires the
    ///                                           heating elements; without
    ///                                           this the buffer never prints)
    /// 0A                          LF          — buffer flush
    /// 1B 64 06                    ESC d 6     — feed 6 lines past tear bar
    /// ```
    private static func m02Stream(raster: Raster, widthPixels: Int) -> Data {
        var bytes = Data()
        bytes.append(contentsOf: [0x1B, 0x40])
        bytes.append(contentsOf: [0x1B, 0x61, 0x01])
        bytes.append(contentsOf: [0x1B, 0x33, 0x00])
        bytes.append(contentsOf: [0x1D, 0x76, 0x30, 0x00])
        let widthBytes = widthPixels / 8
        bytes.append(UInt8(widthBytes & 0xFF))
        bytes.append(UInt8((widthBytes >> 8) & 0xFF))
        bytes.append(UInt8(raster.height & 0xFF))
        bytes.append(UInt8((raster.height >> 8) & 0xFF))
        bytes.append(raster.data)
        bytes.append(contentsOf: [0x1F, 0x11, 0x08])
        bytes.append(0x0A)
        bytes.append(contentsOf: [0x1B, 0x64, 0x06])
        return bytes
    }

    /// M110 / M120 / M200 / M220 / D110 / D11 — 40 mm label printer.
    ///
    /// Honest note: the M110 BLE protocol is poorly documented and
    /// reverse-engineered drivers disagree on the exact bytes. This is
    /// the minimal sequence that most cleanly matches the polskafan /
    /// theacodes / python-phomemo M110 implementations:
    ///
    /// ```
    /// 1B 40                       ESC @     — init
    /// 1F 11 02 04                            — Phomemo "set print mode"
    ///                                          (4-byte command; the
    ///                                          0x04 trailing byte is
    ///                                          required on M110)
    /// 1D 76 30 00 xL xH yL yH    GS v 0 0  — raster bit image
    /// <raster>                              — 1-bit packed, MSB-first
    /// 1F 11 08                              — Phomemo END-OF-JOB
    ///                                          (fires the print head;
    ///                                          M110 needs this AND…)
    /// 1B 4A 60                   ESC J 96   — feed 96 dots (12 mm), so
    ///                                          the label clears the
    ///                                          peeler bar
    /// 0C                          FF        — form feed, the last-
    ///                                          chance kick that some
    ///                                          M110 firmware revs use
    ///                                          to actually advance
    /// ```
    ///
    /// Deliberately omitted: SIZE/GAP/SPEED/DENSITY/REFERENCE/CLS/PRINT
    /// (TSPL ceremony). The M110 binary protocol doesn't speak TSPL;
    /// the printer expects its own vendor commands. Sending TSPL
    /// commands gets you an ignored buffer.
    ///
    /// **Important: label gap calibration must be done before first
    /// print.** Hold the M110's feed button while powering on; the
    /// printer beeps once and feeds 2–3 labels to learn where the gaps
    /// are. Without this, the M110 accepts the print job over BLE but
    /// never fires the heating elements — it doesn't know where the
    /// label is. This is the most common cause of "BLE connects fine
    /// but no print" reports for the M110.
    private static func m110Stream(raster: Raster, widthPixels: Int) -> Data {
        var bytes = Data()
        bytes.append(contentsOf: [0x1B, 0x40])                    // init
        bytes.append(contentsOf: [0x1F, 0x11, 0x02, 0x04])        // print mode
        bytes.append(contentsOf: [0x1D, 0x76, 0x30, 0x00])        // GS v 0 0
        let widthBytes = widthPixels / 8
        bytes.append(UInt8(widthBytes & 0xFF))
        bytes.append(UInt8((widthBytes >> 8) & 0xFF))
        bytes.append(UInt8(raster.height & 0xFF))
        bytes.append(UInt8((raster.height >> 8) & 0xFF))
        bytes.append(raster.data)
        bytes.append(contentsOf: [0x1F, 0x11, 0x08])              // end of job
        bytes.append(contentsOf: [0x1B, 0x4A, 0x60])              // feed 96 dots
        bytes.append(0x0C)                                        // form feed
        return bytes
    }

    /// Tiny self-contained test print — a solid black bar sized
    /// appropriately for the chosen model. Used by the picker UI's
    /// "Print test page" button to verify the protocol layer end-to-end
    /// without needing the QR composer. If this prints but the real
    /// label doesn't → bug in `ToolLabelComposer`. If this doesn't
    /// print → wrong model selected, or wrong characteristic, or
    /// printer needs a different command set.
    static func testPagePayload(widthPixels: Int, model: PhomemoModel) -> Data {
        // JADENS: pure-ASCII TSPL with built-in TEXT — no bitmap at all.
        // This makes the test page a transport bisect: if this prints, the
        // BLE link and TSPL mode are both good and any remaining problem is
        // in the BITMAP path; if it doesn't, the bytes aren't reaching the
        // print engine (wrong characteristic, pacing, or mode).
        if model == .jadens {
            let tspl = """
            SIZE 40 mm,30 mm\r\nGAP 2 mm,0 mm\r\nDENSITY 8\r\nCLS\r\nTEXT 24,40,"3",0,2,2,"YARDHARVEST"\r\nTEXT 24,110,"2",0,1,1,"TSPL test OK"\r\nPRINT 1,1\r\n
            """
            return tspl.data(using: .ascii) ?? Data()
        }
        // Everyone else: solid 100% black band, 64 rows tall.
        let widthBytes = widthPixels / 8
        let height = 64
        var raster = Data(count: widthBytes * height)
        for i in 0..<raster.count { raster[i] = 0xFF }
        let r = Raster(width: widthPixels, height: height, data: raster)
        return commandStream(raster: r, widthPixels: widthPixels, model: model)
    }
}
