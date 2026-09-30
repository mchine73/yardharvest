import SwiftUI

/// The people you've blocked, and the way back.
///
/// App Store guideline 1.2 requires a block control; a block you cannot undo
/// would be a worse product than none, so this screen is reachable from
/// Settings whether or not the list is empty.
struct BlockedMembersView: View {
    @State private var members: [APIClient.BlockedMember] = []
    @State private var isLoading = true
    @State private var errorMessage: String?
    @State private var working: Set<Int> = []

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: members.isEmpty,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "hand.raised",
                    title: "Nobody blocked",
                    message: "Block someone from the menu on any post on a "
                           + "garden's community wall. Their posts stop "
                           + "showing up for you.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    ForEach(members) { member in
                        YHCard {
                            HStack(spacing: YH.Space.sm) {
                                YHAvatar(name: member.name, size: 34)
                                VStack(alignment: .leading, spacing: 0) {
                                    Text(member.name)
                                        .font(.yhBodyMedium)
                                        .foregroundStyle(YH.ink)
                                    if let at = member.blockedAt {
                                        Text("Blocked \(at.formatted(.relative(presentation: .named)))")
                                            .font(.yhCaption)
                                            .foregroundStyle(YH.muted)
                                    }
                                }
                                Spacer()
                                if working.contains(member.userId) {
                                    ProgressView()
                                } else {
                                    Button("Unblock") {
                                        Task { await unblock(member) }
                                    }
                                    .font(.system(size: 13, weight: .semibold))
                                    .foregroundStyle(YH.ink)
                                }
                            }
                        }
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Blocked")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        defer { isLoading = false }
        do {
            members = try await APIClient.shared.blockedMembers()
            errorMessage = nil
        } catch let error as APIError {
            errorMessage = error.errorDescription
        } catch {
            errorMessage = error.localizedDescription
        }
    }

    private func unblock(_ member: APIClient.BlockedMember) async {
        working.insert(member.userId)
        defer { working.remove(member.userId) }
        do {
            try await APIClient.shared.unblockMember(userID: member.userId)
            members.removeAll { $0.userId == member.userId }
            Haptics.success()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
