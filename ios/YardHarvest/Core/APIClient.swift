import Foundation

/// REST client over URLSession.
///
/// - Actor-isolated so concurrent calls are safe and refresh is single-flight.
/// - Tolerates the many date shapes Flask emits (ISO8601 w/ offset,
///   ISO w/ fractional seconds, naive datetime, date-only).
/// - Auto-refreshes on 401 and replays the failed request once.
///
/// Endpoint methods live in separate extensions under `API/`.
actor APIClient {
    static let shared = APIClient()

    private let session: URLSession
    private let decoder: JSONDecoder
    private let encoder: JSONEncoder
    private var refreshTask: Task<Void, Error>?

    init(session: URLSession = .shared) {
        self.session = session

        let dec = JSONDecoder()
        dec.dateDecodingStrategy = .custom { decoder in
            let container = try decoder.singleValueContainer()
            let str = try container.decode(String.self)
            if let date = APIClient.parseDate(str) { return date }
            throw DecodingError.dataCorruptedError(
                in: container,
                debugDescription: "Unrecognized date format: \(str)"
            )
        }
        self.decoder = dec

        let enc = JSONEncoder()
        enc.dateEncodingStrategy = .iso8601
        self.encoder = enc
    }

    /// Parse the five date shapes the backend emits. Order matters — most
    /// specific first.
    static func parseDate(_ s: String) -> Date? {
        struct Cached {
            static let isoFractional: ISO8601DateFormatter = {
                let f = ISO8601DateFormatter()
                f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
                return f
            }()
            static let iso: ISO8601DateFormatter = {
                let f = ISO8601DateFormatter()
                f.formatOptions = [.withInternetDateTime]
                return f
            }()
            static let fallbacks: [DateFormatter] = {
                ["yyyy-MM-dd'T'HH:mm:ss.SSSSSS",
                 "yyyy-MM-dd'T'HH:mm:ss.SSS",
                 "yyyy-MM-dd'T'HH:mm:ss",
                 "yyyy-MM-dd"].map { fmt in
                    let f = DateFormatter()
                    f.locale = Locale(identifier: "en_US_POSIX")
                    f.timeZone = TimeZone(identifier: "UTC")
                    f.dateFormat = fmt
                    return f
                }
            }()
        }
        if let d = Cached.isoFractional.date(from: s) { return d }
        if let d = Cached.iso.date(from: s) { return d }
        for f in Cached.fallbacks {
            if let d = f.date(from: s) { return d }
        }
        return nil
    }

    // MARK: - Public methods

    func get<R: Decodable>(_ path: String,
                           query: [String: String] = [:],
                           authenticated: Bool = true) async throws -> R {
        try await request(method: "GET", path: path, query: query,
                          body: Optional<EmptyBody>.none, authenticated: authenticated)
    }

    func post<B: Encodable, R: Decodable>(_ path: String, body: B,
                                          authenticated: Bool = true) async throws -> R {
        try await request(method: "POST", path: path, body: body, authenticated: authenticated)
    }

    func post<R: Decodable>(_ path: String, authenticated: Bool = true) async throws -> R {
        try await request(method: "POST", path: path,
                          body: Optional<EmptyBody>.none, authenticated: authenticated)
    }

    func put<B: Encodable, R: Decodable>(_ path: String, body: B,
                                         authenticated: Bool = true) async throws -> R {
        try await request(method: "PUT", path: path, body: body, authenticated: authenticated)
    }

    func delete<R: Decodable>(_ path: String, authenticated: Bool = true) async throws -> R {
        try await request(method: "DELETE", path: path,
                          body: Optional<EmptyBody>.none, authenticated: authenticated)
    }

    /// Multipart upload helper for the photo endpoint.
    func uploadMultipart<R: Decodable>(_ path: String,
                                        fields: [String: String],
                                        fileField: String,
                                        fileName: String,
                                        mimeType: String,
                                        fileData: Data,
                                        authenticated: Bool = true) async throws -> R {
        var url = AppEnvironment.baseURL
        url.append(path: path)

        let boundary = "----YHBoundary\(UUID().uuidString)"
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        if authenticated {
            guard let token = KeychainStore.get(.accessToken) else { throw APIError.missingToken }
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        var body = Data()
        for (k, v) in fields {
            body.append("--\(boundary)\r\n".data(using: .utf8)!)
            body.append("Content-Disposition: form-data; name=\"\(k)\"\r\n\r\n".data(using: .utf8)!)
            body.append("\(v)\r\n".data(using: .utf8)!)
        }
        body.append("--\(boundary)\r\n".data(using: .utf8)!)
        body.append("Content-Disposition: form-data; name=\"\(fileField)\"; filename=\"\(fileName)\"\r\n".data(using: .utf8)!)
        body.append("Content-Type: \(mimeType)\r\n\r\n".data(using: .utf8)!)
        body.append(fileData)
        body.append("\r\n--\(boundary)--\r\n".data(using: .utf8)!)

        request.httpBody = body
        let (data, response) = try await session.upload(for: request, from: body)
        try Self.throwIfHTTPError(response: response, data: data)
        return try decoder.decode(R.self, from: data)
    }

    // MARK: - Engine

    private struct EmptyBody: Encodable {}

    private func request<B: Encodable, R: Decodable>(
        method: String, path: String, query: [String: String] = [:],
        body: B?, authenticated: Bool
    ) async throws -> R {
        let request = try buildRequest(method: method, path: path, query: query,
                                        body: body, authenticated: authenticated)
        do {
            let (data, response) = try await session.data(for: request)
            if let http = response as? HTTPURLResponse, http.statusCode == 401, authenticated {
                try await performRefreshIfPossible()
                let retried = try buildRequest(method: method, path: path, query: query,
                                                body: body, authenticated: authenticated)
                let (retryData, retryResp) = try await session.data(for: retried)
                try Self.throwIfHTTPError(response: retryResp, data: retryData)
                return try decode(R.self, from: retryData)
            }
            try Self.throwIfHTTPError(response: response, data: data)
            return try decode(R.self, from: data)
        } catch let error as APIError {
            throw error
        } catch let urlErr as URLError {
            throw APIError.network(message: urlErr.localizedDescription)
        } catch let decoded as DecodingError {
            throw APIError.decoding(message: String(describing: decoded))
        } catch {
            throw APIError.network(message: error.localizedDescription)
        }
    }

    private func buildRequest<B: Encodable>(
        method: String, path: String, query: [String: String],
        body: B?, authenticated: Bool
    ) throws -> URLRequest {
        var components = URLComponents(url: AppEnvironment.baseURL, resolvingAgainstBaseURL: false)!
        components.path = (components.path.isEmpty ? "" : components.path) + path
        if !query.isEmpty {
            components.queryItems = query.map { URLQueryItem(name: $0.key, value: $0.value) }
        }
        guard let url = components.url else { throw APIError.invalidURL }

        var req = URLRequest(url: url)
        req.httpMethod = method
        req.setValue("application/json", forHTTPHeaderField: "Accept")
        req.setValue("YardHarvest-iOS/\(AppEnvironment.appVersion) (iOS)",
                     forHTTPHeaderField: "User-Agent")

        if let body = body, !(body is EmptyBody) {
            req.setValue("application/json", forHTTPHeaderField: "Content-Type")
            req.httpBody = try encoder.encode(body)
        }

        if authenticated {
            guard let token = KeychainStore.get(.accessToken) else { throw APIError.missingToken }
            req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        return req
    }

    private func decode<R: Decodable>(_ type: R.Type, from data: Data) throws -> R {
        if R.self == EmptyResponse.self { return EmptyResponse() as! R }
        return try decoder.decode(R.self, from: data)
    }

    private static func throwIfHTTPError(response: URLResponse, data: Data) throws {
        guard let http = response as? HTTPURLResponse else { throw APIError.invalidResponse }
        let status = http.statusCode
        if (200...299).contains(status) { return }
        let serverMessage: String? = {
            if let parsed = try? JSONSerialization.jsonObject(with: data) as? [String: Any] {
                return parsed["error"] as? String ?? parsed["message"] as? String
            }
            return nil
        }()
        switch status {
        case 401: throw APIError.unauthorized
        case 403: throw APIError.forbidden
        case 404: throw APIError.notFound
        case 429: throw APIError.rateLimited
        default: throw APIError.server(status: status, message: serverMessage)
        }
    }

    private func performRefreshIfPossible() async throws {
        if let inflight = refreshTask {
            try await inflight.value
            return
        }
        let task = Task<Void, Error> {
            defer { refreshTask = nil }
            try await self.refresh()
        }
        refreshTask = task
        try await task.value
    }

    private func refresh() async throws {
        guard let refreshToken = KeychainStore.get(.refreshToken) else {
            throw APIError.unauthorized
        }
        struct Req: Encodable { let refresh_token: String }
        struct Resp: Decodable {
            let access_token: String
            let refresh_token: String
        }

        var components = URLComponents(url: AppEnvironment.baseURL, resolvingAgainstBaseURL: false)!
        components.path += "/api/auth/token/refresh"
        guard let url = components.url else { throw APIError.invalidURL }

        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try encoder.encode(Req(refresh_token: refreshToken))

        let (data, response) = try await session.data(for: req)
        guard let http = response as? HTTPURLResponse, (200...299).contains(http.statusCode) else {
            KeychainStore.clear()
            throw APIError.unauthorized
        }
        let decoded = try decoder.decode(Resp.self, from: data)
        KeychainStore.set(decoded.access_token, for: .accessToken)
        KeychainStore.set(decoded.refresh_token, for: .refreshToken)
    }
}

/// Sentinel for endpoints that don't return a useful body.
struct EmptyResponse: Decodable {}
