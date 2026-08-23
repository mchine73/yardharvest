import SwiftUI

/// Discover gardens you can join — paginated, searchable. Each row is the
/// same photo-forward `GardenCard` used elsewhere in the app, tapping it
/// drills into `GardenDetailView` where you can take a plot or join the
/// waitlist.
struct BrowseGardensView: View {
    @Environment(GardenStore.self) private var store

    @State private var gardens: [Garden] = []
    @State private var search = ""
    @State private var debouncedSearch = ""
    @State private var page = 1
    @State private var totalPages = 1
    @State private var isLoading = false
    @State private var isPagingMore = false
    @State private var errorMessage: String?
    @State private var searchTask: Task<Void, Never>?

    var body: some View {
        Group {
            if gardens.isEmpty && isLoading {
                ScrollView {
                    VStack(spacing: YH.Space.sm) {
                        ForEach(0..<4, id: \.self) { _ in
                            YHSkeletonBlock(height: 116, radius: YH.Radius.lg)
                        }
                    }
                    .padding(YH.Space.md)
                }
            } else if gardens.isEmpty, let errorMessage {
                YHErrorState(message: errorMessage) { Task { await reload() } }
            } else if gardens.isEmpty {
                YHEmpty(systemImage: "magnifyingglass",
                        title: "No gardens found",
                        message: search.isEmpty
                            ? "There are no public gardens to show right now."
                            : "Nothing matched “\(search)”. Try a different search.")
            } else {
                ScrollView {
                    LazyVStack(spacing: YH.Space.sm) {
                        ForEach(gardens) { garden in
                            // View-destination link — value-based navigation
                            // from a pushed view duplicate-pushes on this
                            // stack (see the note atop PaymentHubView).
                            NavigationLink {
                                GardenDetailView(gardenID: garden.id)
                            } label: {
                                GardenCard(garden: garden, compact: true)
                            }
                            .buttonStyle(.plain)
                            .onAppear {
                                if garden.id == gardens.last?.id, page < totalPages {
                                    Task { await loadMore() }
                                }
                            }
                        }
                        if isPagingMore {
                            ProgressView().padding(.vertical, YH.Space.md)
                        }
                    }
                    .padding(YH.Space.md)
                }
                .refreshable { await reload() }
            }
        }
        .background(YH.canvas)
        .navigationTitle("Find a Garden")
        .navigationBarTitleDisplayMode(.inline)
        .searchable(text: $search, prompt: "Search by name, city, or description")
        .onChange(of: search) { _, newValue in
            searchTask?.cancel()
            searchTask = Task {
                try? await Task.sleep(nanoseconds: 320_000_000)
                if !Task.isCancelled {
                    debouncedSearch = newValue
                    await reload()
                }
            }
        }
        .task { if gardens.isEmpty { await reload() } }
    }

    private func reload() async {
        isLoading = true
        errorMessage = nil
        page = 1
        defer { isLoading = false }
        do {
            let payload = try await APIClient.shared.browseGardens(page: 1, search: debouncedSearch)
            gardens = payload.gardens
            totalPages = payload.pages
        } catch let error as APIError { errorMessage = error.errorDescription }
        catch { errorMessage = error.localizedDescription }
    }

    private func loadMore() async {
        guard !isPagingMore, page < totalPages else { return }
        isPagingMore = true
        defer { isPagingMore = false }
        do {
            let next = page + 1
            let payload = try await APIClient.shared.browseGardens(page: next, search: debouncedSearch)
            gardens.append(contentsOf: payload.gardens)
            page = next
            totalPages = payload.pages
        } catch {
            // Quietly fail paging — the user can pull-to-refresh if needed.
        }
    }
}
