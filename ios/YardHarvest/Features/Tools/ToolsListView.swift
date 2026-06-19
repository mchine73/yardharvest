import SwiftUI

/// Tool inventory with status filter pills + bento-card rows.
struct ToolsListView: View {
    let garden: Garden

    @State private var resources: [GardenResource] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: ToolFilter = .all

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
        Group {
            if resources.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<4, id: \.self) { _ in YHSkeletonCard() }
                    }.padding()
                }
            } else if resources.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if resources.isEmpty {
                YHEmpty(systemImage: "wrench.and.screwdriver",
                        title: "No tools yet",
                        message: "Tools added on the web will appear here.")
            } else {
                YHContentReveal(systemImage: "wrench.and.screwdriver",
                                id: "tools-\(garden.id)",
                                caption: "Your toolbox") {
                    ScrollView {
                        VStack(spacing: YH.Space.sm) {
                            filterBar
                            ForEach(filtered) { r in
                                ToolRow(resource: r)
                            }
                        }
                        .padding(YH.Space.md)
                    }
                    .refreshable { await load(showSpinner: false) }
                }
            }
        }
        .task(id: garden.id) { await load() }
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(ToolFilter.allCases) { f in
                    Button {
                        Haptics.selection()
                        filter = f
                    } label: {
                        Text(f.label)
                            .font(.system(size: 13, weight: .semibold))
                            .padding(.horizontal, 14)
                            .padding(.vertical, 7)
                            .foregroundStyle(filter == f ? .white : YH.ink)
                            .background(filter == f ? YH.ink : YH.surface)
                            .clipShape(Capsule())
                    }
                    .buttonStyle(.plain)
                }
            }
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
