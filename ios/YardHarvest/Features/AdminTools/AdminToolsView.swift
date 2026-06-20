import SwiftUI

/// Manager-only tool inventory screen. Lists every tool in the active
/// garden, lets the admin add new ones (via `AdminAddToolView`), and lets
/// them print a QR label for any tool (via `ToolQRLabelSheet`). Scanning
/// the printed QR — from the iPhone Camera or our own in-app scanner —
/// drops a gardener into the checkout flow.
struct AdminToolsView: View {
    let garden: Garden

    @State private var resources: [GardenResource] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingAdd = false
    @State private var labelTarget: GardenResource?

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: resources.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() },
                   skeletonCards: 4) {
            YHEmpty(systemImage: "wrench.and.screwdriver",
                    title: "No tools yet",
                    message: "Add a tool to start tracking checkouts and printing QR labels.",
                    actionTitle: "Add a tool") { showingAdd = true }
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    heroBand
                    ForEach(resources) { resource in
                        toolRow(resource)
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Manage Tools")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Haptics.tap()
                    showingAdd = true
                } label: {
                    Image(systemName: "plus.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
                .accessibilityLabel("Add tool")
            }
        }
        .sheet(isPresented: $showingAdd) {
            AdminAddToolView(garden: garden) { created in
                resources.insert(created, at: 0)
                // Auto-open the QR sheet for the freshly-created tool so
                // the admin can print without an extra tap.
                labelTarget = created
            }
        }
        .sheet(item: $labelTarget) { res in
            ToolQRLabelSheet(garden: garden, resource: res)
        }
        .task(id: garden.id) { await load() }
    }

    // MARK: - Sections

    private var heroBand: some View {
        YHBand(tint: .lime) {
            HStack(spacing: 12) {
                YHIconTile(systemImage: "qrcode",
                           size: 48, background: YH.ink, foreground: YH.lime)
                VStack(alignment: .leading, spacing: 2) {
                    Text("\(resources.count) tool\(resources.count == 1 ? "" : "s")")
                        .font(.yhTitle3).foregroundStyle(YH.ink)
                    Text("Tap any tool to print a QR label. Gardeners scan it to check out.")
                        .font(.yhCaption).foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    private func toolRow(_ resource: GardenResource) -> some View {
        Button {
            Haptics.tap()
            labelTarget = resource
        } label: {
            HStack(spacing: 12) {
                YHIconTile(systemImage: iconName(for: resource), size: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(resource.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    HStack(spacing: 6) {
                        if let type = resource.resourceType {
                            Text(type.capitalized).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                        if let who = resource.checkedOutToName {
                            Text("· out to \(who)")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                }
                Spacer()
                statusPill(for: resource)
                Image(systemName: "qrcode")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundStyle(YH.ink)
                    .padding(.leading, 4)
            }
            .padding(YH.Space.md)
            .background(YH.canvas)
            .overlay(RoundedRectangle(cornerRadius: YH.Radius.md).strokeBorder(YH.border))
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func statusPill(for resource: GardenResource) -> some View {
        switch resource.status {
        case "available":     YHPill(text: "Available", tint: YH.ink, background: YH.lime)
        case "checked_out":   YHPill(text: "Out", tint: YH.muted, background: YH.surface)
        case "overdue":       YHPill(text: "Overdue", tint: .white, background: YH.danger)
        case "out_of_service": YHPill(text: "Service", tint: .white, background: YH.warning)
        default: EmptyView()
        }
    }

    private func iconName(for resource: GardenResource) -> String {
        switch (resource.resourceType ?? "tool").lowercased() {
        case "tool": return "wrench.adjustable.fill"
        case "equipment": return "hammer.fill"
        case "supply": return "tray.full.fill"
        case "seed": return "leaf.fill"
        default: return "wrench.and.screwdriver.fill"
        }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { resources = try await APIClient.shared.listResources(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}
