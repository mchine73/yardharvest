import SwiftUI

/// Small surface-gray rounded square wrapping an SF Symbol. The standard
/// prefix icon used on list rows, card headers, and section labels across
/// the app. Replaces ~6 hand-rolled `Image(systemName:).frame.background.clipShape`
/// stacks.
struct YHIconTile: View {
    let systemImage: String
    var size: CGFloat = 28
    var symbolSize: CGFloat? = nil
    var background: Color = YH.surface
    var foreground: Color = YH.ink

    var body: some View {
        Image(systemName: systemImage)
            .font(.system(size: symbolSize ?? size * 0.5, weight: .semibold))
            .foregroundStyle(foreground)
            .frame(width: size, height: size)
            .background(background)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.29, style: .continuous))
    }
}

#Preview {
    HStack(spacing: 12) {
        YHIconTile(systemImage: "bell.fill")
        YHIconTile(systemImage: "wave.3.right", size: 44, background: YH.lime)
        YHIconTile(systemImage: "wrench.adjustable.fill", size: 56, background: YH.ink, foreground: .white)
    }
    .padding()
}
