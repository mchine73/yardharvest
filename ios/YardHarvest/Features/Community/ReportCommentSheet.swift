import SwiftUI

/// Report a wall post as objectionable.
///
/// App Store guideline 1.2 requires any app carrying user-generated content to
/// offer this. A report flags the post into the garden organizer's moderation
/// queue immediately and notifies them, so a human looks at it quickly.
struct ReportCommentSheet: View {
    let garden: Garden
    let comment: WallComment
    /// Called with the confirmation to show once the report is filed.
    let onReported: (String) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var reasons: [APIClient.ReportReason] = []
    @State private var selected: String?
    @State private var note = ""
    @State private var isLoading = true
    @State private var isSending = false
    @State private var errorMessage: String?

    /// Offered if the network call for the list fails — the sheet must still
    /// work offline-ish, because a blocked report is a rejected app.
    private static let fallback: [APIClient.ReportReason] = [
        .init(id: "harassment", label: "Harassment or bullying"),
        .init(id: "hate", label: "Hate speech"),
        .init(id: "spam", label: "Spam or scam"),
        .init(id: "sexual", label: "Sexual content"),
        .init(id: "violence", label: "Violence or threats"),
        .init(id: "other", label: "Something else"),
    ]

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(comment.authorName)
                            .font(.yhBodyMedium)
                            .foregroundStyle(YH.ink)
                        Text(comment.body)
                            .font(.yhCaption)
                            .foregroundStyle(YH.muted)
                            .lineLimit(3)
                    }
                    .padding(.vertical, 2)
                }

                Section("What's wrong with it?") {
                    if isLoading {
                        HStack { ProgressView(); Text("Loading").foregroundStyle(YH.muted) }
                    } else {
                        ForEach(reasons) { reason in
                            Button {
                                selected = reason.id
                            } label: {
                                HStack {
                                    Text(reason.label).foregroundStyle(YH.ink)
                                    Spacer()
                                    if selected == reason.id {
                                        Image(systemName: "checkmark")
                                            .foregroundStyle(YH.ink)
                                            .fontWeight(.semibold)
                                    }
                                }
                            }
                        }
                    }
                }

                Section("Anything to add? (optional)") {
                    TextField("Tell the organizer what happened", text: $note,
                              axis: .vertical)
                        .lineLimit(2...5)
                }

                Section {
                    Text("The garden's organizer reviews reported posts and can "
                         + "remove them. To stop seeing this member entirely, "
                         + "block them from the same menu.")
                        .font(.yhCaption)
                        .foregroundStyle(YH.muted)
                }

                if let errorMessage {
                    Text(errorMessage).foregroundStyle(YH.danger)
                }
            }
            .navigationTitle("Report post")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                        .foregroundStyle(YH.muted)
                        .disabled(isSending)
                }
                ToolbarItem(placement: .topBarTrailing) {
                    if isSending {
                        ProgressView()
                    } else {
                        Button("Send") { Task { await send() } }
                            .fontWeight(.semibold)
                            .disabled(selected == nil)
                    }
                }
            }
            .interactiveDismissDisabled(isSending)
            .task { await loadReasons() }
        }
    }

    private func loadReasons() async {
        defer { isLoading = false }
        do {
            let fetched = try await APIClient.shared.commentReportReasons()
            reasons = fetched.isEmpty ? Self.fallback : fetched
        } catch {
            reasons = Self.fallback
        }
    }

    private func send() async {
        guard let reason = selected else { return }
        isSending = true
        errorMessage = nil
        defer { isSending = false }
        do {
            try await APIClient.shared.reportWallComment(
                gardenID: garden.id, commentID: comment.id,
                reason: reason,
                note: note.trimmingCharacters(in: .whitespacesAndNewlines))
            Haptics.success()
            onReported("This post has been sent to the garden's organizer for review.")
            dismiss()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }
}
