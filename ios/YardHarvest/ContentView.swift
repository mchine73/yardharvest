import SwiftUI

/// Root auth gate. Splash → Login → tab shell.
struct ContentView: View {
    @Environment(AuthManager.self) private var auth

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
        }
        .animation(YH.Motion.snappy, value: stateKey)
        .background(YH.canvas.ignoresSafeArea())
    }

    private var stateKey: Int {
        switch auth.state {
        case .unknown: return 0
        case .signedOut: return 1
        case .signedIn: return 2
        }
    }
}
