import SwiftUI

/// Pill-shaped status indicator. Mirrors the web's chip treatment — light
/// surface background with darker text. Use a custom `tint` to override.
struct YHPill: View {
    let text: String
    var systemImage: String? = nil
    var tint: Color = YH.ink
    var background: Color? = nil

    var body: some View {
        HStack(spacing: 4) {
            if let systemImage {
                Image(systemName: systemImage).font(.system(size: 11, weight: .semibold))
            }
            Text(text).font(.system(size: 12, weight: .semibold))
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 4)
        .foregroundStyle(tint)
        .background(background ?? tint.opacity(0.12))
        .clipShape(Capsule())
    }
}

/// "Lime-highlight" inline text marker — mirrors `.yh-highlight` from the
/// web. Use as a Text view to wrap a phrase you want to call out.
struct YHHighlight: View {
    let text: String
    var body: some View {
        Text(text)
            .padding(.horizontal, 4)
            .padding(.vertical, 1)
            .background(YH.lime)
            .foregroundStyle(YH.ink)
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

/// Lime-branded badge — outer pill + inner lime number. Mirrors `.yh-badge-lime`.
struct YHLimeBadge: View {
    let label: String
    let value: String

    var body: some View {
        HStack(spacing: 6) {
            Text(value)
                .font(.system(size: 12, weight: .semibold))
                .padding(.horizontal, 9)
                .padding(.vertical, 3)
                .background(YH.lime)
                .foregroundStyle(YH.ink)
                .clipShape(Capsule())
            Text(label)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(YH.ink)
        }
        .padding(.trailing, 10)
        .background(YH.surface)
        .clipShape(Capsule())
    }
}
