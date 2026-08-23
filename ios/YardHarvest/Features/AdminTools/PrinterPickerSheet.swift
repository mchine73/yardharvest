import SwiftUI

/// One-time printer pairing UI. Scans for nearby Phomemo printers and lets
/// the admin pick one. The chosen printer is persisted so subsequent prints
/// auto-reconnect without showing this sheet again.
struct PrinterPickerSheet: View {
    @Environment(\.dismiss) private var dismiss
    let printer: PhomemoPrinterManager
    var onPaired: () -> Void

    @State private var connectingID: UUID?
    @State private var testPrintStatus: String?
    @State private var testPrintError: String?
    @State private var isTestPrinting = false
    @State private var isSweeping = false

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.md) {
                    heroBand
                    filterToggle
                    if case .scanning = printer.state, printer.discovered.isEmpty {
                        scanningCard
                    } else if printer.discovered.isEmpty {
                        idleCard
                    }
                    ForEach(printer.discovered) { p in
                        printerRow(p)
                    }
                    if case .scanning = printer.state, !printer.discovered.isEmpty {
                        scanningFooter
                    }
                    if isConnected {
                        testPrintCard
                    }
                    statusFooter
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("Pair Printer")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Close") { dismiss() } }
                ToolbarItem(placement: .topBarTrailing) {
                    if isConnected {
                        Button("Done") { dismiss() }
                            .font(.system(size: 16, weight: .semibold))
                    } else {
                        Button("Scan") { Task { try? await printer.startScan() } }
                            .disabled(isScanning)
                    }
                }
            }
            .task {
                try? await printer.startScan()
            }
            .onDisappear {
                printer.stopScan()
            }
        }
    }

    /// Toggle so the user can opt into seeing every named BLE device if
    /// their printer broadcasts something the Phomemo heuristic doesn't
    /// catch.
    private var filterToggle: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                modelPicker
                Divider().overlay(YH.border)
                Toggle(isOn: Binding(
                    get: { printer.showAllDevices },
                    set: { printer.showAllDevices = $0 }
                )) {
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Show all Bluetooth devices")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text(printer.showAllDevices
                             ? "Showing every nearby BLE device. Phomemo-recognized ones are tagged."
                             : "Only printers we recognize. Flip on if yours isn't appearing.")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
                .tint(YH.ink)
            }
        }
    }

    /// Lets the user pick which printer family they're connecting to.
    /// Three options:
    ///   • M110 — Phomemo 40 mm label printer (the YardHarvest default)
    ///   • M02 — Phomemo 80 mm thermal receipt printer
    ///   • Generic — any cheap ESC/POS BLE thermal printer (the target
    ///     for the "free printer with annual membership" bundle)
    /// They speak different command sets, so the wrong pick = connects
    /// but prints blank.
    private var modelPicker: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("PRINTER MODEL")
                .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
            Picker("Model", selection: Binding(
                get: { printer.model },
                set: { printer.model = $0 }
            )) {
                ForEach(PhomemoModel.allCases) { m in
                    Text(m.label).tag(m)
                }
            }
            .pickerStyle(.segmented)
            Text(modelPickerHelpText)
                .font(.yhCaption).foregroundStyle(YH.muted)
        }
    }

    private var modelPickerHelpText: String {
        switch printer.model {
        case .m110:
            return "Phomemo M110 — 40 mm labels with a peeler. Needs label-gap calibration before first print (see below)."
        case .m02:
            return "Phomemo M02 — 80 mm thermal receipt printer."
        case .generic:
            return "Any cheap 58 mm BLE thermal receipt printer that speaks ESC/POS — Munbyn, NETUM, GOOJPRT, Rongta, MTP/MPT receipt models, etc. Continuous paper; no label-gap calibration needed."
        case .jadens:
            return "JADENS BT-series sticker printer (BT203 / BT460 / BT420). Speaks TSPL — defaults to 40 × 30 mm sticker rolls, the most common JADENS ships."
        }
    }

    private var scanningFooter: some View {
        HStack(spacing: 8) {
            ProgressView().scaleEffect(0.85)
            Text("Still scanning…").font(.yhCaption).foregroundStyle(YH.muted)
        }
    }

    private var heroBand: some View {
        YHBand(tint: .lime) {
            VStack(alignment: .leading, spacing: 6) {
                Text("PHOMEMO").font(.yhCaptionMed).tracking(0.8)
                Text("Pair your label printer.")
                    .font(.system(size: 22, weight: .bold)).tracking(-0.4)
                Text("Power on the printer, hold it within a few feet of this iPhone, and pick it from the list below. We'll remember it for next time.")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.ink.opacity(0.75))
                    .padding(.top, 2)
            }
        }
    }

    @ViewBuilder
    private func printerRow(_ p: PhomemoPrinterManager.DiscoveredPrinter) -> some View {
        Button {
            Haptics.tap()
            Task { await pair(p) }
        } label: {
            HStack(spacing: 12) {
                YHIconTile(systemImage: "printer.fill", size: 40,
                           background: p.isLikelyPhomemo ? YH.lime : YH.surface)
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 6) {
                        Text(p.name.isEmpty ? "Bluetooth printer" : p.name)
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if p.isLikelyPhomemo {
                            Text("Phomemo")
                                .font(.system(size: 10, weight: .bold))
                                .foregroundStyle(YH.ink)
                                .padding(.horizontal, 6).padding(.vertical, 2)
                                .background(YH.lime)
                                .clipShape(Capsule())
                        }
                    }
                    Text(p.id.uuidString.prefix(8).lowercased())
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(YH.muted)
                }
                Spacer()
                if connectingID == p.id {
                    ProgressView()
                } else {
                    Image(systemName: "chevron.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
            }
            .padding(YH.Space.md)
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
        .buttonStyle(.plain)
        .disabled(connectingID != nil)
    }

    private var scanningCard: some View {
        YHCard {
            HStack(spacing: 12) {
                ProgressView()
                Text("Scanning for nearby printers…")
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.muted)
            }
        }
    }

    private var idleCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Label("No printers yet", systemImage: "wifi.slash")
                    .font(.yhBodyMedium).foregroundStyle(YH.ink)
                Text("Tap Scan in the top-right to look again. Phomemo printers usually advertise as M02, M02 PRO, T02, or similar.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }

    @ViewBuilder
    private var statusFooter: some View {
        switch printer.state {
        case .failed(let msg):
            YHCard {
                Text(msg).font(.yhSubheadline).foregroundStyle(YH.danger)
            }
        case .poweredOff:
            YHCard {
                Text("Bluetooth is off. Enable it in Control Center to find your printer.")
                    .font(.yhSubheadline).foregroundStyle(YH.warning)
            }
        case .unauthorized:
            YHCard {
                Text("YardHarvest needs Bluetooth permission. Enable it in Settings → YardHarvest → Bluetooth.")
                    .font(.yhSubheadline).foregroundStyle(YH.warning)
            }
        default:
            EmptyView()
        }
    }

    private var isScanning: Bool {
        if case .scanning = printer.state { return true }
        return false
    }

    private var isConnected: Bool {
        if case .ready = printer.state { return true }
        return false
    }

    /// Shows up after pair succeeds. Prints a tiny black bar so we can
    /// tell whether the protocol byte stream actually fires the heating
    /// elements. If THIS prints but the QR label doesn't, the bug is in
    /// the compositor; if THIS doesn't print, it's the protocol or the
    /// printer needs calibration.
    private var testPrintCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                Label("Test print", systemImage: "checkmark.seal.fill")
                    .font(.yhBodyMedium).foregroundStyle(YH.ink)
                if printer.model == .m110 {
                    calibrationCallout
                }
                Text("Prints a small black bar to verify the connection drives the heating elements. If nothing comes out, see Diagnostics below — that'll tell us where it's failing.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
                YHButton(title: "Print test page",
                         systemImage: "printer.dotmatrix.fill",
                         style: .dark,
                         isLoading: isTestPrinting) {
                    Task { await runTestPrint() }
                }
                // Escalation for a silent printer: try every dialect and let
                // the paper say which one the board speaks.
                YHButton(title: "Try every protocol",
                         systemImage: "questionmark.bubble",
                         style: .ghost,
                         isLoading: isSweeping) {
                    Task { await runSweep() }
                }
                if let testPrintStatus {
                    Text(testPrintStatus).font(.yhCaption).foregroundStyle(YH.ink)
                }
                if let testPrintError {
                    Text(testPrintError).font(.yhCaption).foregroundStyle(YH.danger)
                }
                diagnosticsBlock
            }
        }
    }

    /// Critical first-time-setup note for M110 owners. The single most
    /// common cause of "connects but doesn't print" is that the printer
    /// has never been calibrated for the label gap, so the firmware
    /// accepts data but can't decide when to fire.
    private var calibrationCallout: some View {
        VStack(alignment: .leading, spacing: 4) {
            Label("Calibrate the label gap first", systemImage: "exclamationmark.triangle.fill")
                .font(.yhCaptionMed)
                .foregroundStyle(YH.warning)
            Text("If you haven't already: power-cycle the M110 while HOLDING the feed button until it beeps and feeds 2–3 labels. That teaches it where the gaps are. Without this it accepts data over Bluetooth but never fires.")
                .font(.yhCaption).foregroundStyle(YH.muted)
        }
        .padding(8)
        .background(YH.warning.opacity(0.08))
        .clipShape(RoundedRectangle(cornerRadius: 8))
    }

    /// Read-only diagnostics surface. Tells us — and you — exactly what
    /// the BLE handshake produced. When you say "still doesn't print",
    /// paste me what's in this card and I can pinpoint the layer.
    private var diagnosticsBlock: some View {
        let d = printer.diagnostics
        return VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text("DIAGNOSTICS")
                    .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                Spacer()
                // One tap puts the whole handshake on the clipboard —
                // "paste me the diagnostics" should never require
                // transcribing hex off a phone screen.
                Button {
                    UIPasteboard.general.string = diagnosticsExport(d)
                    Haptics.tap()
                } label: {
                    Label("Copy", systemImage: "doc.on.doc")
                        .font(.yhCaption)
                        .foregroundStyle(YH.ink)
                }
            }
            diagRow("Service", d.serviceUUID ?? "—")
            diagRow("Write char", d.writeCharUUID ?? "—")
            diagRow("Write modes",
                    [d.supportsWrite ? "with-response" : nil,
                     d.supportsWriteWithoutResponse ? "without-response" : nil]
                        .compactMap { $0 }.joined(separator: " + "))
            diagRow("Notify char", d.notifyCharUUID ?? "(none)")
            diagRow("Notify subscribed", d.notificationsSubscribed ? "yes" : "no")
            if d.bytesTotal > 0 {
                diagRow("Bytes sent", "\(d.bytesSent) / \(d.bytesTotal)")
            }
            if let last = d.lastNotification {
                diagRow("Last reply", last)
            }
            if !d.log.isEmpty {
                Text("LOG").font(.yhCaptionMed).tracking(0.6)
                    .foregroundStyle(YH.muted).padding(.top, 4)
                ForEach(Array(d.log.enumerated()), id: \.offset) { _, line in
                    Text("• \(line)")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(YH.muted)
                }
            }
        }
        .padding(.top, 4)
    }

    private func diagnosticsExport(_ d: PhomemoPrinterManager.PrinterDiagnostics) -> String {
        var lines: [String] = []
        lines.append("YardHarvest printer diagnostics")
        lines.append("model: \(printer.model.detailedLabel)")
        lines.append("service: \(d.serviceUUID ?? "—")")
        lines.append("writeChar: \(d.writeCharUUID ?? "—") (write=\(d.supportsWrite) writeNR=\(d.supportsWriteWithoutResponse))")
        lines.append("notifyChar: \(d.notifyCharUUID ?? "none") subscribed=\(d.notificationsSubscribed)")
        lines.append("bytes: \(d.bytesSent)/\(d.bytesTotal)")
        if let last = d.lastNotification { lines.append("lastReply: \(last)") }
        lines.append("log:")
        lines.append(contentsOf: d.log.map { "  \($0)" })
        return lines.joined(separator: "\n")
    }

    private func diagRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Text(label).font(.yhCaption).foregroundStyle(YH.muted)
                .frame(width: 110, alignment: .leading)
            Text(value)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(YH.ink)
                .lineLimit(2)
                .truncationMode(.middle)
            Spacer()
        }
    }

    private func runSweep() async {
        testPrintStatus = nil
        testPrintError = nil
        isSweeping = true
        defer { isSweeping = false }
        do {
            try await printer.runProtocolSweep()
            testPrintStatus = "Sweep done — 4 jobs sent, ~3s apart: 1 TSPL text, "
                + "2 short band, 3 TALL band, 4 medium band. Whichever printed, "
                + "pick that model above: text→JADENS, short→M02, tall→M110, medium→Generic."
            Haptics.success()
        } catch {
            testPrintError = error.localizedDescription
            Haptics.error()
        }
    }

    private func runTestPrint() async {
        testPrintStatus = nil
        testPrintError = nil
        isTestPrinting = true
        defer { isTestPrinting = false }
        do {
            try await printer.printTestPage()
            testPrintStatus = "Test page sent. Did a black bar come out?"
            Haptics.success()
        } catch {
            testPrintError = error.localizedDescription
            Haptics.error()
        }
    }

    private func pair(_ p: PhomemoPrinterManager.DiscoveredPrinter) async {
        connectingID = p.id
        defer { connectingID = nil }
        do {
            try await printer.connect(p)
            Haptics.success()
            onPaired()
            // Don't auto-dismiss — the test-print card now appears and
            // the admin should verify the protocol works before moving
            // on. They tap Done (added below) when satisfied.
        } catch {
            Haptics.error()
        }
    }
}
