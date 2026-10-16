import SwiftUI

/// Covers the app while the biometric lock is engaged.
///
/// Deliberately opaque and content-free: it sits above the signed-in UI, so
/// anything it let through would defeat the point. It also appears in the app
/// switcher snapshot, which is the other place a glance could leak the
/// garden's member list.
struct LockScreenView: View {
    @Bindable var lock: AppLock
    @State private var isWorking = false

    private var biometryName: String { AppLock.biometryName ?? "biometrics" }

    var body: some View {
        ZStack {
            YH.canvas.ignoresSafeArea()
            VStack(spacing: YH.Space.lg) {
                Spacer()
                Image(systemName: "lock.fill")
                    .font(.system(size: 44, weight: .semibold))
                    .foregroundStyle(YH.ink)
                    .padding(28)
                    .background(YH.lime)
                    .clipShape(RoundedRectangle(cornerRadius: YH.Radius.lg,
                                                style: .continuous))
                VStack(spacing: 6) {
                    Text("YardHarvest is locked")
                        .font(.yhTitle2)
                        .foregroundStyle(YH.ink)
                    Text("Unlock with \(biometryName) to carry on.")
                        .font(.yhSubheadline)
                        .foregroundStyle(YH.muted)
                        .multilineTextAlignment(.center)
                }
                if let error = lock.lastError {
                    Text(error)
                        .font(.yhCaption)
                        .foregroundStyle(YH.danger)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, YH.Space.lg)
                }
                Spacer()
                YHButton(title: "Unlock", systemImage: "faceid",
                         style: .dark, isLoading: isWorking) {
                    Task { await attempt() }
                }
                .padding(.horizontal, YH.Space.lg)
                .padding(.bottom, YH.Space.xl)
            }
        }
        // One automatic attempt on appear, so the common case is a glance and
        // nothing more. The button is for after a cancel or a failure.
        .task { await attempt() }
    }

    private func attempt() async {
        guard !isWorking else { return }
        isWorking = true
        defer { isWorking = false }
        await lock.unlock()
    }
}
