import SwiftUI

/// Chat-style conversation. Outgoing bubbles render in ink with white type,
/// incoming bubbles use the surface gray. The composer at the bottom rides
/// above the keyboard via `safeAreaInset`.
///
/// Has two entry points:
///   • `init(thread:)`     — open an existing `InboxThread`
///   • `init(recipient:)`  — start a brand-new conversation with a peer
///                           (no thread on the backend yet — the first send
///                            creates it server-side via `make_thread_id`)
///
/// Both render the same UI; the only difference is whether `load()` makes a
/// round-trip to fetch existing messages.
struct ThreadView: View {
    let recipientID: Int
    let recipientName: String
    /// `nil` for a brand-new conversation (picker flow), set when opened
    /// from an existing inbox row.
    let initialThread: InboxThread?
    /// Invoked after a successful load or send so the inbox can refresh
    /// unread counts and reload the threads list.
    let onChange: () -> Void

    @Environment(AuthManager.self) private var auth
    @Environment(BadgeStore.self) private var badges

    @State private var messages: [DisplayMessage] = []
    @State private var isLoading = false
    @State private var isSending = false
    @State private var errorMessage: String?
    @State private var draft = ""
    @FocusState private var composerFocused: Bool

    // MARK: - Inits

    init(thread: InboxThread, onChange: @escaping () -> Void) {
        self.recipientID = thread.otherUser.id
        self.recipientName = thread.otherUser.displayName
        self.initialThread = thread
        self.onChange = onChange
    }

    init(recipientID: Int, recipientName: String,
         onChange: @escaping () -> Void = {}) {
        self.recipientID = recipientID
        self.recipientName = recipientName
        self.initialThread = nil
        self.onChange = onChange
    }

    private var currentUserID: Int? {
        if case .signedIn(let user) = auth.state { return user.id }
        return nil
    }

    private var hasNoMessagesYet: Bool {
        messages.allSatisfy { $0.kind == .pending } && !isLoading
    }

    // MARK: - Body

    var body: some View {
        ZStack(alignment: .bottom) {
            messageStream
        }
        .background(YH.canvas)
        .navigationTitle(recipientName)
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom, spacing: 0) {
            composer
        }
        .task(id: recipientID) { await load() }
    }

    // MARK: - Stream

    @ViewBuilder
    private var messageStream: some View {
        if messages.isEmpty && isLoading {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    ForEach(0..<4, id: \.self) { _ in YHSkeletonBlock(height: 44) }
                }
                .padding()
            }
        } else if let errorMessage, messages.isEmpty {
            YHErrorState(message: errorMessage) { Task { await load() } }
        } else if messages.isEmpty {
            emptyState
        } else {
            ScrollViewReader { proxy in
                ScrollView {
                    LazyVStack(spacing: 4) {
                        ForEach(Array(messages.enumerated()), id: \.element.id) { idx, msg in
                            let prev = idx > 0 ? messages[idx - 1] : nil
                            let next = idx < messages.count - 1 ? messages[idx + 1] : nil
                            MessageBubble(
                                message: msg,
                                isMine: isMine(msg),
                                isFirstInGroup: isFirstInGroup(msg, prev: prev),
                                isLastInGroup:  isLastInGroup(msg, next: next)
                            )
                            .id(msg.id)
                        }
                    }
                    .padding(.horizontal, YH.Space.md)
                    .padding(.vertical, YH.Space.md)
                }
                .onChange(of: messages.count) { _, _ in
                    scrollToBottom(proxy)
                }
                .onAppear { scrollToBottom(proxy, animated: false) }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: YH.Space.md) {
            ZStack {
                Circle().fill(YH.lime).frame(width: 76, height: 76)
                Text(initials(recipientName))
                    .font(.system(size: 26, weight: .bold))
                    .foregroundStyle(YH.ink)
            }
            Text("Say hi to \(recipientName)")
                .font(.yhTitle3).foregroundStyle(YH.ink)
            Text("This is the start of your conversation.")
                .font(.yhSubheadline).foregroundStyle(YH.muted)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding()
    }

    private func scrollToBottom(_ proxy: ScrollViewProxy, animated: Bool = true) {
        guard let lastID = messages.last?.id else { return }
        if animated {
            withAnimation(YH.Motion.snappy) { proxy.scrollTo(lastID, anchor: .bottom) }
        } else {
            proxy.scrollTo(lastID, anchor: .bottom)
        }
    }

    // MARK: - Composer

    private var composer: some View {
        VStack(spacing: 0) {
            Divider().overlay(YH.border)
            HStack(spacing: 8) {
                TextField("Message", text: $draft, axis: .vertical)
                    .lineLimit(1...5)
                    .focused($composerFocused)
                    .font(.system(size: 16))
                    .foregroundStyle(YH.ink)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(YH.surface)
                    .overlay(RoundedRectangle(cornerRadius: 20)
                                .strokeBorder(YH.border, lineWidth: 1))
                    .clipShape(RoundedRectangle(cornerRadius: 20))

                Button {
                    Task { await send() }
                } label: {
                    Image(systemName: isSending ? "ellipsis" : "arrow.up")
                        .font(.system(size: 16, weight: .bold))
                        .foregroundStyle(canSend ? .white : YH.muted)
                        .frame(width: 38, height: 38)
                        .background(canSend ? YH.ink : YH.surface)
                        .clipShape(Circle())
                }
                .disabled(!canSend || isSending)
                .accessibilityLabel("Send")
            }
            .padding(.horizontal, YH.Space.md)
            .padding(.vertical, YH.Space.sm)
            .background(YH.canvas)
            if let errorMessage {
                Text(errorMessage)
                    .font(.yhCaption)
                    .foregroundStyle(YH.danger)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, YH.Space.md)
                    .padding(.bottom, YH.Space.xs)
            }
        }
        .background(YH.canvas)
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    // MARK: - Actions

    private func load() async {
        // Brand-new conversation — no thread to fetch yet.
        guard let thread = initialThread else {
            return
        }
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            let payload = try await APIClient.shared.thread(threadID: thread.threadId)
            messages = payload.messages.map { DisplayMessage(message: $0) }
            badges.threadWasRead(unread: thread.unread)
            onChange()
        } catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func send() async {
        let body = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !body.isEmpty, !isSending else { return }
        guard let me = currentUserID else { return }

        let tempID = UUID()
        let pending = DisplayMessage(
            id: .pending(tempID),
            kind: .pending,
            body: body,
            createdAt: Date(),
            senderId: me
        )

        // Optimistic: drop the bubble in immediately, then replace on success.
        draft = ""
        errorMessage = nil
        isSending = true
        defer { isSending = false }
        messages.append(pending)

        do {
            let sent = try await APIClient.shared.sendMessage(
                recipientID: recipientID, body: body,
                listingID: initialThread?.listing?.id)
            // Swap the pending bubble for the real one.
            if let idx = messages.firstIndex(where: { $0.id == pending.id }) {
                messages[idx] = DisplayMessage(message: sent)
            }
            Haptics.success()
            onChange()
        } catch let error as APIError {
            messages.removeAll { $0.id == pending.id }
            draft = body            // restore so the user doesn't lose it
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            messages.removeAll { $0.id == pending.id }
            draft = body
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    // MARK: - Grouping helpers

    private func isMine(_ msg: DisplayMessage) -> Bool { msg.senderId == currentUserID }

    private func isFirstInGroup(_ msg: DisplayMessage, prev: DisplayMessage?) -> Bool {
        guard let prev else { return true }
        return prev.senderId != msg.senderId
    }

    private func isLastInGroup(_ msg: DisplayMessage, next: DisplayMessage?) -> Bool {
        guard let next else { return true }
        return next.senderId != msg.senderId
    }

    private func initials(_ name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        return parts.map { String($0.first ?? " ") }.joined().uppercased()
    }
}

// MARK: - DisplayMessage

/// Adapter wrapping a real `YHMessage` *or* a pending optimistic stub. Lets
/// the chat list render uniformly while a send is in flight.
private struct DisplayMessage: Equatable, Hashable {
    enum ID: Hashable {
        case real(Int)
        case pending(UUID)
    }

    enum Kind: Equatable {
        case real, pending
    }

    let id: ID
    let kind: Kind
    let body: String
    let createdAt: Date?
    let senderId: Int

    init(message: YHMessage) {
        self.id = .real(message.id)
        self.kind = .real
        self.body = message.body
        self.createdAt = message.createdAt
        self.senderId = message.senderId
    }

    init(id: ID, kind: Kind, body: String, createdAt: Date?, senderId: Int) {
        self.id = id
        self.kind = kind
        self.body = body
        self.createdAt = createdAt
        self.senderId = senderId
    }
}

// MARK: - MessageBubble

private struct MessageBubble: View {
    let message: DisplayMessage
    let isMine: Bool
    let isFirstInGroup: Bool
    let isLastInGroup: Bool

    var body: some View {
        HStack(alignment: .bottom, spacing: 0) {
            if isMine { Spacer(minLength: 56) }
            VStack(alignment: isMine ? .trailing : .leading, spacing: 3) {
                Text(message.body)
                    .font(.yhBody)
                    .foregroundStyle(isMine ? .white : YH.ink)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(isMine ? YH.ink : YH.surface)
                    .clipShape(BubbleShape(isMine: isMine,
                                           sharpTop: !isFirstInGroup,
                                           sharpBottom: !isLastInGroup))
                    .opacity(message.kind == .pending ? 0.6 : 1)
                if isLastInGroup, let when = message.createdAt {
                    HStack(spacing: 4) {
                        if message.kind == .pending {
                            Image(systemName: "clock")
                                .font(.system(size: 9))
                                .foregroundStyle(YH.muted)
                        }
                        Text(when.formatted(date: .omitted, time: .shortened))
                            .font(.system(size: 10, weight: .medium))
                            .foregroundStyle(YH.muted)
                    }
                }
            }
            if !isMine { Spacer(minLength: 56) }
        }
        // Tighten spacing within a group of same-sender messages.
        .padding(.top, isFirstInGroup ? 6 : 1)
    }
}

/// Asymmetric rounded shape — tail corner shrinks on the sender's side and on
/// non-edge bubbles within a group, for that classic stacked-bubble look.
private struct BubbleShape: Shape {
    let isMine: Bool
    var sharpTop: Bool = false
    var sharpBottom: Bool = false

    func path(in rect: CGRect) -> Path {
        let small: CGFloat = 6
        let big: CGFloat = 18
        let topSame = sharpTop ? small : big
        let bottomSame = sharpBottom ? small : big
        let tl = isMine ? big : topSame
        let tr = isMine ? topSame : big
        let bl = isMine ? big : (sharpBottom ? small : small)
        let br = isMine ? (sharpBottom ? small : small) : big
        // For bubbles inside a group, both opposite-corner tails are small;
        // for the last bubble in a group the sender's own bottom corner is
        // also small — that's the "tail" look.
        let blFinal = isMine ? (sharpTop ? small : big) : bl
        let brFinal = isMine ? br : (sharpTop ? small : big)
        return Path { p in
            p.move(to: CGPoint(x: tl, y: 0))
            p.addLine(to: CGPoint(x: rect.maxX - tr, y: 0))
            p.addQuadCurve(to: CGPoint(x: rect.maxX, y: tr),
                           control: CGPoint(x: rect.maxX, y: 0))
            p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - brFinal))
            p.addQuadCurve(to: CGPoint(x: rect.maxX - brFinal, y: rect.maxY),
                           control: CGPoint(x: rect.maxX, y: rect.maxY))
            p.addLine(to: CGPoint(x: blFinal, y: rect.maxY))
            p.addQuadCurve(to: CGPoint(x: 0, y: rect.maxY - blFinal),
                           control: CGPoint(x: 0, y: rect.maxY))
            p.addLine(to: CGPoint(x: 0, y: tl))
            p.addQuadCurve(to: CGPoint(x: tl, y: 0),
                           control: CGPoint(x: 0, y: 0))
        }
    }
}
