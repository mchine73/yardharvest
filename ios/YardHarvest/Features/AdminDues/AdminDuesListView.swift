import SwiftUI

/// Manager-side dues roster — shows every dues record for the active garden,
/// pill-filtered, with a "Collect" button on each unpaid row that pushes the
/// Tap-to-Pay flow.
struct AdminDuesListView: View {
    let garden: Garden

    @State private var dues: [AdminDuesRecord] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var filter: Filter = .unpaid

    enum Filter: String, CaseIterable, Identifiable {
        case all, unpaid, paid
        var id: String { rawValue }
        var label: String { rawValue.capitalized }
        var apiValue: String? { self == .all ? nil : rawValue }
    }

    private var filtered: [AdminDuesRecord] {
        switch filter {
        case .all:    return dues
        case .unpaid: return dues.filter { !$0.isSettled && $0.balance > 0 }
        case .paid:   return dues.filter { $0.isSettled }
        }
    }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: dues.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "dollarsign.circle",
                    title: "No dues yet",
                    message: "Generate dues for this season on the website to start collecting.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    filterBar
                    ForEach(filtered) { record in
                        // View-destination link, NOT value-based. This stack
                        // has a duplicate-push bug when a pushed view
                        // registers `.navigationDestination(for:)` (see the
                        // note atop PaymentHubView) — and this list is itself
                        // a pushed view. Value navigation here produced a
                        // phantom extra dues list above the charge screen.
                        NavigationLink {
                            AdminCollectDuesView(garden: garden, record: record) {
                                Task { await load(showSpinner: false) }
                            }
                        } label: {
                            AdminDuesRow(record: record)
                        }
                        .buttonStyle(.plain)
                    }
                    if filtered.isEmpty {
                        YHCard {
                            Text(filter == .unpaid
                                 ? "No unpaid dues 🎉"
                                 : "No \(filter.label.lowercased()) dues to show.")
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
        .navigationTitle("Collect Dues")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
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
        do { dues = try await APIClient.shared.adminListDues(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct AdminDuesRow: View {
    let record: AdminDuesRecord

    var body: some View {
        YHCard {
            HStack(spacing: 12) {
                YHAvatar(name: record.userName, size: 42,
                         background: record.isSettled ? YH.surface : YH.lime)
                VStack(alignment: .leading, spacing: 2) {
                    Text(record.userName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    HStack(spacing: 6) {
                        Text(String(record.seasonYear))
                            .font(.yhCaption).foregroundStyle(YH.muted)
                        if record.balance > 0 {
                            Text("· $\(String(format: "%.2f", record.balance)) due")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        } else {
                            Text("· $\(String(format: "%.2f", record.amountPaid)) paid")
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                }
                Spacer()
                statusPill
            }
        }
    }

    @ViewBuilder private var statusPill: some View {
        switch record.status {
        case "paid":    YHPill(text: "Paid", tint: YH.ink, background: YH.lime)
        case "partial": YHPill(text: "Partial", tint: YH.ink, background: YH.surface)
        case "waived":  YHPill(text: "Waived", tint: YH.muted, background: YH.surface)
        case "comp":    YHPill(text: "Comp", tint: YH.muted, background: YH.surface)
        default:        YHPill(text: "Unpaid", tint: .white, background: YH.danger)
        }
    }

}
