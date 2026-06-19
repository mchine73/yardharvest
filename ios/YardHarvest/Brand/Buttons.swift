import SwiftUI

/// The three canonical YardHarvest button variants from the web design
/// system: `.dark` (ink background, white text — primary CTA), `.ghost`
/// (white, ink border — secondary), and `.lime` (lime background, ink text —
/// playful accent CTA).
enum YHButtonStyle: Equatable {
    case dark, ghost, lime
}

struct YHButton: View {
    let title: String
    var systemImage: String? = nil
    var style: YHButtonStyle = .dark
    var isLoading: Bool = false
    var fullWidth: Bool = true
    let action: () -> Void

    @State private var pressed = false

    var body: some View {
        Button {
            Haptics.tap()
            action()
        } label: {
            HStack(spacing: YH.Space.xs) {
                if isLoading {
                    ProgressView().tint(foreground)
                } else {
                    if let systemImage {
                        Image(systemName: systemImage)
                            .font(.system(size: 15, weight: .semibold))
                    }
                    Text(title).font(.system(size: 16, weight: .semibold))
                }
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 14)
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .foregroundStyle(foreground)
            .background(background)
            .overlay(
                RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous)
                    .strokeBorder(borderColor, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: YH.Radius.md, style: .continuous))
            .scaleEffect(pressed ? 0.985 : 1)
            .animation(YH.Motion.snappy, value: pressed)
        }
        .buttonStyle(.plain)
        .disabled(isLoading)
        ._onButtonGesture { pressed = $0 } perform: {}
    }

    private var foreground: Color {
        switch style {
        case .dark: return .white
        case .ghost: return YH.ink
        case .lime: return YH.ink
        }
    }

    private var background: Color {
        switch style {
        case .dark: return YH.ink
        case .ghost: return YH.canvas
        case .lime: return YH.lime
        }
    }

    private var borderColor: Color {
        switch style {
        case .dark: return YH.ink
        case .ghost: return YH.border
        case .lime: return YH.lime
        }
    }
}

// Internal helper that mirrors SwiftUI's private `_onButtonGesture` for press
// state; falls back gracefully on platforms where it's missing.
private extension View {
    func _onButtonGesture(_ pressing: @escaping (Bool) -> Void, perform: @escaping () -> Void) -> some View {
        self.simultaneousGesture(
            DragGesture(minimumDistance: 0)
                .onChanged { _ in pressing(true) }
                .onEnded { _ in pressing(false) }
        )
    }
}

#Preview("Buttons") {
    VStack(spacing: 12) {
        YHButton(title: "Sign In", style: .dark) {}
        YHButton(title: "Cancel", style: .ghost) {}
        YHButton(title: "Log Harvest", systemImage: "basket.fill", style: .lime) {}
        YHButton(title: "Saving…", isLoading: true) {}
    }
    .padding()
    .background(YH.canvas)
}
