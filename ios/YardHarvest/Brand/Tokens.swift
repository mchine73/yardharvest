import SwiftUI

/// Design tokens that mirror the YardHarvest "lime / Onest" web system
/// (see `frontend/src/App.css` and `app/static/css/yh-tokens.css`).
///
/// Values are read from the asset catalog so dark-mode adaptation can be
/// added later by editing the color sets, no code changes.
enum YH {

    // MARK: - Palette

    /// Near-black `#22242a` — primary text, dark CTAs, the new "brand color".
    static let ink         = Color("Ink")
    /// Chartreuse `#e3ff8f` — single accent. Buttons, highlights, badges.
    static let lime        = Color("Lime")
    /// Pale lime `#edf7cf` — soft surfaces, hover wash.
    static let limeSoft    = Color("LimeSoft")
    /// White `#ffffff` — canvas.
    static let canvas      = Color("Canvas")
    /// Subtle `#f2f3f3` — recessed surfaces.
    static let surface     = Color("Surface")
    /// Subtler `#f7f8f8`.
    static let surfaceAlt  = Color("SurfaceAlt")
    /// Hairline `#e5e6e6`.
    static let border      = Color("Border")
    /// Muted gray `#6b6e76` — secondary text.
    static let muted       = Color("Muted")
    /// Forest `#1b4d3e` — preserved for the sunflower logo backdrop only.
    static let forest      = Color("Forest")

    /// Semantic colors derived from the palette.
    static let textPrimary    = ink
    static let textSecondary  = muted
    static let success        = Color(red: 0.10, green: 0.62, blue: 0.32)
    static let warning        = Color(red: 0.85, green: 0.60, blue: 0.17)  // brand gold
    static let danger         = Color(red: 0.88, green: 0.34, blue: 0.31)

    // MARK: - Radius

    enum Radius {
        static let sm: CGFloat = 8
        static let md: CGFloat = 12
        static let lg: CGFloat = 16
        static let xl: CGFloat = 20
        static let pill: CGFloat = 999
    }

    // MARK: - Spacing

    enum Space {
        static let xxs: CGFloat = 4
        static let xs:  CGFloat = 8
        static let sm:  CGFloat = 12
        static let md:  CGFloat = 16
        static let lg:  CGFloat = 20
        static let xl:  CGFloat = 28
        static let xxl: CGFloat = 40
    }

    // MARK: - Motion

    enum Motion {
        static let snappy     = Animation.spring(response: 0.32, dampingFraction: 0.85)
        static let bounce     = Animation.spring(response: 0.42, dampingFraction: 0.65)
        static let smooth     = Animation.easeInOut(duration: 0.22)
    }
}
