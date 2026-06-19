import SwiftUI

/// Plays the same lime-circle + symbol-bounce intro as `YHEmpty`, then morphs
/// into the wrapped content. Use it to wrap the "we have content" branch of
/// list screens so they reveal with the same delight as the empty-state.
///
/// The intro plays **once per `id` per app session** (tracked in a static
/// Set) so re-entering a screen via tab-switch or back-nav doesn't replay it.
/// Pass a stable id like `"tools-\(garden.id)"` so each garden gets its own
/// first-visit moment.
struct YHContentReveal<Content: View>: View {
    let systemImage: String
    /// Stable identifier — drives both reveal-once tracking and `task(id:)`.
    let id: String
    /// Optional sub-label shown beneath the icon during the intro.
    let caption: String?
    @ViewBuilder let content: () -> Content

    @State private var phase: Phase

    enum Phase { case intro, content }

    init(systemImage: String, id: String, caption: String? = nil,
         @ViewBuilder content: @escaping () -> Content) {
        self.systemImage = systemImage
        self.id = id
        self.caption = caption
        self.content = content
        _phase = State(initialValue: YHRevealMemory.shared.contains(id) ? .content : .intro)
    }

    var body: some View {
        ZStack {
            switch phase {
            case .intro:
                intro
                    .transition(.asymmetric(
                        insertion: .opacity,
                        removal: .opacity.combined(with: .scale(scale: 0.55))
                    ))
            case .content:
                content()
                    .transition(.asymmetric(
                        insertion: .opacity.combined(with: .scale(scale: 0.97)),
                        removal: .opacity
                    ))
            }
        }
        .task(id: id) {
            if YHRevealMemory.shared.contains(id) {
                if phase != .content { phase = .content }
                return
            }
            if phase != .intro { phase = .intro }
            try? await Task.sleep(nanoseconds: 800_000_000)   // ~0.8s hero hold
            YHRevealMemory.shared.insert(id)
            withAnimation(.spring(response: 0.45, dampingFraction: 0.78)) {
                phase = .content
            }
        }
    }

    private var intro: some View {
        VStack(spacing: YH.Space.md) {
            Image(systemName: systemImage)
                .font(.system(size: 42, weight: .light))
                .symbolEffect(.bounce.up.byLayer, options: .nonRepeating)
                .foregroundStyle(YH.ink)
                .padding(20)
                .background(YH.lime)
                .clipShape(Circle())
            if let caption {
                Text(caption)
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.muted)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Non-generic session memory for `YHContentReveal` — tracks which screens
/// have already played their intro this app session. Static storage isn't
/// allowed on generic types, hence this small wrapper.
@MainActor
final class YHRevealMemory {
    static let shared = YHRevealMemory()
    private var ids: Set<String> = []

    func contains(_ id: String) -> Bool { ids.contains(id) }
    func insert(_ id: String) { ids.insert(id) }
}
