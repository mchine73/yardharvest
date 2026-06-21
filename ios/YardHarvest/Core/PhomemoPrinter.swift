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
    /// Generic ESC/POS BLE thermal printer (58 mm). Covers the long tail
    /// of cheap white-label thermal printers — Munbyn, NETUM, JADENS,
    /// GOOJPRT, Rongta, POS-mate, MPT/MTP receipt printers, etc. — that
    /// implement a common ESC/POS subset (`ESC @` + `GS v 0` raster +
    /// `ESC d` feed) and expose `FF00`/`FF02` (or similar) BLE
    /// characteristics. This is the target model for the "ship a printer
    /// with the annual membership" plan: pick whichever 58 mm BLE
    /// receipt printer is cheapest in bulk and ship it; the app just
    /// works because the protocol is the same standardized subset every
    /// vendor in this category implements.
    case generic

    var id: String { rawValue }
    var label: String {
        switch self {
        case .m02:     return "M02"
        case .m110:    return "M110"
        case .generic: return "Generic"
        }
    }

    /// Long form for the help text under the picker.
    var detailedLabel: String {
        switch self {
        case .m02:     return "Phomemo M02 (80 mm receipt)"
        case .m110:    return "Phomemo M110 (40 mm label)"
        case .generic: return "Generic ESC/POS (58 mm receipt)"
        }
    }

    /// Native print head width in pixels. M02 = 80 mm × 8 dpi/mm head.
    /// M110 = 40 mm × 8 dpi/mm. Generic 58 mm thermal printers also use
    /// a 384-dot head (58 mm × 8 dpi/mm minus some bezel).
    var defaultPrintWidth: Int {
        switch self {
        case .m02: return 384
        case .m110: return 320
        case .generic: return 384
        }
    }

    /// Default label height in pixels. M02 + generic use continuous
    /// paper so we match the width for a square label. M110 ships with
    /// 40 × 30 mm labels by default — sized for the most common roll.
    var defaultLabelHeight: Int {
        switch self {
        case .m02: return 384       // square, continuous paper
        case .m110: return 240      // 30 mm × 8 dpi/mm
        case .generic: return 384   // square, continuous paper
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
        diagnostics.append("Connecting…")

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
        var foundWrite: CBCharacteristic?
        var foundNotify: CBCharacteristic?
        let orderedServices = services.sorted {
            PhomemoUUIDs.candidateServices.contains($0.uuid)
                && !PhomemoUUIDs.candidateServices.contains($1.uuid)
        }
        for svc in orderedServices {
            let chars = try await discoverCharacteristics(for: svc, on: peripheral)
            for c in chars {
                if foundWrite == nil, writable(c) {
                    if PhomemoUUIDs.candidateWriteChars.contains(c.uuid) {
                        foundWrite = c
                        diagnostics.serviceUUID = svc.uuid.uuidString
                    } else if foundWrite == nil {
                        foundWrite = c
                    }
                }
                if foundNotify == nil, c.properties.contains(.notify) {
                    foundNotify = c
                }
            }
            if foundWrite != nil { break }
        }
        guard let writeChar = foundWrite else {
            throw PhomemoError.characteristicNotFound
        }
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
            // Generic / common cheap BLE thermal printers
            "MUNBYN", "NETUM", "JADENS", "GOOJPRT", "RONGTA", "POS-MATE",
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
    case rasterEncodingFailed

    var errorDescription: String? {
        switch self {
        case .bluetoothOff:
            return "Bluetooth is off. Turn it on in Control Center, then try again."
        case .bluetoothUnauthorized:
            return "YardHarvest doesn't have Bluetooth permission. Enable it in Settings → YardHarvest."
        case .bluetoothUnsupported:
            return "This device doesn't support Bluetooth LE."
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
    /// the model-appropriate command set. All three families share the
    /// `GS v 0 0` raster header but everything around it differs.
    static func commandStream(raster: Raster, widthPixels: Int, model: PhomemoModel) -> Data {
        switch model {
        case .m02:     return m02Stream(raster: raster, widthPixels: widthPixels)
        case .m110:    return m110Stream(raster: raster, widthPixels: widthPixels)
        case .generic: return genericESCPOSStream(raster: raster, widthPixels: widthPixels)
        }
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
        // Solid 100% black band, 64 rows tall.
        let widthBytes = widthPixels / 8
        let height = 64
        var raster = Data(count: widthBytes * height)
        for i in 0..<raster.count { raster[i] = 0xFF }
        let r = Raster(width: widthPixels, height: height, data: raster)
        return commandStream(raster: r, widthPixels: widthPixels, model: model)
    }
}
