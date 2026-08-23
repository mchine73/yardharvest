import SwiftUI

/// Manager-side plot roster — the iOS counterpart of the web admin
/// dashboard's "Plot Management" tab. Shows every plot with its status,
/// occupant, and renewal date; tapping a plot pushes the detail screen with
/// the full action set (confirm/decline reservations, assign, release,
/// maintenance, edit).
///
/// The drag-and-drop Garden Designer stays a website feature — laying out a
/// grid is desktop work. This screen is for the day-to-day: who has which
/// plot, what's pending, what's open.
struct PlotsView: View {
    let garden: Garden

    @State private var plots: [Plot] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: Filter = .all

    enum Filter: String, CaseIterable, Identifiable {
        case all, available, assigned, reserved, maintenance
        var id: String { rawValue }
        var label: String { self == .reserved ? "Pending" : rawValue.capitalized }
    }

    private var filtered: [Plot] {
        filter == .all ? plots : plots.filter { $0.status == filter.rawValue }
    }

    private var pendingCount: Int { plots.filter { $0.status == "reserved" }.count }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: plots.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "square.grid.3x3",
                    title: "No plots yet",
                    message: "Design your garden layout on the website to create plots, then manage them here.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    if pendingCount > 0 { pendingBanner }
                    filterBar
                    ForEach(filtered) { plot in
                        // View-destination link — value-based navigation from
                        // a pushed view duplicate-pushes on this stack (see
                        // the note atop PaymentHubView).
                        NavigationLink {
                            PlotDetailView(garden: garden, plot: plot) {
                                Task { await load(showSpinner: false) }
                            }
                        } label: {
                            PlotRow(plot: plot)
                        }
                        .buttonStyle(.plain)
                    }
                    if filtered.isEmpty {
                        YHCard {
                            Text("No \(filter.label.lowercased()) plots to show.")
                                .font(.yhSubheadline)
                                .foregroundStyle(YH.muted)
                        }
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Plots")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
    }

    /// Mirrors the web's explainer: reservations vs the waitlist trips up
    /// new organizers, so say it once, up top, only when it matters.
    private var pendingBanner: some View {
        YHBand(tint: .lime) {
            HStack(spacing: 12) {
                Image(systemName: "clock.badge.exclamationmark")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundStyle(YH.ink)
                VStack(alignment: .leading, spacing: 2) {
                    Text(pendingCount == 1
                         ? "1 reservation waiting"
                         : "\(pendingCount) reservations waiting")
                        .font(.yhTitle3)
                        .foregroundStyle(YH.ink)
                    Text("Members reserved specific plots from your garden page. Confirm or decline them below.")
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.ink.opacity(0.75))
                }
                Spacer()
            }
        }
    }

    private var filterBar: some View {
        YHFilterChips(selection: $filter,
                      options: Filter.allCases,
                      label: { $0.label })
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { plots = try await APIClient.shared.adminListPlots(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

// MARK: - Row

struct PlotRow: View {
    let plot: Plot

    var body: some View {
        YHCard {
            HStack(spacing: 12) {
                numberTile
                VStack(alignment: .leading, spacing: 2) {
                    Text(plot.displayLabel)
                        .font(.yhBodyMedium)
                        .foregroundStyle(YH.ink)
                    Text(subtitle)
                        .font(.yhCaption)
                        .foregroundStyle(YH.muted)
                        .lineLimit(1)
                }
                Spacer()
                PlotStatusPill(status: plot.status)
            }
        }
    }

    /// Square number chip — echoes the web layout grid without pretending
    /// to be one.
    private var numberTile: some View {
        Text("#\(plot.plotNumber)")
            .font(.system(size: 15, weight: .bold))
            .foregroundStyle(YH.ink)
            .frame(width: 46, height: 46)
            .background(plot.status == "assigned" ? YH.lime : YH.surface)
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
    }

    private var subtitle: String {
        var parts: [String] = []
        if let size = plot.size, !size.isEmpty { parts.append(size) }
        if let name = plot.assignedToName {
            parts.append(name)
        } else if let reserver = plot.reservedByName {
            parts.append("Reserved by \(reserver)")
        }
        if parts.isEmpty { parts.append("Unassigned") }
        return parts.joined(separator: " · ")
    }
}

// MARK: - Status pill

/// One source of truth for plot status colors — mirrors the web's
/// PLOT_STATUS_COLORS palette in brand terms.
struct PlotStatusPill: View {
    let status: String

    var body: some View {
        switch status {
        case "available":   YHPill(text: "Available", tint: YH.ink, background: YH.lime)
        case "assigned":    YHPill(text: "Assigned", tint: YH.ink, background: YH.surface)
        case "reserved":    YHPill(text: "Pending", tint: .white, background: YH.warning)
        case "maintenance": YHPill(text: "Maintenance", tint: .white, background: YH.muted)
        default:            YHPill(text: status.capitalized, tint: YH.ink, background: YH.surface)
        }
    }
}
