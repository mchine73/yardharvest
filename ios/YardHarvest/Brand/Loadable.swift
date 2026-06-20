import SwiftUI

/// Canonical four-state list shell: skeleton-while-loading, error-with-retry,
/// empty placeholder, or real content. Replaces the same hand-rolled
/// `Group { if isEmpty && isLoading { … } else if isEmpty, let errorMessage { … }
/// else if isEmpty { YHEmpty(…) } else { … } }` block that appears in ~10
/// list views across the app.
///
/// Usage:
/// ```swift
/// YHLoadable(isLoading: isLoading,
///            isEmpty: items.isEmpty,
///            errorMessage: errorMessage,
///            onRetry: { await load() }) {
///     YHEmpty(systemImage: "calendar", title: "No events yet",
///             message: "Volunteer workdays will show up here.")
/// } content: {
///     ScrollView { … }
/// }
/// ```
///
/// `skeletonCards` and `skeletonRows` tune the placeholder density to match
/// the real list's row weight (e.g. AnnouncementCard is 3 rows, InboxRow is
/// 2). Padding around the skeleton uses `YH.Space.md` to match every
/// existing call site.
struct YHLoadable<Empty: View, Content: View>: View {
    let isLoading: Bool
    let isEmpty: Bool
    let errorMessage: String?
    let onRetry: () async -> Void
    var skeletonCards: Int = 4
    var skeletonRows: Int = 2
    @ViewBuilder let empty: () -> Empty
    @ViewBuilder let content: () -> Content

    var body: some View {
        if isEmpty && isLoading {
            ScrollView {
                VStack(spacing: YH.Space.sm) {
                    ForEach(0..<skeletonCards, id: \.self) { _ in
                        YHSkeletonCard(rows: skeletonRows)
                    }
                }
                .padding(YH.Space.md)
            }
        } else if isEmpty, let errorMessage {
            YHErrorState(message: errorMessage) {
                Task { await onRetry() }
            }
        } else if isEmpty {
            empty()
        } else {
            content()
        }
    }
}
