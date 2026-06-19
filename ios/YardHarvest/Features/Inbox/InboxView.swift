import SwiftUI
import MessageUI
import UIKit

/// Threaded inbox — list of conversations with the same lime/Onest visual
/// language as the rest of the app. Tapping a row pushes `ThreadView`.
/// The toolbar "+" opens a peer picker (with a YardHarvest Admin email shortcut).
struct InboxView: View {
    @Environment(BadgeStore.self) private var badges

    @State private var threads: [InboxThread] = []
    @State private var isLoading = false
    @State private var errorMessage: String?

    // New-message flow
    @State private var showingPicker = false
    @State private var pendingNewPeer: NewPeerThread?
    @State private var pendingExistingThread: InboxThread?
    @State private var showingMailComposer = false
    @State private var actionToast: String?

    /// Identifiable wrapper so we can drive a `navigationDestination(item:)`
    /// push for a brand-new conversation (no thread on the backend yet).
    struct NewPeerThread: Identifiable, Hashable {
        let id = UUID()
        let userID: Int
        let name: String
    }

    private let supportEmail = "james@yardharvest.app"
    private let supportSubject = "YardHarvest support"

    var body: some View {
        Group {
            if threads.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<4, id: \.self) { _ in YHSkeletonCard(rows: 2) }
                    }
                    .padding(YH.Space.md)
                }
            } else if threads.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if threads.isEmpty {
                YHEmpty(systemImage: "bubble.left.and.bubble.right",
                        title: "No messages yet",
                        message: "Conversations with members and organizers show up here.")
            } else {
                YHContentReveal(systemImage: "bubble.left.and.bubble.right",
                                id: "inbox",
                                caption: "Your conversations") {
                    ScrollView {
                        LazyVStack(spacing: YH.Space.sm) {
                            ForEach(threads) { thread in
                                NavigationLink(value: thread) {
                                    InboxRow(thread: thread)
                                }
                                .buttonStyle(.plain)
                            }
                        }
                        .padding(YH.Space.md)
                    }
                    .refreshable { await load(showSpinner: false) }
                }
            }
        }
        .background(YH.canvas)
        // Both destinations live at the InboxView root so they work whether
        // threads are present or empty (e.g. picking a peer on first launch).
        .navigationDestination(for: InboxThread.self) { thread in
            ThreadView(thread: thread) {
                Task {
                    await badges.refresh()
                    await load(showSpinner: false)
                }
            }
        }
        .navigationDestination(item: $pendingNewPeer) { peer in
            ThreadView(recipientID: peer.userID, recipientName: peer.name) {
                Task {
                    await badges.refresh()
                    await load(showSpinner: false)
                }
            }
        }
        .navigationDestination(item: $pendingExistingThread) { thread in
            ThreadView(thread: thread) {
                Task {
                    await badges.refresh()
                    await load(showSpinner: false)
                }
            }
        }
        .navigationTitle("Messages")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Haptics.tap()
                    showingPicker = true
                } label: {
                    Image(systemName: "square.and.pencil")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
                .accessibilityLabel("New message")
            }
        }
        .overlay(alignment: .top) {
            if let toast = actionToast {
                Text(toast)
                    .font(.yhCaptionMed)
                    .foregroundStyle(YH.ink)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(YH.lime)
                    .clipShape(Capsule())
                    .padding(.top, 8)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
        .sheet(isPresented: $showingPicker) {
            NewMessagePickerSheet { destination in
                showingPicker = false
                handlePick(destination)
            }
        }
        .sheet(isPresented: $showingMailComposer) {
            MailComposeView(recipients: [supportEmail],
                            subject: supportSubject) { }
        }
        .task { await load() }
    }

    // MARK: - New-message flow

    private func handlePick(_ destination: NewMessagePickerSheet.Destination) {
        switch destination {
        case .peer(let userID, let name):
            // If we already have a thread with this peer, push that so the
            // user sees their conversation history — otherwise start a fresh
            // empty thread that the first send will materialize server-side.
            if let existing = threads.first(where: { $0.otherUser.id == userID }) {
                pendingExistingThread = existing
            } else {
                pendingNewPeer = NewPeerThread(userID: userID, name: name)
            }
        case .yardHarvestAdmin:
            openAdminMail()
        }
    }

    private func openAdminMail() {
        if MailComposeView.canSend {
            showingMailComposer = true
        } else if let url = MailtoURL.make(to: supportEmail, subject: supportSubject) {
            UIApplication.shared.open(url) { opened in
                if !opened {
                    Task { @MainActor in
                        showToast("No email app is set up on this device.")
                    }
                }
            }
        } else {
            showToast("Couldn't compose an email.")
        }
    }

    private func showToast(_ text: String) {
        withAnimation(YH.Motion.snappy) { actionToast = text }
        Task {
            try? await Task.sleep(nanoseconds: 2_400_000_000)
            withAnimation(YH.Motion.snappy) { actionToast = nil }
        }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { threads = try await APIClient.shared.inbox() }
        catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct InboxRow: View {
    let thread: InboxThread

    var body: some View {
        YHCard(padding: YH.Space.md) {
            HStack(spacing: 12) {
                avatar
                VStack(alignment: .leading, spacing: 4) {
                    HStack {
                        Text(thread.otherUser.displayName)
                            .font(thread.unread > 0 ? .yhBodyMedium : .yhBody)
                            .foregroundStyle(YH.ink)
                        Spacer()
                        if let when = thread.lastMessage.createdAt {
                            Text(when.formatted(.relative(presentation: .named)))
                                .font(.yhCaption)
                                .foregroundStyle(YH.muted)
                        }
                    }
                    Text(thread.lastMessage.body)
                        .font(.yhSubheadline)
                        .foregroundStyle(thread.unread > 0 ? YH.ink : YH.muted)
                        .lineLimit(2)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                if thread.unread > 0 {
                    Text("\(thread.unread)")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(YH.ink)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 3)
                        .background(YH.lime)
                        .clipShape(Capsule())
                }
            }
        }
    }

    private var avatar: some View {
        ZStack {
            Circle().fill(YH.lime)
            Text(initials(thread.otherUser.displayName))
                .font(.system(size: 15, weight: .bold))
                .foregroundStyle(YH.ink)
        }
        .frame(width: 44, height: 44)
    }

    private func initials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.map { String($0.first ?? " ") }.joined().uppercased()
    }
}
