import SwiftUI

/// The YardHarvest sunflower mark. The forest-green tile and white petals are
/// preserved historical brand equity even after the redesign; we just place
/// them on the new lime/ink canvases.
struct YHLogo: View {
    var size: CGFloat = 72

    var body: some View {
        Image("Sunflower")
            .resizable()
            .scaledToFit()
            .frame(width: size, height: size)
            .clipShape(RoundedRectangle(cornerRadius: size * 0.22, style: .continuous))
    }
}

/// Wordmark — logo + "YardHarvest" set in tight semibold ink.
struct YHWordmark: View {
    var size: CGFloat = 28
    var body: some View {
        HStack(spacing: 8) {
            YHLogo(size: size)
            Text("YardHarvest")
                .font(.system(size: size * 0.6, weight: .semibold))
                .tracking(-0.4)
                .foregroundStyle(YH.ink)
        }
    }
}

#Preview {
    VStack(spacing: 24) {
        YHLogo(size: 128)
        YHWordmark(size: 32)
    }
    .padding()
    .background(YH.canvas)
}
