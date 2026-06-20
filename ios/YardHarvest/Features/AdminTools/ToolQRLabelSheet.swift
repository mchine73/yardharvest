import SwiftUI
import CoreImage.CIFilterBuiltins
import UIKit

/// Renders a printable QR-code label for one tool and drives the native
/// Phomemo print flow. Used from `AdminToolsView` after the admin taps
/// "Print QR" on a row. The QR encodes the resource's full scannable URL
/// (`qrCodeURL`), so any QR-aware app — including our own scanner and the
/// system Camera (via universal links) — drops the gardener into the
/// checkout flow when they scan it.
struct ToolQRLabelSheet: View {
    let garden: Garden
    let resource: GardenResource

    @Environment(\.dismiss) private var dismiss
    @State private var printer = PhomemoPrinterManager()
    @State private var showingPicker = false
    @State private var statusMessage: String?
    @State private var errorMessage: String?
    @State private var isPrinting = false

    /// The composed label image shown in the preview AND sent to the
    /// printer. Cached so we render it once.
    @State private var labelImage: UIImage?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: YH.Space.md) {
                    previewCard
                    detailsCard
                    statusCard
                    actionButtons
                    helpCard
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("Print Label")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Close") { dismiss() } }
            }
            .task {
                // Compose at the printer's native head width AND label
                // height so M110's 40 × 30 mm sticker fits exactly
                // (320 × 240 px). M02 stays square (384 × 384 px) since
                // it's continuous paper.
                let width = CGFloat(printer.model.defaultPrintWidth)
                let height = CGFloat(printer.model.defaultLabelHeight)
                labelImage = ToolLabelComposer.compose(
                    toolName: resource.name,
                    gardenName: garden.name,
                    qrPayload: resource.qrCodeURL ?? resource.qrCodeToken ?? "",
                    canvasSize: CGSize(width: width, height: height))
            }
            .sheet(isPresented: $showingPicker) {
                PrinterPickerSheet(printer: printer) {
                    Task { await printAfterPairing() }
                }
            }
        }
    }

    // MARK: - Sections

    private var previewCard: some View {
        YHCard {
            VStack(spacing: YH.Space.sm) {
                if let img = labelImage {
                    Image(uiImage: img)
                        .resizable()
                        .interpolation(.high)
                        .scaledToFit()
                        .frame(maxWidth: 240)
                        .padding(8)
                        .background(Color.white)
                        .overlay(RoundedRectangle(cornerRadius: 8)
                                    .strokeBorder(YH.border))
                        .clipShape(RoundedRectangle(cornerRadius: 8))
                } else {
                    ProgressView().frame(height: 240)
                }
                Text("Preview")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
            .frame(maxWidth: .infinity)
        }
    }

    private var detailsCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Text("TOOL").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                Text(resource.name).font(.yhTitle3).foregroundStyle(YH.ink)
                if let type = resource.resourceType {
                    Text(type.capitalized).font(.yhCaption).foregroundStyle(YH.muted)
                }
                Divider().overlay(YH.border).padding(.vertical, 4)
                Text("ENCODES").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                Text(resource.qrCodeURL ?? resource.qrCodeToken ?? "—")
                    .font(.system(size: 11, design: .monospaced))
                    .foregroundStyle(YH.muted)
                    .lineLimit(2)
                    .truncationMode(.middle)
            }
        }
    }

    @ViewBuilder
    private var statusCard: some View {
        switch printer.state {
        case .ready(let name):
            YHCard {
                HStack {
                    YHIconTile(systemImage: "printer.fill",
                               background: YH.lime, foreground: YH.ink)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("Connected").font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text(name).font(.yhCaption).foregroundStyle(YH.muted)
                    }
                    Spacer()
                }
            }
        case .printing:
            YHBand(tint: .lime) {
                HStack(spacing: 12) {
                    ProgressView()
                    Text("Printing…").font(.yhBodyMedium).foregroundStyle(YH.ink)
                }
            }
        case .connecting(let name):
            YHCard {
                HStack(spacing: 12) {
                    ProgressView()
                    Text("Connecting to \(name)…")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
            }
        case .failed(let msg):
            YHCard {
                Label(msg, systemImage: "exclamationmark.triangle.fill")
                    .font(.yhSubheadline).foregroundStyle(YH.danger)
            }
        case .poweredOff:
            YHCard {
                Label("Turn on Bluetooth to print.",
                      systemImage: "antenna.radiowaves.left.and.right.slash")
                    .font(.yhSubheadline).foregroundStyle(YH.warning)
            }
        case .unauthorized:
            YHCard {
                Label("Enable Bluetooth permission in Settings → YardHarvest.",
                      systemImage: "hand.raised.fill")
                    .font(.yhSubheadline).foregroundStyle(YH.warning)
            }
        default:
            EmptyView()
        }
    }

    @ViewBuilder
    private var actionButtons: some View {
        VStack(spacing: YH.Space.sm) {
            if !hasScannablePayload {
                emptyPayloadWarning
            }
            YHButton(title: primaryButtonTitle,
                     systemImage: "printer.fill",
                     style: .lime,
                     isLoading: isPrinting) {
                Task { await primaryAction() }
            }
            .disabled(labelImage == nil || isPrinting || !hasScannablePayload)
            YHButton(title: "Pair a different printer",
                     systemImage: "arrow.triangle.2.circlepath",
                     style: .ghost) {
                printer.disconnect()
                showingPicker = true
            }
        }
        if let errorMessage {
            Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
        }
        if let statusMessage {
            Text(statusMessage).font(.yhSubheadline).foregroundStyle(YH.ink)
        }
    }

    private var helpCard: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Label("How it works", systemImage: "info.circle")
                    .font(.yhCaptionMed).foregroundStyle(YH.muted)
                Text("YardHarvest talks to your Phomemo printer directly over Bluetooth — no third-party app required. The QR encodes a yardharvest.app link that scans into the checkout flow on any device. Pair the printer once; we'll remember it for future labels.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }

    // MARK: - Empty-payload guard

    /// Returns true if the resource has anything scannable to encode in
    /// the QR. Defends against the case where the backend hasn't been
    /// redeployed with `qr_code_token` / `qr_code_url` in the response —
    /// without this guard we'd happily print a label whose QR decodes
    /// to an empty string, then the scanner would 400 with "token
    /// parameter is required".
    private var hasScannablePayload: Bool {
        let url = (resource.qrCodeURL ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        let token = (resource.qrCodeToken ?? "").trimmingCharacters(in: .whitespacesAndNewlines)
        return !url.isEmpty || !token.isEmpty
    }

    private var emptyPayloadWarning: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 4) {
                Label("Can't print yet", systemImage: "exclamationmark.triangle.fill")
                    .font(.yhBodyMedium).foregroundStyle(YH.danger)
                Text("This tool has no QR token from the backend. Redeploy the YardHarvest backend so the resource API returns qr_code_url + qr_code_token, then come back here.")
                    .font(.yhCaption).foregroundStyle(YH.muted)
            }
        }
    }

    // MARK: - Actions

    private var primaryButtonTitle: String {
        if printer.savedPrinterID == nil { return "Pair Printer & Print" }
        switch printer.state {
        case .ready: return "Print Label"
        case .printing: return "Printing…"
        default: return "Print Label"
        }
    }

    private func primaryAction() async {
        errorMessage = nil
        statusMessage = nil
        if printer.savedPrinterID == nil {
            showingPicker = true
            return
        }
        await ensureConnectedAndPrint()
    }

    private func printAfterPairing() async {
        // Called after the picker successfully paired. The printer is
        // already in `.ready` state, so we go straight to print.
        await ensureConnectedAndPrint()
    }

    private func ensureConnectedAndPrint() async {
        // Reconnect to the saved printer if we lost it (e.g. the device
        // slept between sessions). If reconnect fails, surface the picker.
        if case .ready = printer.state {
            // already connected
        } else {
            do { try await printer.reconnectSaved() }
            catch {
                errorMessage = error.localizedDescription
                showingPicker = true
                return
            }
        }
        guard let img = labelImage else {
            errorMessage = "Label hasn't rendered yet — try again."
            return
        }
        isPrinting = true
        defer { isPrinting = false }
        do {
            try await printer.printImage(img)
            statusMessage = "Sent to printer."
            Haptics.success()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}

// MARK: - Label compositor

/// Composes a print-ready label image: a high-density QR centered with the
/// tool name and garden name underneath. Rendered as a square so it fits
/// the M02-family's 50mm continuous thermal label nicely.
enum ToolLabelComposer {
    static func compose(toolName: String,
                        gardenName: String,
                        qrPayload: String,
                        canvasSize: CGSize = CGSize(width: 384, height: 384)) -> UIImage? {
        // Adaptive layout: short labels (M110 40×30 mm = 320×240 px) use
        // a compact stack — small title, big QR, small footer. Taller
        // labels (M02 continuous) use the expanded layout with room for
        // both the garden name and the "Scan to check out" hint.
        let isShortLabel = canvasSize.height < canvasSize.width * 0.85

        // Sizes adapt to canvas height so neither overflows nor leaves a
        // huge empty band at the bottom.
        let titleHeight: CGFloat = isShortLabel ? 26 : 36
        let footerHeight: CGFloat = isShortLabel ? 20 : 24
        let hintHeight: CGFloat = isShortLabel ? 0 : 20
        let topPadding: CGFloat = 6
        let bottomPadding: CGFloat = isShortLabel ? 4 : 8
        let gap: CGFloat = 4

        // QR is the centerpiece — give it whatever's left after title +
        // footer + paddings, but stay square and constrained by width.
        let verticalConsumed = topPadding + titleHeight + gap + footerHeight
            + (hintHeight > 0 ? gap + hintHeight : 0) + bottomPadding
        let availableHeight = max(40, canvasSize.height - verticalConsumed)
        let qrSide = min(canvasSize.width * 0.92, availableHeight)

        guard let qr = makeQR(payload: qrPayload, targetSide: Int(qrSide)) else {
            return nil
        }
        let format = UIGraphicsImageRendererFormat()
        format.scale = 1
        format.opaque = true
        let renderer = UIGraphicsImageRenderer(size: canvasSize, format: format)
        return renderer.image { _ in
            UIColor.white.setFill()
            UIRectFill(CGRect(origin: .zero, size: canvasSize))

            // Title (tool name) — bold, centered, single line truncated.
            let nameAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: isShortLabel ? 20 : 28, weight: .bold),
                .foregroundColor: UIColor.black,
                .paragraphStyle: centeredParagraph()
            ]
            let nameRect = CGRect(x: 6, y: topPadding,
                                  width: canvasSize.width - 12,
                                  height: titleHeight)
            (toolName as NSString).draw(in: nameRect, withAttributes: nameAttrs)

            // QR centered horizontally, just below the title.
            let qrY = topPadding + titleHeight + gap
            let qrRect = CGRect(x: (canvasSize.width - qrSide) / 2,
                                y: qrY,
                                width: qrSide,
                                height: qrSide)
            qr.draw(in: qrRect)

            // Footer — garden name (always shown). Hint line only shown
            // on tall labels where there's room without crowding the QR.
            let footerAttrs: [NSAttributedString.Key: Any] = [
                .font: UIFont.systemFont(ofSize: isShortLabel ? 14 : 18, weight: .medium),
                .foregroundColor: UIColor.black,
                .paragraphStyle: centeredParagraph()
            ]
            let footerY = qrRect.maxY + gap
            let footerRect = CGRect(x: 6, y: footerY,
                                    width: canvasSize.width - 12,
                                    height: footerHeight)
            (gardenName as NSString).draw(in: footerRect, withAttributes: footerAttrs)

            if hintHeight > 0 {
                let hintAttrs: [NSAttributedString.Key: Any] = [
                    .font: UIFont.systemFont(ofSize: 13, weight: .regular),
                    .foregroundColor: UIColor.darkGray,
                    .paragraphStyle: centeredParagraph()
                ]
                let hintRect = CGRect(x: 6, y: footerY + footerHeight + 2,
                                      width: canvasSize.width - 12,
                                      height: hintHeight)
                ("Scan to check out" as NSString).draw(in: hintRect, withAttributes: hintAttrs)
            }
        }
    }

    /// Generate a crisp, scannable QR at the requested side length in
    /// pixels. We use Core Image's built-in generator at error-correction
    /// level H (most robust) so labels survive being scuffed or curled.
    private static func makeQR(payload: String, targetSide: Int) -> UIImage? {
        let filter = CIFilter.qrCodeGenerator()
        filter.message = Data(payload.utf8)
        filter.correctionLevel = "H"
        guard let output = filter.outputImage else { return nil }

        // The filter produces a tiny image — scale up by an integer factor
        // so the modules stay pixel-aligned (avoid blurry edges).
        let nativeSide = max(1, output.extent.width)
        let scale = max(1, CGFloat(targetSide) / nativeSide)
        let scaled = output.transformed(by: CGAffineTransform(scaleX: scale, y: scale))

        let context = CIContext(options: nil)
        guard let cg = context.createCGImage(scaled, from: scaled.extent) else {
            return nil
        }
        return UIImage(cgImage: cg)
    }

    private static func centeredParagraph() -> NSParagraphStyle {
        let p = NSMutableParagraphStyle()
        p.alignment = .center
        p.lineBreakMode = .byTruncatingTail
        return p
    }
}
