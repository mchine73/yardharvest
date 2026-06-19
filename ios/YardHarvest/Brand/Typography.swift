import SwiftUI

/// Typography scale tuned to match the web's Onest treatment (semibold
/// headlines with tight tracking). We use San Francisco — Apple's system
/// typeface — at matching weights instead of bundling a custom font, which
/// keeps launch fast and is more iOS-native. The `tracking()` modifier
/// approximates Onest's `-0.025em` letter spacing on display sizes.
extension Font {
    static var yhDisplay:     Font { .system(size: 40, weight: .bold,   design: .default) }
    static var yhTitle:       Font { .system(size: 30, weight: .bold,   design: .default) }
    static var yhTitle2:      Font { .system(size: 24, weight: .bold,   design: .default) }
    static var yhTitle3:      Font { .system(size: 20, weight: .semibold, design: .default) }
    static var yhHeadline:    Font { .system(size: 17, weight: .semibold, design: .default) }
    static var yhBody:        Font { .system(size: 16, weight: .regular,  design: .default) }
    static var yhBodyMedium:  Font { .system(size: 16, weight: .medium,   design: .default) }
    static var yhSubheadline: Font { .system(size: 14, weight: .regular,  design: .default) }
    static var yhCaption:     Font { .system(size: 12, weight: .regular,  design: .default) }
    static var yhCaptionMed:  Font { .system(size: 12, weight: .semibold, design: .default) }
    static var yhMono:        Font { .system(size: 14, weight: .regular,  design: .monospaced) }
}

extension Text {
    /// Apply tight tracking on display-sized text — mirrors the web's `-0.025em`.
    func yhTitleTracking() -> Text { self.tracking(-0.6) }
}

/// View modifier that applies the brand's display treatment in one call.
struct YHDisplayStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .font(.yhDisplay)
            .tracking(-0.8)
            .foregroundStyle(YH.ink)
    }
}

extension View {
    func yhDisplay() -> some View { modifier(YHDisplayStyle()) }
}
