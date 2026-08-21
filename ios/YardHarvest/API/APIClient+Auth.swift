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
        let response: TokenResponse
        do {
            response = try await post(
                "/api/auth/token",
                body: LoginRequest(email: email, password: password),
                authenticated: false
            )
        } catch APIError.unauthorized {
            // A 401 here can only mean the credentials were wrong — there's no
            // session to have expired yet.
            throw APIError.invalidCredentials
        } catch APIError.forbidden {
            // The only 403 this endpoint returns is a deactivated account;
            // the generic permissions wording makes no sense on a sign-in form.
            throw APIError.accountDeactivated
        }
        KeychainStore.set(response.access_token, for: .accessToken)
        KeychainStore.set(response.refresh_token, for: .refreshToken)
        return response
    }

    struct ForgotPasswordRequest: Encodable { let email: String }

    /// `POST /api/auth/forgot-password`
    ///
    /// Always succeeds when the email is well-formed — the server deliberately
    /// doesn't reveal whether an account exists. Rate-limited to 3/hour, which
    /// surfaces as `APIError.rateLimited`.
    func forgotPassword(email: String) async throws {
        let _: EmptyResponse = try await post(
            "/api/auth/forgot-password",
            body: ForgotPasswordRequest(email: email),
            authenticated: false
        )
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
