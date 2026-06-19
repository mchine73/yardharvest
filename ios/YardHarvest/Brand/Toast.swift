import SwiftUI

/// In-app toast banner. Anchors to the top safe area; lime-iconed; tappable
/// to dismiss with an explicit `x` button as a backup. Designed to live in an
/// overlay so it floats above the tab content without blocking it.
struct YHToast: View {
    let alert: AppAlert
    var onTap: () -> Void
    var onDismiss: () -> Void

    var body: some View {
        Button {
            Haptics.tap()
            onTap()
        } label: {
            HStack(spacing: 12) {
                Image(systemName: alert.kind.systemImage)
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(YH.ink)
                    .frame(width: 34, height: 34)
                    .background(YH.lime)
                    .clipShape(Circle())
                VStack(alignment: .leading, spacing: 1) {
                    Text(alert.title)
                        .font(.yhBodyMedium)
                        .foregroundStyle(YH.ink)
                        .lineLimit(1)
                    if let body = alert.body, !body.isEmpty {
                        Text(body)
                            .font(.yhCaption)
                            .foregroundStyle(YH.muted)
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 8)
                Button {
                    Haptics.tap()
                    onDismiss()
                } label: {
                    Image(systemName: "xmark")
                        .font(.system(size: 11, weight: .bold))
                        .foregroundStyle(YH.muted)
                        .frame(width: 24, height: 24)
                        .background(YH.surface)
                        .clipShape(Circle())
                }
                .buttonStyle(.plain)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(YH.canvas)
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .strokeBorder(YH.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .shadow(color: .black.opacity(0.10), radius: 10, x: 0, y: 6)
        }
        .buttonStyle(.plain)
    }
}

/// View modifier that overlays the alert center's current toast (if any) at
/// the top of the host view. Use once at the tab/root level.
struct YHToastBannerOverlay: ViewModifier {
    let center: AppAlertCenter
    var onTap: (AppAlert) -> Void

    func body(content: Content) -> some View {
        content.overlay(alignment: .top) {
            if let alert = center.current {
                YHToast(
                    alert: alert,
                    onTap: {
                        onTap(alert)
                        center.dismiss()
                    },
                    onDismiss: { center.dismiss() }
                )
                .padding(.horizontal, 12)
                .padding(.top, 6)
                .transition(.move(edge: .top).combined(with: .opacity))
                .zIndex(1000)
            }
        }
        .animation(.spring(response: 0.42, dampingFraction: 0.78),
                   value: center.current?.id)
    }
}

extension View {
    /// Convenience: attach the toast banner driven by `center`.
    func yhToastBanner(_ center: AppAlertCenter,
                       onTap: @escaping (AppAlert) -> Void = { _ in }) -> some View {
        modifier(YHToastBannerOverlay(center: center, onTap: onTap))
    }
}
