import SwiftUI

struct AnnouncementsView: View {
    let garden: Garden

    @State private var items: [Announcement] = []
    @State private var isLoading = false
    @State private var errorMessage: String?
    @State private var showingCompose = false

    var body: some View {
        Group {
            if items.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<3, id: \.self) { _ in YHSkeletonCard(rows: 3) }
                    }
                    .padding(YH.Space.md)
                }
            } else if items.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await load() } }
            } else if items.isEmpty {
                YHEmpty(systemImage: "megaphone",
                        title: "Nothing posted yet",
                        message: "Tap + to share an update with members.",
                        actionTitle: "Post Announcement") { showingCompose = true }
            } else {
                YHContentReveal(systemImage: "megaphone",
                                id: "announcements-\(garden.id)",
                                caption: "Fresh from your garden") {
                    ScrollView {
                        VStack(spacing: YH.Space.sm) {
                            ForEach(items) { ann in
                                AnnouncementCard(announcement: ann)
                            }
                        }
                        .padding(YH.Space.md)
                    }
                    .refreshable { await load(showSpinner: false) }
                }
            }
        }
        .toolbar {
            ToolbarItem(placement: .topBarTrailing) {
                Button {
                    Haptics.tap()
                    showingCompose = true
                } label: {
                    Image(systemName: "square.and.pencil")
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundStyle(YH.ink)
                }
            }
        }
        .sheet(isPresented: $showingCompose) {
            ComposeAnnouncementView(garden: garden) { newItem in
                items.insert(newItem, at: 0)
            }
        }
        .task(id: garden.id) { await load() }
    }

    private func load(showSpinner: Bool = true) async {
        if showSpinner { isLoading = true }
        errorMessage = nil
        defer { isLoading = false }
        do { items = try await APIClient.shared.listAnnouncements(gardenID: garden.id) }
        catch let e as APIError { errorMessage = e.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }
}

private struct AnnouncementCard: View {
    let announcement: Announcement

    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    if announcement.pinned == true {
                        Image(systemName: "pin.fill")
                            .font(.caption2).foregroundStyle(YH.ink)
                            .padding(5).background(YH.lime).clipShape(Circle())
                    }
                    Text(announcement.title)
                        .font(.yhTitle3)
                        .foregroundStyle(YH.ink)
                    Spacer()
                }
                Text(announcement.body)
                    .font(.yhBody)
                    .foregroundStyle(YH.ink.opacity(0.85))
                HStack(spacing: 8) {
                    if let author = announcement.authorName {
                        Label(author, systemImage: "person.fill")
                            .labelStyle(.titleOnly)
                            .font(.yhCaption)
                            .foregroundStyle(YH.muted)
                    }
                    if let when = announcement.createdAt {
                        Text("·").font(.yhCaption).foregroundStyle(YH.muted)
                        Text(when.formatted(.relative(presentation: .named)))
                            .font(.yhCaption).foregroundStyle(YH.muted)
                    }
                }
            }
        }
    }
}

struct ComposeAnnouncementView: View {
    let garden: Garden
    let onCreate: (Announcement) -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var body_ = ""
    @State private var sendEmail = true
    @State private var sendSMS = false
    @State private var isPosting = false
    @State private var errorMessage: String?

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    field(label: "Title", text: $title, isMultiline: false)
                    field(label: "Message", text: $body_, isMultiline: true)
                    YHCard {
                        VStack(spacing: 12) {
                            Toggle(isOn: $sendEmail) {
                                Label("Send email", systemImage: "envelope.fill")
                                    .font(.yhBodyMedium)
                            }
                            .tint(YH.ink)
                            Toggle(isOn: $sendSMS) {
                                Label("Send SMS", systemImage: "message.fill")
                                    .font(.yhBodyMedium)
                            }
                            .tint(YH.ink)
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).font(.yhSubheadline).foregroundStyle(YH.danger)
                    }
                    YHButton(title: "Post", systemImage: "paperplane.fill",
                             style: .dark, isLoading: isPosting) {
                        Task { await submit() }
                    }
                    .disabled(title.isEmpty || body_.isEmpty)
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("New Announcement")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Cancel") { dismiss() }
                }
            }
        }
    }

    @ViewBuilder
    private func field(label: String, text: Binding<String>, isMultiline: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.yhCaptionMed).foregroundStyle(YH.muted)
            Group {
                if isMultiline {
                    TextEditor(text: text)
                        .scrollContentBackground(.hidden)
                        .frame(minHeight: 140, alignment: .topLeading)
                } else {
                    TextField("", text: text)
                }
            }
            .font(.system(size: 17, weight: .regular))
            .foregroundStyle(YH.ink)
            .padding(12)
            .background(YH.surface)
            .overlay(
                RoundedRectangle(cornerRadius: YH.Radius.md)
                    .strokeBorder(YH.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md))
        }
    }

    private func submit() async {
        isPosting = true; errorMessage = nil
        defer { isPosting = false }
        do {
            let ann = try await APIClient.shared.createAnnouncement(
                gardenID: garden.id, title: title, body: body_,
                sendEmail: sendEmail, sendSMS: sendSMS)
            onCreate(ann)
            Haptics.success()
            dismiss()
        } catch let e as APIError { errorMessage = e.errorDescription; Haptics.error() }
        catch { errorMessage = error.localizedDescription; Haptics.error() }
    }
}
