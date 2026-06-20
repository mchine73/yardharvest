import SwiftUI

/// Compose a brand-new message to a specific recipient (e.g. messaging a
/// garden organizer from `GardenDetailView`). Sends via `/api/messages/send`
/// and dismisses on success — the inbox refresh picks up the new thread.
struct ComposeMessageView: View {
    let recipientID: Int
    let recipientName: String
    /// Optional context (e.g. the garden name) shown as a chip above the editor.
    let contextLabel: String?
    /// Called after a successful send.
    let onSent: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var body_: String = ""
    @State private var isSending = false
    @State private var errorMessage: String?
    @FocusState private var focused: Bool

    init(recipientID: Int, recipientName: String,
         contextLabel: String? = nil, onSent: @escaping () -> Void) {
        self.recipientID = recipientID
        self.recipientName = recipientName
        self.contextLabel = contextLabel
        self.onSent = onSent
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    header
                    YHCard {
                        VStack(alignment: .leading, spacing: YH.Space.sm) {
                            Text("MESSAGE")
                                .font(.yhCaptionMed).tracking(0.6)
                                .foregroundStyle(YH.muted)
                            TextEditor(text: $body_)
                                .scrollContentBackground(.hidden)
                                .font(.yhBody)
                                .foregroundStyle(YH.ink)
                                .focused($focused)
                                .frame(minHeight: 160, alignment: .topLeading)
                                .padding(12)
                                .background(YH.surface)
                                .overlay(RoundedRectangle(cornerRadius: YH.Radius.md)
                                            .strokeBorder(YH.border))
                                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage)
                            .font(.yhSubheadline)
                            .foregroundStyle(YH.danger)
                    }
                    YHButton(title: "Send", systemImage: "paperplane.fill",
                             style: .dark, isLoading: isSending) {
                        Task { await send() }
                    }
                    .disabled(!canSend)
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("New Message")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) { Button("Cancel") { dismiss() } }
            }
            .task { focused = true }
        }
    }

    private var header: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 6) {
                Text("TO").font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                HStack(spacing: 10) {
                    YHAvatar(name: recipientName, size: 36)
                    Text(recipientName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                    Spacer()
                }
                if let contextLabel {
                    Label(contextLabel, systemImage: "leaf.fill")
                        .font(.yhCaption).foregroundStyle(YH.muted)
                }
            }
        }
    }

    private var canSend: Bool {
        !body_.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    private func send() async {
        guard canSend, !isSending else { return }
        isSending = true
        errorMessage = nil
        defer { isSending = false }
        do {
            _ = try await APIClient.shared.sendMessage(
                recipientID: recipientID,
                body: body_.trimmingCharacters(in: .whitespacesAndNewlines))
            Haptics.success()
            onSent()
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
