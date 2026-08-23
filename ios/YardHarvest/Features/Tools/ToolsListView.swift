import SwiftUI

/// Tool inventory with status filter pills + bento-card rows.
struct ToolsListView: View {
    let garden: Garden

    @State private var resources: [GardenResource] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: ToolFilter = .all
    @State private var selected: GardenResource?

    enum ToolFilter: String, CaseIterable, Identifiable {
        case all, available, out = "out", overdue, service
        var id: String { rawValue }
        var label: String {
            switch self {
            case .all: return "All"
            case .available: return "Available"
            case .out: return "Out"
            case .overdue: return "Overdue"
            case .service: return "Service"
            }
        }
    }

    var filtered: [GardenResource] {
        switch filter {
        case .all: return resources
        case .available: return resources.filter { $0.status == "available" }
        case .out: return resources.filter { $0.status == "checked_out" }
        case .overdue: return resources.filter { $0.status == "overdue" }
        case .service: return resources.filter { $0.status == "out_of_service" }
        }
    }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: resources.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "wrench.and.screwdriver",
                    title: "No tools yet",
                    message: "Tools added on the web will appear here.")
        } content: {
            YHContentReveal(systemImage: "wrench.and.screwdriver",
                            id: "tools-\(garden.id)",
                            caption: "Your toolbox") {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        filterBar
                        ForEach(filtered) { r in
                            Button {
                                Haptics.tap()
                                selected = r
                            } label: {
                                ToolRow(resource: r)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                    .padding(YH.Space.md)
                }
                .refreshable { await load(showSpinner: false) }
            }
        }
        .task(id: garden.id) { await load() }
        .sheet(item: $selected) { resource in
            // Same sheet the QR scanner lands on — the row is just a scan
            // you didn't have to point a camera at.
            ResourceActionSheet(
                lookup: ResourceLookup(gardenId: garden.id,
                                       gardenName: garden.name,
                                       resourceId: resource.id,
                                       resource: resource),
                organizerId: garden.organizerId
            ) { changed in
                selected = nil
                if changed { Task { await load(showSpinner: false) } }
            }
        }
    }

    private var filterBar: some View {
        YHFilterChips(selection: $filter,
                      options: ToolFilter.allCases,
                      label: { $0.label })
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

private struct ToolRow: View {
    let resource: GardenResource

    var body: some View {
        YHCard(padding: YH.Space.md) {
            HStack(spacing: 12) {
                ZStack {
                    RoundedRectangle(cornerRadius: 10).fill(YH.surface)
                    Image(systemName: iconName)
                        .font(.system(size: 18, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
                .frame(width: 44, height: 44)
                VStack(alignment: .leading, spacing: 2) {
                    Text(resource.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    HStack(spacing: 6) {
                        if let type = resource.resourceType {
                            Text(type.capitalized).font(.yhCaption).foregroundStyle(YH.muted)
                        }
                        if let to = resource.checkedOutToName {
                            Text("· \(to)").font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                }
                Spacer()
                statusPill
            }
        }
    }

    private var iconName: String {
        switch (resource.resourceType ?? "tool").lowercased() {
        case "tool": return "wrench.adjustable.fill"
        case "equipment": return "hammer.fill"
        case "supply": return "tray.full.fill"
        case "seed": return "leaf.fill"
        default: return "wrench.and.screwdriver.fill"
        }
    }

    @ViewBuilder
    private var statusPill: some View {
        switch resource.status {
        case "available": YHPill(text: "Available", tint: YH.ink, background: YH.lime)
        case "checked_out": YHPill(text: "Out", tint: YH.muted, background: YH.surface)
        case "overdue": YHPill(text: "Overdue", tint: .white, background: YH.danger)
        case "out_of_service": YHPill(text: "Service", tint: .white, background: YH.warning)
        default: YHPill(text: resource.status.capitalized, tint: YH.muted, background: YH.surface)
        }
    }
}
