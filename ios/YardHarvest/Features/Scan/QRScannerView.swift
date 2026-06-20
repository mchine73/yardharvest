import SwiftUI
import AVFoundation
import UIKit

/// Live camera QR scanner — UIViewControllerRepresentable around an
/// AVCaptureSession. Fires `onCode` exactly once with the decoded string
/// then stops the session.
struct QRScannerView: UIViewControllerRepresentable {
    let onCode: (String) -> Void
    let onError: (String) -> Void

    func makeUIViewController(context: Context) -> QRScannerViewController {
        let vc = QRScannerViewController()
        vc.onCode = onCode
        vc.onError = onError
        return vc
    }

    func updateUIViewController(_ uiViewController: QRScannerViewController, context: Context) {}
}

final class QRScannerViewController: UIViewController, AVCaptureMetadataOutputObjectsDelegate {
    var onCode: ((String) -> Void)?
    var onError: ((String) -> Void)?

    private let session = AVCaptureSession()
    private var previewLayer: AVCaptureVideoPreviewLayer?
    private var hasFired = false
    /// Earliest moment we're willing to accept a decoded QR. Set 1.3 s
    /// after `session.startRunning()` returns so the camera has time to
    /// finish its initial autofocus pass — accepting the very first
    /// frame often locks onto an out-of-focus or stale image and either
    /// decodes wrong content or fails silently. 1.3 s is the empirical
    /// sweet spot: long enough for the lens to settle on a label held
    /// up to the camera, short enough that the user doesn't notice the
    /// wait once they're aimed.
    private var acceptDecodesAfter: Date = .distantFuture

    override func viewDidLoad() {
        super.viewDidLoad()
        view.backgroundColor = .black
        configureSession()
    }

    override func viewWillAppear(_ animated: Bool) {
        super.viewWillAppear(animated)
        hasFired = false
        acceptDecodesAfter = .distantFuture
        if !session.isRunning {
            DispatchQueue.global(qos: .userInitiated).async { [weak self] in
                self?.session.startRunning()
                // Once the session is actually running, give the camera
                // 1.3 s to autofocus before we'll trust any decode.
                DispatchQueue.main.async {
                    self?.acceptDecodesAfter = Date().addingTimeInterval(1.3)
                }
            }
        }
    }

    override func viewWillDisappear(_ animated: Bool) {
        super.viewWillDisappear(animated)
        if session.isRunning { session.stopRunning() }
    }

    override func viewDidLayoutSubviews() {
        super.viewDidLayoutSubviews()
        previewLayer?.frame = view.bounds
    }

    private func configureSession() {
        guard let device = AVCaptureDevice.default(for: .video),
              let input = try? AVCaptureDeviceInput(device: device) else {
            onError?("This device can't access the camera.")
            return
        }

        session.beginConfiguration()
        defer { session.commitConfiguration() }

        guard session.canAddInput(input) else {
            onError?("Couldn't attach the camera input.")
            return
        }
        session.addInput(input)

        let output = AVCaptureMetadataOutput()
        guard session.canAddOutput(output) else {
            onError?("Couldn't attach metadata output.")
            return
        }
        session.addOutput(output)
        output.setMetadataObjectsDelegate(self, queue: DispatchQueue.main)
        output.metadataObjectTypes = [.qr]

        let preview = AVCaptureVideoPreviewLayer(session: session)
        preview.frame = view.bounds
        preview.videoGravity = .resizeAspectFill
        view.layer.addSublayer(preview)
        self.previewLayer = preview
    }

    func metadataOutput(_ output: AVCaptureMetadataOutput,
                        didOutput metadataObjects: [AVMetadataObject],
                        from connection: AVCaptureConnection) {
        guard !hasFired,
              Date() >= acceptDecodesAfter,
              let obj = metadataObjects.first as? AVMetadataMachineReadableCodeObject,
              obj.type == .qr,
              let value = obj.stringValue else { return }

        // Defensive: a degenerate QR (e.g. one printed from a backend
        // that didn't include the qr_code_url/qr_code_token fields)
        // decodes to an empty string. Don't fire — surface a clear
        // error instead of bothering the lookup endpoint with an
        // empty token (which produces a confusing "token parameter is
        // required" 400).
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        if trimmed.isEmpty {
            hasFired = true
            session.stopRunning()
            onError?("This QR code is blank. Reprint the label after redeploying the backend so the resource has a fresh token.")
            return
        }

        hasFired = true
        Haptics.success()
        session.stopRunning()
        onCode?(trimmed)
    }
}
