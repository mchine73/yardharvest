import Foundation

/// Typed errors surfaced by APIClient. UI matches on these rather than
/// inspecting raw URLSession errors.
enum APIError: Error, LocalizedError, Equatable {
    case invalidURL
    case invalidResponse
    case unauthorized
    case forbidden
    case notFound
    case rateLimited
    case server(status: Int, message: String?)
    case network(message: String)
    case decoding(message: String)
    case missingToken

    var errorDescription: String? {
        switch self {
        case .invalidURL: return "Invalid request URL."
        case .invalidResponse: return "The server returned an unexpected response."
        case .unauthorized: return "Your session has expired — please sign in again."
        case .forbidden: return "You don't have permission for this action."
        case .notFound: return "We couldn't find that."
        case .rateLimited: return "Too many requests. Please slow down and try again."
        case let .server(status, message):
            return message ?? "Server error (\(status))."
        case let .network(message): return "Network error: \(message)"
        case let .decoding(message): return "Couldn't read the server response. (\(message))"
        case .missingToken: return "Not signed in."
        }
    }
}
