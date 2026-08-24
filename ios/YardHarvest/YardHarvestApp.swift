import SwiftUI
import UIKit

@main
struct YardHarvestApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @State private var auth = AuthManager()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(auth)
                .preferredColorScheme(.light)   // The lime/Onest skin is light-first.
                .tint(YH.ink)
                .task { await auth.bootstrap() }
        }
    }
}

final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        // Before anything else: a cold-start notification tap delivers to the
        // delegate during launch, so it must be installed here, not on the
        // first screen that happens to care.
        PushManager.shared.install()

        // Modernize navigation/tab bar chrome to the canvas palette.
        let navBarAppearance = UINavigationBarAppearance()
        navBarAppearance.configureWithTransparentBackground()
        navBarAppearance.backgroundColor = UIColor(named: "Canvas")
        navBarAppearance.titleTextAttributes = [.foregroundColor: UIColor(named: "Ink") ?? .black]
        navBarAppearance.largeTitleTextAttributes = [.foregroundColor: UIColor(named: "Ink") ?? .black]
        UINavigationBar.appearance().standardAppearance = navBarAppearance
        UINavigationBar.appearance().scrollEdgeAppearance = navBarAppearance

        let tabAppearance = UITabBarAppearance()
        tabAppearance.configureWithDefaultBackground()
        tabAppearance.backgroundColor = UIColor(named: "Canvas")
        UITabBar.appearance().standardAppearance = tabAppearance
        UITabBar.appearance().scrollEdgeAppearance = tabAppearance

        return true
    }

    func application(_ application: UIApplication,
                     didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let hex = deviceToken.map { String(format: "%02.2hhx", $0) }.joined()
        Task { try? await APIClient.shared.registerDeviceToken(hex) }
    }

    func application(_ application: UIApplication,
                     didFailToRegisterForRemoteNotificationsWithError error: Error) {
        // Simulators and entitlement-less builds land here; harmless.
        print("APNs registration failed: \(error.localizedDescription)")
    }
}
