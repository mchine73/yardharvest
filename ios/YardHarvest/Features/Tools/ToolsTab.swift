import SwiftUI
import AVFoundation

/// Tools tab — built around the QR scanner as the primary action with the
/// tool inventory below. A modern viewfinder overlay shows guidance; tapping
/// the inventory rows lets the user act on a tool manually.
struct ToolsTab: View {
    @Environment(GardenStore.self) private var store
    @State private var showingPicker = false
    @State private var showingScanner = false

    var body: some View {
        NavigationStack {
            Group {
                if let garden = store.selectedGarden {
                    ToolsListView(garden: garden)
                } else if store.isLoading {
                    YHSkeletonCard().padding()
                } else {
                    YHEmpty(systemImage: "wrench.and.screwdriver",
                            title: "No garden selected",
                            message: "Pick a garden to view its tools.")
                }
            }
            .background(YH.canvas)
            .navigationTitle("Tools")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        Haptics.tap()
                        showingScanner = true
                    } label: {
                        Image(systemName: "qrcode.viewfinder")
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundStyle(YH.ink)
                    }
                    .accessibilityLabel("Scan a tool QR")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button {
                        Haptics.tap()
                        showingPicker = true
                    } label: {
                        Image(systemName: "arrow.up.arrow.down")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(YH.muted)
                    }
                }
            }
            .fullScreenCover(isPresented: $showingScanner) {
                ScannerScreen()
            }
            .sheet(isPresented: $showingPicker) { GardenPickerSheet().environment(store) }
        }
    }
}

/// Full-screen modal scanner with a viewfinder overlay and a Done button.
struct ScannerScreen: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(GardenStore.self) private var store

    @State private var scanned: String?
    @State private var lookup: ResourceLookup?
    @State private var isResolving = false
    @State private var errorMessage: String?
    @State private var cameraDenied = false

    var body: some View {
        ZStack {
            Color.black.ignoresSafeArea()
            if cameraDenied {
                cameraDeniedView
            } else {
                QRScannerView(
                    onCode: { code in
                        guard scanned == nil else { return }
                        scanned = code
                        Task { await resolve(code) }
                    },
                    onError: { msg in errorMessage = msg }
                )
                .ignoresSafeArea()
                viewfinderOverlay
            }
            if isResolving {
                Color.black.opacity(0.5).ignoresSafeArea()
                VStack(spacing: 12) {
                    ProgressView().tint(YH.ink)
                    Text("Resolving…").font(.yhBodyMedium).foregroundStyle(YH.ink)
                }
                .padding(20)
                .background(.ultraThinMaterial)
                .clipShape(RoundedRectangle(cornerRadius: 14))
            }
        }
        .overlay(alignment: .topLeading) {
            Button {
                Haptics.tap()
                dismiss()
            } label: {
                Label("Done", systemImage: "xmark")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.white)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(.ultraThinMaterial)
                    .clipShape(Capsule())
            }
            .padding(.horizontal, 16)
            .padding(.top, 12)
        }
        .task { await requestCamera() }
        .sheet(item: Binding(
            get: { lookup.map(IDLookup.init) },
            set: { lookup = $0?.value }
        )) { wrap in
            ResourceActionSheet(lookup: wrap.value) { changed in
                lookup = nil
                scanned = nil
                if changed { dismiss() }
            }
        }
        .alert("Scan Error",
               isPresented: Binding(
                get: { errorMessage != nil },
                set: { if !$0 { errorMessage = nil } }
               ),
               actions: {
            Button("OK") { errorMessage = nil; scanned = nil }
        }, message: { Text(errorMessage ?? "") })
    }

    private var viewfinderOverlay: some View {
        GeometryReader { proxy in
            let size = min(proxy.size.width, proxy.size.height) * 0.7
            ZStack {
                Color.black.opacity(0.35)
                    .mask {
                        Rectangle()
                            .overlay(
                                RoundedRectangle(cornerRadius: 24, style: .continuous)
                                    .frame(width: size, height: size)
                                    .blendMode(.destinationOut)
                            )
                            .compositingGroup()
                    }
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .strokeBorder(YH.lime, lineWidth: 3)
                    .frame(width: size, height: size)
                VStack {
                    Spacer()
                    Text("Point at a tool's QR code")
                        .font(.yhBodyMedium)
                        .foregroundStyle(YH.ink)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(YH.lime)
                        .clipShape(Capsule())
                        .padding(.bottom, 80)
                }
            }
        }
    }

    private var cameraDeniedView: some View {
        YHEmpty(systemImage: "camera.fill",
                title: "Camera access needed",
                message: "Enable camera access for YardHarvest in iOS Settings to scan tool QR codes.")
    }

    private func requestCamera() async {
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .notDetermined:
            let granted = await AVCaptureDevice.requestAccess(for: .video)
            cameraDenied = !granted
        case .denied, .restricted: cameraDenied = true
        default: cameraDenied = false
        }
    }

    private func resolve(_ token: String) async {
        isResolving = true
        defer { isResolving = false }
        do { lookup = try await APIClient.shared.resourceLookup(token: token) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct IDLookup: Identifiable {
    let value: ResourceLookup
    var id: Int { value.resourceId }
}
