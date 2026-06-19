import Foundation
import Security

/// Minimal Keychain wrapper for the access + refresh JWTs. Hand-rolled to
/// avoid adding a dependency for the small surface area we use.
struct KeychainStore {
    enum Key: String {
        case accessToken = "yh.auth.accessToken"
        case refreshToken = "yh.auth.refreshToken"
    }

    private static let service = "app.yardharvest.manager"

    static func set(_ value: String?, for key: Key) {
        let account = key.rawValue
        let deleteQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
        ]
        SecItemDelete(deleteQuery as CFDictionary)

        guard let value, let data = value.data(using: .utf8) else { return }

        let addQuery: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: account,
            kSecValueData as String: data,
            kSecAttrAccessible as String: kSecAttrAccessibleAfterFirstUnlock,
        ]
        SecItemAdd(addQuery as CFDictionary, nil)
    }

    static func get(_ key: Key) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrService as String: service,
            kSecAttrAccount as String: key.rawValue,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne,
        ]
        var result: AnyObject?
        let status = SecItemCopyMatching(query as CFDictionary, &result)
        guard status == errSecSuccess, let data = result as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }
        return string
    }

    static func clear() {
        set(nil, for: .accessToken)
        set(nil, for: .refreshToken)
    }
}
