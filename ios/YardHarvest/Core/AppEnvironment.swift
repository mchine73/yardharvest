import Foundation

/// Runtime configuration. Defaults to the live Render backend; can be
/// overridden in Settings for local backend testing.
enum AppEnvironment {

    /// The canonical Render-hosted backend.
    static var defaultBaseURL: URL {
        URL(string: "https://www.yardharvest.app")!
    }

    private static let overrideKey = "yh.api.baseURL.override"

    /// Effective base URL the app should use right now.
    static var baseURL: URL {
        if let override = UserDefaults.standard.string(forKey: overrideKey),
           let url = URL(string: override) {
            return url
        }
        return defaultBaseURL
    }

    /// Persist a runtime override. Pass `nil` to clear.
    static func setBaseURLOverride(_ urlString: String?) {
        if let urlString, !urlString.isEmpty {
            UserDefaults.standard.set(urlString, forKey: overrideKey)
        } else {
            UserDefaults.standard.removeObject(forKey: overrideKey)
        }
    }

    static var appVersion: String {
        Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "0.0.0"
    }

    static var buildNumber: String {
        Bundle.main.infoDictionary?["CFBundleVersion"] as? String ?? "0"
    }

    /// Resolve a possibly-relative media path against the current backend.
    /// Absolute URLs (starting with `http`) are returned as-is.
    static func mediaURL(_ path: String?) -> URL? {
        mediaURL(path, base: baseURL)
    }

    /// The joining itself, against an explicit base. Split out so it can be
    /// tested without the ambient override: that override can be written to
    /// the simulator's device-level preference domain, which the app cannot
    /// clear from inside itself, so a test that reads it is at the mercy of
    /// whatever the last hand-test left behind.
    static func mediaURL(_ path: String?, base: URL) -> URL? {
        guard let path, !path.isEmpty else { return nil }
        if path.hasPrefix("http://") || path.hasPrefix("https://") {
            return URL(string: path)
        }
        let stem = base.absoluteString.hasSuffix("/")
            ? String(base.absoluteString.dropLast())
            : base.absoluteString
        return URL(string: stem + (path.hasPrefix("/") ? path : "/" + path))
    }
}
