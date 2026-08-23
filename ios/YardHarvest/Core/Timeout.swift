import Foundation

/// Thrown when `withTimeout` hits its deadline before the work finishes.
struct TimeoutError: LocalizedError, Equatable {
    var errorDescription: String? { "The request timed out." }
}

/// Run `operation`, giving up after `seconds`.
///
/// URLSession timeouts cover a single request; this bounds a whole operation
/// (including retries and token refresh) so a caller can promise it will
/// always finish. Used on launch, where a request that never returns would
/// otherwise leave the app on the splash screen forever.
func withTimeout<T: Sendable>(
    seconds: Double,
    _ operation: @escaping @Sendable () async throws -> T
) async throws -> T {
    try await withThrowingTaskGroup(of: T.self) { group in
        group.addTask { try await operation() }
        group.addTask {
            try await Task.sleep(nanoseconds: UInt64(seconds * 1_000_000_000))
            throw TimeoutError()
        }
        guard let first = try await group.next() else { throw TimeoutError() }
        group.cancelAll()
        return first
    }
}
