import SwiftUI

/// Organizer-only moderation queue for the community wall — the iOS side of
/// the web admin's comment moderation.
///
/// Three segments: **Reported** posts are ones a member objected to and the
/// queue Apple's guideline 1.2 obliges us to work through; **Flagged** posts
/// are live on the wall but the AI moderator wants a human look (approve
/// clears the flag, delete removes them); **Auto-denied** posts were blocked
/// outright and are invisible everywhere else in the app — publishing one is
/// how a false positive gets rescued. Each card shows the moderator's stated
/// reason, because "the AI said so" is not reviewable.
struct ModerationView: View {
    let garden: Garden

    @State private var feed: APIClient.AdminCommentsFeed?
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var segment: Segment = .reported
    @State private var workingId: Int?
    @State private var pendingDelete: APIClient.AdminWallComment?

    enum Segment: String, CaseIterable, Identifiable {
        case reported, flagged, blocked
        var id: String { rawValue }
    }

    private var comments: [APIClient.AdminWallComment] { feed?.comments ?? [] }

    var body: some View {
        YHLoadable(isLoading: isLoading,
                   isEmpty: feed == nil,
                   errorMessage: errorMessage,
                   onRetry: { await load() }) {
            YHEmpty(systemImage: "checkmark.shield",
                    title: "Nothing to review",
                    message: "Reported, flagged and auto-denied posts appear here.")
        } content: {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    segmentBar
                    if comments.isEmpty {
                        YHCard {
                            Label(emptyQueueMessage, systemImage: "checkmark.seal")
                                .font(.yhSubheadline)
                                .foregroundStyle(YH.muted)
                        }
                    }
                    ForEach(comments) { comment in
                        ModerationCard(comment: comment,
                                       isWorking: workingId == comment.id,
                                       approveLabel: segment == .blocked ? "Publish" : "Keep",
                                       onApprove: { Task { await approve(comment) } },
                                       onDelete: { pendingDelete = comment })
                    }
                }
                .padding(YH.Space.md)
            }
            .refreshable { await load(showSpinner: false) }
        }
        .background(YH.canvas)
        .navigationTitle("Moderation")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: "\(garden.id)-\(segment.rawValue)") { await load() }
        .confirmationDialog("Delete this post?",
                            isPresented: Binding(get: { pendingDelete != nil },
                                                 set: { if !$0 { pendingDelete = nil } }),
                            titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                if let target = pendingDelete { Task { await remove(target) } }
            }
        } message: {
            Text(segment == .blocked
                 ? "The author was never shown it publicly; this erases it for good."
                 : "Removes it from the wall permanently.")
        }
    }

    private var segmentBar: some View {
        Picker("Queue", selection: $segment) {
            Text(reportedLabel).tag(Segment.reported)
            Text(flaggedLabel).tag(Segment.flagged)
            Text(blockedLabel).tag(Segment.blocked)
        }
        .pickerStyle(.segmented)
    }

    private var reportedLabel: String {
        let n = feed?.reportedCount ?? 0
        return n > 0 ? "Reported (\(n))" : "Reported"
    }

    /// Worded per queue — "nothing here" means something different in each.
    private var emptyQueueMessage: String {
        switch segment {
        case .reported: return "No reported posts — nothing is waiting on you."
        case .flagged:  return "No flagged posts — the wall is clean."
        case .blocked:  return "Nothing has been auto-denied."
        }
    }

    private var flaggedLabel: String {
        let n = feed?.flaggedCount ?? 0
        return n > 0 ? "Flagged (\(n))" : "Flagged"
    }

    private var blockedLabel: String {
        let n = feed?.blockedCount ?? 0
        return n > 0 ? "Auto-denied (\(n))" : "Auto-denied"
    }

    // MARK: - Data

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do {
            feed = try await APIClient.shared.adminListComments(
                gardenID: garden.id, status: segment.rawValue)
        }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func approve(_ comment: APIClient.AdminWallComment) async {
        guard workingId == nil else { return }
        workingId = comment.id
        defer { workingId = nil }
        do {
            _ = try await APIClient.shared.adminApproveComment(
                gardenID: garden.id, commentID: comment.id)
            Haptics.success()
            await load(showSpinner: false)
        } catch let error as APIError { errorMessage = error.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }

    private func remove(_ comment: APIClient.AdminWallComment) async {
        pendingDelete = nil
        guard workingId == nil else { return }
        workingId = comment.id
        defer { workingId = nil }
        do {
            try await APIClient.shared.adminDeleteComment(
                gardenID: garden.id, commentID: comment.id)
            Haptics.success()
            await load(showSpinner: false)
        } catch let error as APIError { errorMessage = error.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }
}

// MARK: - Card

private struct ModerationCard: View {
    let comment: APIClient.AdminWallComment
    let isWorking: Bool
    let approveLabel: String
    let onApprove: () -> Void
    let onDelete: () -> Void

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                HStack(spacing: 8) {
                    YHAvatar(name: comment.authorName, size: 32)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(comment.authorName)
                            .font(.yhBodyMedium).foregroundStyle(YH.ink)
                        if let at = comment.createdAt {
                            Text(at.formatted(.relative(presentation: .named)))
                                .font(.yhCaption).foregroundStyle(YH.muted)
                        }
                    }
                    Spacer()
                    if let n = comment.reportCount, n > 0 {
                        // Shows an organizer whether one person objected or
                        // several — that changes how urgent this is.
                        Text(n == 1 ? "1 report" : "\(n) reports")
                            .font(.system(size: 11, weight: .semibold))
                            .foregroundStyle(YH.danger)
                            .padding(.horizontal, 8)
                            .padding(.vertical, 4)
                            .background(YH.danger.opacity(0.12))
                            .clipShape(Capsule())
                    }
                }
                Text(comment.body)
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.ink)
                    .fixedSize(horizontal: false, vertical: true)
                if let reason = comment.moderationReason, !reason.isEmpty {
                    HStack(alignment: .top, spacing: 6) {
                        Image(systemName: "exclamationmark.bubble")
                            .font(.system(size: 12, weight: .semibold))
                        Text(reason)
                            .font(.yhCaption)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .foregroundStyle(YH.warning)
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(YH.warning.opacity(0.08))
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.sm, style: .continuous))
                }
                HStack(spacing: YH.Space.sm) {
                    YHButton(title: approveLabel, systemImage: "checkmark",
                             style: .lime, isLoading: isWorking, fullWidth: false) {
                        onApprove()
                    }
                    YHButton(title: "Delete", systemImage: "trash",
                             style: .ghost, fullWidth: false) {
                        onDelete()
                    }
                    Spacer()
                }
            }
        }
    }
}
