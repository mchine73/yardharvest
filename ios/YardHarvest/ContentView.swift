import SwiftUI

/// Root auth gate. Splash → Login → tab shell.
struct ContentView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(\.scenePhase) private var scenePhase
    @State private var lock = AppLock.shared

    var body: some View {
        ZStack {
            switch auth.state {
            case .unknown:
                SplashView()
                    .transition(.opacity)
            case .signedOut:
                LoginView()
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            case .signedIn(let user):
                HomeTabView(user: user)
                    .transition(.opacity)
            }

            // Above everything, and only over a signed-in session — there is
            // nothing to protect on the login screen, and covering the splash
            // would race the bootstrap.
            if lock.isLocked, case .signedIn = auth.state {
                LockScreenView(lock: lock)
                    .transition(.opacity)
                    .zIndex(1)
            }
        }
        .animation(YH.Motion.snappy, value: stateKey)
        .animation(YH.Motion.snappy, value: lock.isLocked)
        .background(YH.canvas.ignoresSafeArea())
        .onChange(of: scenePhase) { _, phase in
            // Only a true .background arms the lock. .inactive covers Control
            // Center, the notification shade and system sheets — Apple's Tap
            // to Pay sheet among them.
            switch phase {
            case .background: lock.didEnterBackground()
            case .active:     lock.didBecomeActive()
            default:          break
            }
        }
    }

    private var stateKey: Int {
        switch auth.state {
        case .unknown: return 0
        case .signedOut: return 1
        case .signedIn: return 2
        }
    }
}
