import SwiftUI

/// Circular avatar — lime fill with ink initials, or a system symbol when
/// no name is available. Replaces the seven hand-rolled inline ZStacks
/// that were doing the same dance across the inbox / members / dues views.
struct YHAvatar: View {
    enum Source {
        case name(String)
        case symbol(String)
    }

    let source: Source
    var size: CGFloat = 44
    var background: Color = YH.lime
    var foreground: Color = YH.ink

    /// Convenience: most callers just want `YHAvatar(name: "...")`.
    init(name: String, size: CGFloat = 44,
         background: Color = YH.lime, foreground: Color = YH.ink) {
        self.source = .name(name)
        self.size = size
        self.background = background
        self.foreground = foreground
    }

    init(systemImage: String, size: CGFloat = 44,
         background: Color = YH.lime, foreground: Color = YH.ink) {
        self.source = .symbol(systemImage)
        self.size = size
        self.background = background
        self.foreground = foreground
    }

    init(source: Source, size: CGFloat = 44,
         background: Color = YH.lime, foreground: Color = YH.ink) {
        self.source = source
        self.size = size
        self.background = background
        self.foreground = foreground
    }

    var body: some View {
        ZStack {
            Circle().fill(background)
            content
                .foregroundStyle(foreground)
        }
        .frame(width: size, height: size)
    }

    @ViewBuilder
    private var content: some View {
        switch source {
        case .name(let name):
            Text(YHAvatar.initials(for: name))
                .font(.system(size: size * 0.36, weight: .bold))
        case .symbol(let symbol):
            Image(systemName: symbol)
                .font(.system(size: size * 0.42, weight: .semibold))
        }
    }

    /// Up-to-two-character initials. Public so callers that need *just* the
    /// initials (e.g. text fields) can share the same heuristic.
    static func initials(for name: String) -> String {
        let parts = name.split(separator: " ").prefix(2)
        let chars = parts.map { String($0.first ?? Character(" ")) }.joined()
        return chars.isEmpty ? "?" : chars.uppercased()
    }
}

#Preview {
    VStack(spacing: 16) {
        YHAvatar(name: "Far West Omaha", size: 64)
        YHAvatar(name: "James Goodman")
        YHAvatar(systemImage: "leaf.fill")
    }
    .padding()
}
