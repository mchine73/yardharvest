import SwiftUI

/// Empty state — friendly illustration via SF Symbol, ink title, muted body,
/// optional action button.
struct YHEmpty: View {
    let systemImage: String
    let title: String
    let message: String
    var actionTitle: String? = nil
    var action: (() -> Void)? = nil

    var body: some View {
        VStack(spacing: YH.Space.md) {
            Image(systemName: systemImage)
                .font(.system(size: 42, weight: .light))
                .symbolEffect(.bounce.up.byLayer, options: .nonRepeating)
                .foregroundStyle(YH.ink)
                .padding(20)
                .background(YH.lime)
                .clipShape(Circle())
            VStack(spacing: 6) {
                Text(title)
                    .font(.yhTitle3)
                    .foregroundStyle(YH.ink)
                    .multilineTextAlignment(.center)
                Text(message)
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.muted)
                    .multilineTextAlignment(.center)
            }
            if let actionTitle, let action {
                YHButton(title: actionTitle, style: .dark, fullWidth: false, action: action)
                    .padding(.top, 4)
            }
        }
        .padding(.horizontal, 32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}

/// Error state — same layout as empty but with a triangle icon + retry.
struct YHErrorState: View {
    let message: String
    let retry: (() -> Void)?

    var body: some View {
        VStack(spacing: YH.Space.md) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 36, weight: .regular))
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(YH.danger)
                .symbolEffect(.bounce, options: .nonRepeating)
            VStack(spacing: 6) {
                Text("Something went sideways")
                    .font(.yhTitle3)
                    .foregroundStyle(YH.ink)
                Text(message)
                    .font(.yhSubheadline)
                    .foregroundStyle(YH.muted)
                    .multilineTextAlignment(.center)
            }
            if let retry {
                YHButton(title: "Try Again", style: .dark, fullWidth: false, action: retry)
                    .padding(.top, 4)
            }
        }
        .padding(.horizontal, 32)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
