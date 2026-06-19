import Foundation

extension APIClient {
    struct LoginRequest: Encodable { let email: String; let password: String }
    struct TokenResponse: Decodable {
        let user: AuthUser
        let access_token: String
        let refresh_token: String
    }

    /// `POST /api/auth/token`
    func login(email: String, password: String) async throws -> TokenResponse {
        let response: TokenResponse = try await post(
            "/api/auth/token",
            body: LoginRequest(email: email, password: password),
            authenticated: false
        )
        KeychainStore.set(response.access_token, for: .accessToken)
        KeychainStore.set(response.refresh_token, for: .refreshToken)
        return response
    }

    /// `GET /api/auth/me`
    func me() async throws -> AuthUser { try await get("/api/auth/me") }

    /// `POST /api/auth/logout`
    func logout() async throws {
        let _: EmptyResponse = try await post("/api/auth/logout")
        KeychainStore.clear()
    }

    struct DeviceTokenRequest: Encodable {
        let device_token: String
        let platform: String
    }

    /// `PUT /api/auth/device-token`
    func registerDeviceToken(_ token: String) async throws {
        let _: EmptyResponse = try await put(
            "/api/auth/device-token",
            body: DeviceTokenRequest(device_token: token, platform: "ios")
        )
    }
}
