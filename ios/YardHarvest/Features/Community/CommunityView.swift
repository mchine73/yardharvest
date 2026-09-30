import SwiftUI

/// `GET /api/gardens/{id}/comments` — shape from `_comment_to_dict` in
/// `app/api/gardens_api.py`. Lives with the feature; nothing else uses it.
struct WallComment: Codable, Identifiable, Equatable {
    let id: Int
    let gardenId: Int
    let parentId: Int?
    let authorId: Int
    let authorName: String
    let authorImage: String?
    let body: String
    /// `approved` or `flagged` (flagged posts show but the organizer was alerted).
    let status: String
    var likesCount: Int
    var likedByMe: Bool
    let createdAt: Date?
    let canDelete: Bool
    /// False on your own posts — there is nothing to report or block there.
    let canReport: Bool
    var reportedByMe: Bool

    enum CodingKeys: String, CodingKey {
        case id
        case gardenId = "garden_id"
        case parentId = "parent_id"
        case authorId = "author_id"
        case authorName = "author_name"
        case authorImage = "author_image"
        case body, status
        case likesCount = "likes_count"
        case likedByMe = "liked_by_me"
        case createdAt = "created_at"
        case canDelete = "can_delete"
        case canReport = "can_report"
        case reportedByMe = "reported_by_me"
    }
}

/// The garden's community wall — the members' feed from the web's garden
/// page, in brand. Top-level posts with one level of replies, likes, and a
/// composer pinned below the feed. Posting runs the backend's AI moderator:
/// a held post comes back as an error explaining why, shown verbatim.
struct CommunityView: View {
    let garden: Garden

    @Environment(AuthManager.self) private var auth
    @State private var comments: [WallComment] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var composerText = ""
    @State private var replyTarget: WallComment?
    @State private var isPosting = false
    @State private var postError: String?
    @State private var pendingDelete: WallComment?
    @State private var reportTarget: WallComment?
    @State private var pendingBlock: WallComment?
    @State private var noticeMessage: String?
    @FocusState private var composerFocused: Bool

    private var isOrganizer: Bool {
        // Moderation rides the CONTENT capability (organizer + co-organizer);
        // the identity check remains as a fallback for payloads without
        // capabilities. The backend enforces regardless.
        if garden.can("content") { return true }
        if case .signedIn(let u) = auth.state { return garden.organizerId == u.id }
        return false
    }

    private var topLevel: [WallComment] { comments.filter { $0.parentId == nil } }
    private func replies(to comment: WallComment) -> [WallComment] {
        comments.filter { $0.parentId == comment.id }
            .sorted { ($0.createdAt ?? .distantPast) < ($1.createdAt ?? .distantPast) }
    }

    var body: some View {
        VStack(spacing: 0) {
            YHLoadable(isLoading: isLoading,
                       isEmpty: comments.isEmpty,
                       errorMessage: errorMessage,
                       onRetry: { await load() }) {
                YHEmpty(systemImage: "bubble.left.and.bubble.right",
                        title: "Nothing on the wall yet",
                        message: "Say hello — posts here are visible to everyone in the garden.")
            } content: {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        PhotoStripSection(garden: garden)
                        ForEach(topLevel) { comment in
                            WallCommentCard(comment: comment,
                                            replies: replies(to: comment),
                                            onLike: { c in Task { await toggleLike(c) } },
                                            onReply: { c in
                                                replyTarget = c
                                                composerFocused = true
                                            },
                                            onDelete: { c in pendingDelete = c },
                                            onReport: { c in reportTarget = c },
                                            onBlock: { c in pendingBlock = c })
                        }
                    }
                    .padding(YH.Space.md)
                }
                .refreshable { await load(showSpinner: false) }
            }
            composer
        }
        .background(YH.canvas)
        .navigationTitle("Community")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if isOrganizer {
                ToolbarItem(placement: .topBarTrailing) {
                    // View-destination link per the house rule — this screen
                    // is itself a pushed view.
                    NavigationLink {
                        ModerationView(garden: garden)
                    } label: {
                        Image(systemName: "checkmark.shield")
                            .font(.system(size: 15, weight: .medium))
                            .foregroundStyle(YH.ink)
                    }
                    .accessibilityLabel("Moderation queue")
                }
            }
        }
        .task(id: garden.id) { await load() }
        .confirmationDialog("Delete this post?",
                            isPresented: Binding(get: { pendingDelete != nil },
                                                 set: { if !$0 { pendingDelete = nil } }),
                            titleVisibility: .visible) {
            Button("Delete", role: .destructive) {
                if let target = pendingDelete { Task { await remove(target) } }
            }
        } message: {
            Text("Replies to it are removed too. This can't be undone.")
        }
        .sheet(item: $reportTarget) { target in
            ReportCommentSheet(garden: garden, comment: target) { message in
                // Mark it reported locally so the menu reads "Reported" without
                // a round trip; the post also moves into the organizer's queue.
                if let i = comments.firstIndex(where: { $0.id == target.id }) {
                    comments[i].reportedByMe = true
                }
                noticeMessage = message
            }
        }
        .confirmationDialog("Block \(pendingBlock?.authorName ?? "this member")?",
                            isPresented: Binding(get: { pendingBlock != nil },
                                                 set: { if !$0 { pendingBlock = nil } }),
                            titleVisibility: .visible) {
            Button("Block", role: .destructive) {
                if let target = pendingBlock { Task { await block(target) } }
            }
        } message: {
            Text("You won't see their posts or replies anywhere in YardHarvest. "
                 + "They aren't told. You can undo this in Settings.")
        }
        .alert("Thanks", isPresented: Binding(get: { noticeMessage != nil },
                                              set: { if !$0 { noticeMessage = nil } })) {
            Button("OK", role: .cancel) { noticeMessage = nil }
        } message: {
            Text(noticeMessage ?? "")
        }
    }

    // MARK: - Composer

    private var composer: some View {
        VStack(spacing: 6) {
            if let replyTarget {
                HStack(spacing: 6) {
                    Image(systemName: "arrowshape.turn.up.left")
                        .font(.system(size: 11, weight: .semibold))
                    Text("Replying to \(replyTarget.authorName)")
                        .font(.yhCaption)
                    Spacer()
                    Button {
                        self.replyTarget = nil
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundStyle(YH.muted)
                    }
                }
                .foregroundStyle(YH.muted)
                .padding(.horizontal, YH.Space.md)
            }
            if let postError {
                Text(postError)
                    .font(.yhCaption)
                    .foregroundStyle(YH.danger)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, YH.Space.md)
            }
            HStack(spacing: YH.Space.xs) {
                TextField("Write something…", text: $composerText, axis: .vertical)
                    .lineLimit(1...4)
                    .focused($composerFocused)
                    .font(.system(size: 16))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(YH.surface)
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg, style: .continuous))
                Button {
                    Task { await post() }
                } label: {
                    Group {
                        if isPosting {
                            ProgressView().tint(YH.ink)
                        } else {
                            Image(systemName: "arrow.up")
                                .font(.system(size: 16, weight: .bold))
                                .foregroundStyle(YH.ink)
                        }
                    }
                    .frame(width: 40, height: 40)
                    .background(YH.lime)
                    .clipShape(Circle())
                }
                .disabled(isPosting
                          || composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
            .padding(.horizontal, YH.Space.md)
        }
        .padding(.vertical, YH.Space.sm)
        .background(YH.canvas)
        .overlay(alignment: .top) { Divider().overlay(YH.border) }
    }

    // MARK: - Data

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { comments = try await APIClient.shared.listWallComments(gardenID: garden.id) }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func post() async {
        guard !isPosting else { return }
        let text = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        isPosting = true
        postError = nil
        defer { isPosting = false }
        do {
            let posted = try await APIClient.shared.postWallComment(
                gardenID: garden.id, body: text, parentID: replyTarget?.id)
            comments.insert(posted, at: 0)
            composerText = ""
            replyTarget = nil
            composerFocused = false
            Haptics.success()
        } catch let error as APIError {
            // Moderation holds arrive as a server message — show it as-is.
            postError = error.errorDescription
            Haptics.error()
        } catch {
            postError = error.localizedDescription
            Haptics.error()
        }
    }

    private func toggleLike(_ comment: WallComment) async {
        do {
            let result = try await APIClient.shared.toggleCommentLike(
                gardenID: garden.id, commentID: comment.id)
            if let i = comments.firstIndex(where: { $0.id == comment.id }) {
                comments[i].likesCount = result.likesCount
                comments[i].likedByMe = result.liked
            }
            Haptics.tap()
        } catch { /* likes are low-stakes; a failed toggle just stays put */ }
    }

    private func block(_ comment: WallComment) async {
        let target = comment
        pendingBlock = nil
        do {
            try await APIClient.shared.blockMember(userID: target.authorId)
            // Their posts leave this feed immediately rather than on next load.
            comments.removeAll { $0.authorId == target.authorId }
            Haptics.success()
            noticeMessage = "You won't see posts from \(target.authorName) any more."
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func remove(_ comment: WallComment) async {
        pendingDelete = nil
        do {
            try await APIClient.shared.deleteWallComment(gardenID: garden.id,
                                                         commentID: comment.id)
            comments.removeAll { $0.id == comment.id || $0.parentId == comment.id }
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

// MARK: - Comment card

private struct WallCommentCard: View {
    let comment: WallComment
    let replies: [WallComment]
    let onLike: (WallComment) -> Void
    let onReply: (WallComment) -> Void
    let onDelete: (WallComment) -> Void
    let onReport: (WallComment) -> Void
    let onBlock: (WallComment) -> Void

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                CommentBody(comment: comment,
                            onLike: onLike, onReply: onReply, onDelete: onDelete,
                            onReport: onReport, onBlock: onBlock,
                            isReply: false)
                ForEach(replies) { reply in
                    HStack(alignment: .top, spacing: YH.Space.xs) {
                        RoundedRectangle(cornerRadius: 1)
                            .fill(YH.border)
                            .frame(width: 2)
                        CommentBody(comment: reply,
                                    onLike: onLike, onReply: onReply, onDelete: onDelete,
                                    onReport: onReport, onBlock: onBlock,
                                    isReply: true)
                    }
                    .padding(.leading, YH.Space.sm)
                }
            }
        }
    }
}

private struct CommentBody: View {
    let comment: WallComment
    let onLike: (WallComment) -> Void
    let onReply: (WallComment) -> Void
    let onDelete: (WallComment) -> Void
    let onReport: (WallComment) -> Void
    let onBlock: (WallComment) -> Void
    let isReply: Bool

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                YHAvatar(name: comment.authorName, size: isReply ? 26 : 34)
                VStack(alignment: .leading, spacing: 0) {
                    Text(comment.authorName)
                        .font(isReply ? .yhCaptionMed : .yhBodyMedium)
                        .foregroundStyle(YH.ink)
                    if let at = comment.createdAt {
                        Text(at.formatted(.relative(presentation: .named)))
                            .font(.yhCaption)
                            .foregroundStyle(YH.muted)
                    }
                }
                Spacer()
                // One overflow menu rather than a row of icons: delete is for
                // your own posts, report and block are for everyone else's.
                if comment.canDelete || comment.canReport {
                    Menu {
                        if comment.canReport {
                            Button {
                                onReport(comment)
                            } label: {
                                Label(comment.reportedByMe ? "Reported" : "Report post",
                                      systemImage: "flag")
                            }
                            .disabled(comment.reportedByMe)
                            Button(role: .destructive) {
                                onBlock(comment)
                            } label: {
                                Label("Block \(comment.authorName)",
                                      systemImage: "hand.raised")
                            }
                        }
                        if comment.canDelete {
                            Button(role: .destructive) {
                                onDelete(comment)
                            } label: {
                                Label("Delete post", systemImage: "trash")
                            }
                        }
                    } label: {
                        Image(systemName: "ellipsis")
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(YH.muted)
                            .frame(width: 30, height: 30)
                            .contentShape(Rectangle())
                    }
                    .accessibilityLabel("More actions")
                }
            }
            Text(comment.body)
                .font(.yhSubheadline)
                .foregroundStyle(YH.ink)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: YH.Space.md) {
                Button { onLike(comment) } label: {
                    HStack(spacing: 4) {
                        Image(systemName: comment.likedByMe ? "heart.fill" : "heart")
                            .foregroundStyle(comment.likedByMe ? YH.danger : YH.muted)
                        if comment.likesCount > 0 {
                            Text("\(comment.likesCount)")
                                .foregroundStyle(YH.muted)
                        }
                    }
                    .font(.system(size: 13, weight: .medium))
                }
                if !isReply {
                    Button { onReply(comment) } label: {
                        Text("Reply")
                            .font(.system(size: 13, weight: .medium))
                            .foregroundStyle(YH.muted)
                    }
                }
                Spacer()
            }
        }
    }
}
