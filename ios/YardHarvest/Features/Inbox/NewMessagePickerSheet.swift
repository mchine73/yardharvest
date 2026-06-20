import SwiftUI

/// Pick a recipient for a new conversation. Shows a pinned "YardHarvest
/// Admin" contact (which routes to email) followed by a searchable list of
/// peers from every garden the signed-in user is part of — deduplicated by
/// user id and excluding the signed-in user themselves.
struct NewMessagePickerSheet: View {
    /// Called with the selected destination. The parent dismisses the sheet
    /// and presents the appropriate follow-up (compose view or mail composer).
    let onSelected: (Destination) -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(AuthManager.self) private var auth
    @Environment(GardenStore.self) private var gardenStore

    @State private var peers: [PeerRow] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var search = ""

    enum Destination {
        case peer(userID: Int, name: String)
        case yardHarvestAdmin
    }

    /// Merged peer entry. `gardens` is the list of garden names they share
    /// with the signed-in user — shown as the row's subtitle.
    private struct PeerRow: Identifiable, Hashable {
        let userID: Int
        let name: String
        let isOrganizer: Bool
        let gardens: [String]
        let plotNumber: String?
        var id: Int { userID }
    }

    private var currentUserID: Int? {
        if case .signedIn(let u) = auth.state { return u.id }
        return nil
    }

    private var filteredPeers: [PeerRow] {
        guard !search.isEmpty else { return peers }
        let needle = search.lowercased()
        return peers.filter {
            $0.name.lowercased().contains(needle)
                || $0.gardens.joined(separator: " ").lowercased().contains(needle)
        }
    }

    var body: some View {
        NavigationStack {
            content
                .background(YH.canvas)
                .navigationTitle("New Message")
                .navigationBarTitleDisplayMode(.inline)
                .searchable(text: $search, prompt: "Search peers")
                .toolbar {
                    ToolbarItem(placement: .topBarLeading) {
                        Button("Cancel") { dismiss() }
                    }
                }
                .task { await load() }
        }
    }

    @ViewBuilder private var content: some View {
        ScrollView {
            VStack(spacing: YH.Space.md) {
                supportSection
                peerSection
            }
            .padding(YH.Space.md)
        }
    }

    private var supportSection: some View {
        VStack(alignment: .leading, spacing: YH.Space.xs) {
            Text("SUPPORT".uppercased())
                .font(.yhCaptionMed).tracking(0.6)
                .foregroundStyle(YH.muted)
                .padding(.horizontal, 4)
            Button {
                Haptics.tap()
                onSelected(.yardHarvestAdmin)
            } label: {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 14).fill(YH.ink)
                        Image(systemName: "envelope.fill")
                            .font(.system(size: 16, weight: .semibold))
                            .foregroundStyle(YH.lime)
                    }
                    .frame(width: 44, height: 44)
                    VStack(alignment: .leading, spacing: 2) {
                        Text("YardHarvest Admin")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text("Email james@yardharvest.app")
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                    Spacer()
                    Image(systemName: "arrow.up.right")
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(YH.muted)
                }
                .padding(YH.Space.md)
                .background(YH.canvas)
                .overlay(RoundedRectangle(cornerRadius: YH.Radius.lg).strokeBorder(YH.border))
                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg))
            }
            .buttonStyle(.plain)
        }
    }

    @ViewBuilder
    private var peerSection: some View {
        VStack(alignment: .leading, spacing: YH.Space.xs) {
            Text("FROM YOUR GARDENS")
                .font(.yhCaptionMed).tracking(0.6)
                .foregroundStyle(YH.muted)
                .padding(.horizontal, 4)
            if isLoading {
                VStack(spacing: YH.Space.sm) {
                    ForEach(0..<3, id: \.self) { _ in YHSkeletonCard(rows: 1) }
                }
            } else if let errorMessage {
                YHCard {
                    Text(errorMessage)
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.danger)
                }
            } else if peers.isEmpty {
                YHCard {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("No peers yet")
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        Text("Join a garden to message its members.")
                            .font(.yhSubheadline).foregroundStyle(YH.muted)
                    }
                }
            } else if filteredPeers.isEmpty {
                YHCard {
                    Text("No matches for “\(search)”.")
                        .font(.yhSubheadline).foregroundStyle(YH.muted)
                }
            } else {
                LazyVStack(spacing: YH.Space.sm) {
                    ForEach(filteredPeers) { peer in
                        Button {
                            Haptics.tap()
                            onSelected(.peer(userID: peer.userID, name: peer.name))
                        } label: {
                            peerRow(peer)
                        }
                        .buttonStyle(.plain)
                    }
                }
            }
        }
    }

    private func peerRow(_ peer: PeerRow) -> some View {
        HStack(spacing: 12) {
            YHAvatar(name: peer.name, size: 44)
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 6) {
                    Text(peer.name).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    if peer.isOrganizer {
                        YHPill(text: "Organizer", tint: YH.ink, background: YH.lime)
                    }
                }
                Text(subtitleLine(for: peer))
                    .font(.yhCaption).foregroundStyle(YH.muted)
                    .lineLimit(1)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(YH.muted)
        }
        .padding(YH.Space.md)
        .background(YH.canvas)
        .overlay(RoundedRectangle(cornerRadius: YH.Radius.lg).strokeBorder(YH.border))
        .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg))
    }

    private func subtitleLine(for peer: PeerRow) -> String {
        let gardenLabel = peer.gardens.joined(separator: " · ")
        if let plot = peer.plotNumber, !plot.isEmpty {
            return "Plot \(plot) · \(gardenLabel)"
        }
        return gardenLabel
    }

    private func load() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }

        let gardens = gardenStore.gardens?.all ?? []
        guard !gardens.isEmpty else {
            peers = []
            return
        }

        // Fetch all gardens' rosters in parallel.
        await withTaskGroup(of: (gardenName: String, members: [GardenMember]).self) { group in
            for garden in gardens {
                group.addTask {
                    let members = (try? await APIClient.shared.listGardenMembers(gardenID: garden.id)) ?? []
                    return (garden.name, members)
                }
            }
            var bucket: [Int: PeerRow] = [:]
            for await (gardenName, members) in group {
                for m in members {
                    if m.userId == currentUserID { continue }
                    if var existing = bucket[m.userId] {
                        if !existing.gardens.contains(gardenName) {
                            existing = PeerRow(
                                userID: existing.userID, name: existing.name,
                                isOrganizer: existing.isOrganizer || m.isOrganizer,
                                gardens: existing.gardens + [gardenName],
                                plotNumber: existing.plotNumber ?? m.plotNumber)
                        }
                        bucket[m.userId] = existing
                    } else {
                        bucket[m.userId] = PeerRow(
                            userID: m.userId, name: m.name,
                            isOrganizer: m.isOrganizer,
                            gardens: [gardenName],
                            plotNumber: m.plotNumber)
                    }
                }
            }
            peers = bucket.values.sorted { $0.name < $1.name }
        }
    }
}
