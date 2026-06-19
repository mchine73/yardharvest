import SwiftUI

/// Animated shimmer for placeholder skeletons. Used while data loads — feels
/// much more modern than a spinner. Built on `phaseAnimator` for smooth
/// looping motion.
struct YHShimmer: ViewModifier {
    @State private var phase: CGFloat = -1

    func body(content: Content) -> some View {
        content
            .overlay(
                GeometryReader { proxy in
                    LinearGradient(
                        colors: [.clear, .white.opacity(0.55), .clear],
                        startPoint: .leading, endPoint: .trailing
                    )
                    .frame(width: proxy.size.width * 1.6)
                    .offset(x: phase * proxy.size.width * 1.6)
                    .blendMode(.overlay)
                }
            )
            .mask(content)
            .onAppear {
                withAnimation(.linear(duration: 1.4).repeatForever(autoreverses: false)) {
                    phase = 1
                }
            }
    }
}

extension View {
    func yhShimmer() -> some View { modifier(YHShimmer()) }
}

/// Generic skeleton block — a rounded gray rect that shimmers.
struct YHSkeletonBlock: View {
    var height: CGFloat = 14
    var radius: CGFloat = 6

    var body: some View {
        RoundedRectangle(cornerRadius: radius, style: .continuous)
            .fill(YH.surface)
            .frame(height: height)
            .yhShimmer()
    }
}

/// Skeleton card scaffold — use as a placeholder for any list-row or tile.
struct YHSkeletonCard: View {
    var rows: Int = 2
    var body: some View {
        YHCard {
            VStack(alignment: .leading, spacing: YH.Space.sm) {
                YHSkeletonBlock(height: 16)
                ForEach(0..<rows, id: \.self) { _ in
                    YHSkeletonBlock(height: 12)
                }
            }
        }
    }
}

/// Skeleton bento grid used while the dashboard loads.
struct YHSkeletonBento: View {
    var body: some View {
        VStack(spacing: YH.Space.sm) {
            HStack(spacing: YH.Space.sm) { tile; tile }
            HStack(spacing: YH.Space.sm) { tile; tile }
            YHSkeletonCard(rows: 3)
            YHSkeletonCard(rows: 2)
        }
    }
    private var tile: some View {
        YHCard {
            VStack(alignment: .leading, spacing: 10) {
                YHSkeletonBlock(height: 10)
                YHSkeletonBlock(height: 22).frame(width: 80)
                YHSkeletonBlock(height: 10).frame(width: 60)
            }
        }
    }
}
