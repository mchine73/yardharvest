import SwiftUI
import PhotosUI

// MARK: - Models (shapes from app/api/photos_api.py)

struct GalleryPhoto: Codable, Identifiable, Equatable {
    let id: Int
    let filename: String
    let url: String
    let caption: String?
    let width: Int?
    let height: Int?
    let userId: Int
    let userName: String
    var likesCount: Int
    var likedByMe: Bool
    var commentsCount: Int
    let canDelete: Bool
    let uploadedAt: Date?

    enum CodingKeys: String, CodingKey {
        case id, filename, url, caption, width, height
        case userId = "user_id"
        case userName = "user_name"
        case likesCount = "likes_count"
        case likedByMe = "liked_by_me"
        case commentsCount = "comments_count"
        case canDelete = "can_delete"
        case uploadedAt = "uploaded_at"
    }
}

struct PhotoComment: Codable, Identifiable, Equatable {
    let id: Int
    let photoId: Int
    let userId: Int
    let userName: String
    let content: String
    let createdAt: Date?

    enum CodingKeys: String, CodingKey {
        case id
        case photoId = "photo_id"
        case userId = "user_id"
        case userName = "user_name"
        case content
        case createdAt = "created_at"
    }
}

// MARK: - Strip on the wall

/// Horizontal photo strip atop the community wall: latest photos, an add
/// button, tap-through to the full photo with its comments. Self-loads.
/// Photos are Garden Pro — a non-Pro garden gets nothing rendered at all
/// rather than an upsell taking wall space.
struct PhotoStripSection: View {
    let garden: Garden

    @State private var photos: [GalleryPhoto] = []
    @State private var proRequired = false
    @State private var loaded = false
    @State private var pickedItem: PhotosPickerItem?
    @State private var isUploading = false
    @State private var uploadError: String?
    @State private var openPhoto: GalleryPhoto?

    var body: some View {
        if proRequired {
            EmptyView()
        } else {
            VStack(alignment: .leading, spacing: YH.Space.xs) {
                HStack {
                    Text("PHOTOS")
                        .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                    Spacer()
                    if isUploading {
                        ProgressView().scaleEffect(0.8)
                    }
                }
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: YH.Space.xs) {
                        PhotosPicker(selection: $pickedItem, matching: .images) {
                            VStack(spacing: 6) {
                                Image(systemName: "camera.fill")
                                    .font(.system(size: 18, weight: .semibold))
                                Text("Add")
                                    .font(.yhCaptionMed)
                            }
                            .foregroundStyle(YH.ink)
                            .frame(width: 84, height: 84)
                            .background(YH.lime)
                            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
                        }
                        ForEach(photos.prefix(12)) { photo in
                            Button {
                                Haptics.tap()
                                openPhoto = photo
                            } label: {
                                thumb(photo)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                if let uploadError {
                    Text(uploadError).font(.yhCaption).foregroundStyle(YH.danger)
                }
            }
            .task(id: garden.id) { await load() }
            .onChange(of: pickedItem) { _, item in
                guard let item else { return }
                Task { await upload(item) }
            }
            .sheet(item: $openPhoto) { photo in
                PhotoDetailView(photo: photo) { Task { await load() } }
            }
        }
    }

    private func thumb(_ photo: GalleryPhoto) -> some View {
        AsyncImage(url: AppEnvironment.mediaURL(photo.url)) { phase in
            switch phase {
            case .success(let image):
                image.resizable().scaledToFill()
            case .failure:
                Image(systemName: "photo")
                    .foregroundStyle(YH.muted)
            default:
                YHSkeletonBlock(height: 84)
            }
        }
        .frame(width: 84, height: 84)
        .background(YH.surface)
        .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
        .overlay(alignment: .bottomTrailing) {
            if photo.commentsCount > 0 {
                Image(systemName: "bubble.left.fill")
                    .font(.system(size: 9))
                    .foregroundStyle(.white)
                    .padding(5)
            }
        }
    }

    private func load() async {
        do {
            let feed = try await APIClient.shared.listGardenPhotos(gardenID: garden.id)
            photos = feed.photos
            proRequired = feed.proRequired ?? false
        } catch { /* strip is decorative; the wall still works without it */ }
        loaded = true
    }

    private func upload(_ item: PhotosPickerItem) async {
        isUploading = true
        uploadError = nil
        defer { isUploading = false; pickedItem = nil }
        do {
            guard let raw = try await item.loadTransferable(type: Data.self),
                  let image = UIImage(data: raw),
                  let jpeg = image.jpegData(compressionQuality: 0.85) else {
                uploadError = "Couldn't read that image — try a different one."
                return
            }
            _ = try await APIClient.shared.uploadGardenPhoto(
                gardenID: garden.id, jpegData: jpeg, caption: "")
            Haptics.success()
            await load()
        } catch let error as APIError {
            uploadError = error.errorDescription
            Haptics.error()
        } catch {
            uploadError = error.localizedDescription
            Haptics.error()
        }
    }
}

// MARK: - Photo detail

/// One photo, full width, with its likes and comment thread.
struct PhotoDetailView: View {
    let onChange: () -> Void

    @Environment(\.dismiss) private var dismiss
    @State private var photo: GalleryPhoto
    @State private var comments: [PhotoComment] = []
    @State private var commentsLoaded = false
    @State private var composerText = ""
    @State private var isPosting = false
    @State private var errorMessage: String?
    @State private var confirmingDelete = false

    init(photo: GalleryPhoto, onChange: @escaping () -> Void) {
        self.onChange = onChange
        _photo = State(initialValue: photo)
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: YH.Space.md) {
                    AsyncImage(url: AppEnvironment.mediaURL(photo.url)) { phase in
                        switch phase {
                        case .success(let image):
                            image.resizable().scaledToFit()
                        case .failure:
                            YHCard { Label("Couldn't load the photo.", systemImage: "photo") }
                        default:
                            YHSkeletonBlock(height: 260)
                        }
                    }
                    .frame(maxWidth: .infinity)
                    .background(YH.surface)
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg, style: .continuous))

                    HStack(spacing: 10) {
                        YHAvatar(name: photo.userName, size: 32)
                        VStack(alignment: .leading, spacing: 0) {
                            Text(photo.userName).font(.yhBodyMedium).foregroundStyle(YH.ink)
                            if let at = photo.uploadedAt {
                                Text(at.formatted(.relative(presentation: .named)))
                                    .font(.yhCaption).foregroundStyle(YH.muted)
                            }
                        }
                        Spacer()
                        Button {
                            Task { await toggleLike() }
                        } label: {
                            HStack(spacing: 4) {
                                Image(systemName: photo.likedByMe ? "heart.fill" : "heart")
                                    .foregroundStyle(photo.likedByMe ? YH.danger : YH.muted)
                                if photo.likesCount > 0 {
                                    Text("\(photo.likesCount)").foregroundStyle(YH.muted)
                                }
                            }
                            .font(.system(size: 15, weight: .medium))
                        }
                    }
                    if let caption = photo.caption, !caption.isEmpty {
                        Text(caption).font(.yhSubheadline).foregroundStyle(YH.ink)
                    }

                    Divider().overlay(YH.border)
                    Text("COMMENTS")
                        .font(.yhCaptionMed).tracking(0.6).foregroundStyle(YH.muted)
                    if !commentsLoaded {
                        YHSkeletonBlock(height: 40)
                    } else if comments.isEmpty {
                        Text("No comments yet.")
                            .font(.yhSubheadline).foregroundStyle(YH.muted)
                    }
                    ForEach(comments) { comment in
                        HStack(alignment: .top, spacing: 8) {
                            YHAvatar(name: comment.userName, size: 26)
                            VStack(alignment: .leading, spacing: 2) {
                                HStack(spacing: 6) {
                                    Text(comment.userName)
                                        .font(.yhCaptionMed).foregroundStyle(YH.ink)
                                    if let at = comment.createdAt {
                                        Text(at.formatted(.relative(presentation: .named)))
                                            .font(.yhCaption).foregroundStyle(YH.muted)
                                    }
                                }
                                Text(comment.content)
                                    .font(.yhSubheadline).foregroundStyle(YH.ink)
                            }
                            Spacer(minLength: 0)
                        }
                    }
                    if let errorMessage {
                        Text(errorMessage).font(.yhCaption).foregroundStyle(YH.danger)
                    }
                }
                .padding(YH.Space.md)
            }
            .background(YH.canvas)
            .navigationTitle("Photo")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button("Close") { dismiss() }.foregroundStyle(YH.muted)
                }
                if photo.canDelete {
                    ToolbarItem(placement: .topBarTrailing) {
                        Button {
                            confirmingDelete = true
                        } label: {
                            Image(systemName: "trash").foregroundStyle(YH.danger)
                        }
                    }
                }
            }
            .safeAreaInset(edge: .bottom) { composer }
            .task { await loadComments() }
            .confirmationDialog("Delete this photo?",
                                isPresented: $confirmingDelete,
                                titleVisibility: .visible) {
                Button("Delete Photo", role: .destructive) { Task { await remove() } }
            } message: {
                Text("Its comments go with it. This can't be undone.")
            }
        }
    }

    private var composer: some View {
        HStack(spacing: YH.Space.xs) {
            TextField("Add a comment…", text: $composerText, axis: .vertical)
                .lineLimit(1...3)
                .font(.system(size: 15))
                .padding(.horizontal, 12)
                .padding(.vertical, 9)
                .background(YH.surface)
                .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg, style: .continuous))
            Button {
                Task { await post() }
            } label: {
                Group {
                    if isPosting { ProgressView().tint(YH.ink) }
                    else {
                        Image(systemName: "arrow.up")
                            .font(.system(size: 14, weight: .bold))
                            .foregroundStyle(YH.ink)
                    }
                }
                .frame(width: 34, height: 34)
                .background(YH.lime)
                .clipShape(Circle())
            }
            .disabled(isPosting
                      || composerText.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
        .padding(.horizontal, YH.Space.md)
        .padding(.vertical, YH.Space.sm)
        .background(YH.canvas)
        .overlay(alignment: .top) { Divider().overlay(YH.border) }
    }

    private func loadComments() async {
        comments = (try? await APIClient.shared.listPhotoComments(photoID: photo.id)) ?? []
        commentsLoaded = true
    }

    private func toggleLike() async {
        do {
            let result = try await APIClient.shared.togglePhotoLike(photoID: photo.id)
            photo.likedByMe = result.liked
            photo.likesCount = result.likesCount
            Haptics.tap()
            onChange()
        } catch { /* low stakes */ }
    }

    private func post() async {
        let text = composerText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !isPosting else { return }
        isPosting = true
        errorMessage = nil
        defer { isPosting = false }
        do {
            let comment = try await APIClient.shared.postPhotoComment(
                photoID: photo.id, content: text)
            comments.append(comment)
            composerText = ""
            photo.commentsCount += 1
            Haptics.success()
            onChange()
        } catch let error as APIError {
            errorMessage = error.errorDescription
            Haptics.error()
        } catch {
            errorMessage = error.localizedDescription
            Haptics.error()
        }
    }

    private func remove() async {
        do {
            try await APIClient.shared.deleteGardenPhoto(photoID: photo.id)
            Haptics.success()
            onChange()
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
