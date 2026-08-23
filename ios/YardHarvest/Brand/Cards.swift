import SwiftUI

/// Brand card surface — white on canvas, hairline border, 16pt radius.
/// Mirrors `.yh-feature-card` from the web design.
struct YHCard<Content: View>: View {
    var padding: CGFloat = YH.Space.md
    var radius: CGFloat = YH.Radius.lg
    let content: Content

    init(padding: CGFloat = YH.Space.md, radius: CGFloat = YH.Radius.lg,
         @ViewBuilder content: () -> Content) {
        self.padding = padding
        self.radius = radius
        self.content = content()
    }

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(padding)
            .background(YH.canvas)
            .overlay(
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(YH.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
}

/// Tint options for `YHBand`. Top-level so callers can reference the enum
/// without having to specify a `Content` generic parameter (which Swift
/// doesn't infer well from a computed property's return type).
enum YHBandTint { case lime, dark }

/// Full-bleed colored band used as a hero or callout. Mirrors `.yh-band-lime`
/// and `.yh-band-dark` from the web — 18pt radius, generous padding, contrast
/// foreground.
struct YHBand<Content: View>: View {
    var tint: YHBandTint = .lime
    let content: Content

    init(tint: YHBandTint = .lime, @ViewBuilder content: () -> Content) {
        self.tint = tint
        self.content = content()
    }

    var body: some View {
        content
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(YH.Space.lg)
            .foregroundStyle(tint == .dark ? .white : YH.ink)
            .background(tint == .dark ? YH.ink : YH.lime)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }
}

/// Bento-style stat tile used on the dashboard. Big number, optional sparkline
/// or symbol icon, soft secondary tint band on the right.
struct YHStatTile: View {
    let label: String
    let value: String
    var detail: String? = nil
    var systemImage: String = "circle.fill"

    var body: some View {
        YHCard(padding: YH.Space.md) {
            VStack(alignment: .leading, spacing: YH.Space.xs) {
                HStack {
                    Text(label.uppercased())
                        .font(.yhCaptionMed)
                        .tracking(0.5)
                        .foregroundStyle(YH.muted)
                    Spacer()
                    iconBadge
                }
                Text(value)
                    .font(.system(size: 28, weight: .bold))
                    .tracking(-0.6)
                    .foregroundStyle(YH.ink)
                if let detail {
                    Text(detail)
                        .font(.yhCaption)
                        .foregroundStyle(YH.muted)
                }
            }
        }
    }

    // Every stat icon gets the lime chip — one consistent look across the
    // grid, matching the Occupancy tile the rest were originally set against.
    private var iconBadge: some View {
        Image(systemName: systemImage)
            .font(.system(size: 14, weight: .semibold))
            .foregroundStyle(YH.ink)
            .padding(8)
            .background(YH.lime)
            .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
    }
}
