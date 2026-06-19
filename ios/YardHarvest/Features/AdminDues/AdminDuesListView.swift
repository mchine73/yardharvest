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
        Group {
            if dues.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<4, id: \.self) { _ in YHSkeletonCard(rows: 2) }
                    }.padding()
                }
            } else if dues.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if dues.isEmpty {
                YHEmpty(systemImage: "dollarsign.circle",
                        title: "No dues yet",
                        message: "Generate dues for this season on the website to start collecting.")
            } else {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        filterBar
                        ForEach(filtered) { record in
                            NavigationLink(value: record) {
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
                .navigationDestination(for: AdminDuesRecord.self) { record in
                    AdminCollectDuesView(garden: garden, record: record) {
                        Task { await load(showSpinner: false) }
                    }
                }
            }
        }
        .background(YH.canvas)
        .navigationTitle("Collect Dues")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: garden.id) { await load() }
    }

    private var filterBar: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(Filter.allCases) { f in
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
                ZStack {
                    Circle().fill(record.isSettled ? YH.surface : YH.lime)
                    Text(initials(record.userName))
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(YH.ink)
                }
                .frame(width: 42, height: 42)
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

    private func initials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.map { String($0.first ?? " ") }.joined().uppercased()
    }
}
