import SwiftUI

/// Minimal splash — sunflower mark with a gentle entrance animation while
/// the auth bootstrap fires. Uses `phaseAnimator` for a sequenced reveal.
struct SplashView: View {
    @State private var didAppear = false

    var body: some View {
        ZStack {
            YH.canvas.ignoresSafeArea()
            VStack(spacing: YH.Space.lg) {
                YHLogo(size: 104)
                    .scaleEffect(didAppear ? 1 : 0.85)
                    .opacity(didAppear ? 1 : 0)
                Text("YardHarvest")
                    .font(.yhTitle2)
                    .tracking(-0.4)
                    .foregroundStyle(YH.ink)
                    .opacity(didAppear ? 1 : 0)
                    .offset(y: didAppear ? 0 : 8)
                ProgressView()
                    .tint(YH.ink)
                    .opacity(didAppear ? 1 : 0)
            }
        }
        .onAppear {
            withAnimation(YH.Motion.bounce) { didAppear = true }
        }
    }
}

#Preview { SplashView() }
