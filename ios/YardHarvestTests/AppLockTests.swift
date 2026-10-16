import XCTest
import LocalAuthentication
@testable import YardHarvest

/// The lock's state machine, with the biometric check stubbed — `LAContext`
/// can't be driven from a test, but everything around it can, and that is
/// where the behaviour people depend on lives.
@MainActor
final class AppLockTests: XCTestCase {

    private func makeDefaults(_ name: String) -> UserDefaults {
        let d = UserDefaults(suiteName: name)!
        d.removePersistentDomain(forName: name)
        return d
    }

    private func makeLock(_ name: String = #function,
                          result: @escaping () -> Result<Bool, Error>)
                          -> (AppLock, UserDefaults) {
        let d = makeDefaults("applock.\(name)")
        return (AppLock(defaults: d, authenticator: { _ in result() }), d)
    }

    func testStartsOffAndUnlocked() {
        let (lock, _) = makeLock { .success(true) }
        XCTAssertFalse(lock.isEnabled)
        XCTAssertFalse(lock.isLocked)
    }

    func testEnableRequiresPassingTheCheck() async {
        let (lock, _) = makeLock { .success(false) }
        let ok = await lock.enable()
        XCTAssertFalse(ok)
        XCTAssertFalse(lock.isEnabled, "a failed check must not arm the lock")
    }

    func testEnablePersistsWhenTheCheckPasses() async {
        let (lock, _) = makeLock { .success(true) }
        let ok = await lock.enable()
        XCTAssertTrue(ok)
        XCTAssertTrue(lock.isEnabled)
        XCTAssertFalse(lock.isLocked, "enabling shouldn't lock you out on the spot")
    }

    func testDisableRequiresPassingTheCheck() async {
        let d = makeDefaults("applock.disableguard")
        var pass = true
        let lock = AppLock(defaults: d, authenticator: { _ in .success(pass) })
        _ = await lock.enable()
        XCTAssertTrue(lock.isEnabled)

        pass = false
        let ok = await lock.disable()
        XCTAssertFalse(ok)
        XCTAssertTrue(lock.isEnabled,
                      "someone who can't pass the check must not be able to switch it off")
    }

    func testDisableTurnsItOffWhenTheCheckPasses() async {
        let (lock, _) = makeLock { .success(true) }
        _ = await lock.enable()
        let ok = await lock.disable()
        XCTAssertTrue(ok)
        XCTAssertFalse(lock.isEnabled)
    }

    func testLocksOnlyAfterTheGracePeriod() async {
        let d = makeDefaults("applock.grace")
        let lock = AppLock(defaults: d, authenticator: { _ in .success(true) })
        _ = await lock.enable()

        // Straight back from a brief excursion — no prompt.
        lock.didEnterBackground()
        lock.didBecomeActive()
        XCTAssertFalse(lock.isLocked,
                       "a quick flip to another app shouldn't demand Face ID")
    }

    func testDoesNotArmWhenDisabled() {
        let (lock, _) = makeLock { .success(true) }
        lock.didEnterBackground()
        lock.didBecomeActive()
        XCTAssertFalse(lock.isLocked)
    }

    func testColdLaunchStartsLockedWhenEnabled() async {
        let d = makeDefaults("applock.coldlaunch")
        let first = AppLock(defaults: d, authenticator: { _ in .success(true) })
        _ = await first.enable()

        // A second instance over the same store stands in for a fresh launch.
        let relaunched = AppLock(defaults: d, authenticator: { _ in .success(true) })
        XCTAssertTrue(relaunched.isLocked)
    }

    func testUnlockClearsTheLock() async {
        let d = makeDefaults("applock.unlock")
        let first = AppLock(defaults: d, authenticator: { _ in .success(true) })
        _ = await first.enable()
        let relaunched = AppLock(defaults: d, authenticator: { _ in .success(true) })
        XCTAssertTrue(relaunched.isLocked)

        await relaunched.unlock()
        XCTAssertFalse(relaunched.isLocked)
    }

    func testFailedUnlockLeavesItLocked() async {
        let d = makeDefaults("applock.failedunlock")
        let first = AppLock(defaults: d, authenticator: { _ in .success(true) })
        _ = await first.enable()
        let relaunched = AppLock(
            defaults: d,
            authenticator: { _ in .failure(LAError(.authenticationFailed)) })
        await relaunched.unlock()
        XCTAssertTrue(relaunched.isLocked)
        XCTAssertNotNil(relaunched.lastError)
    }

    func testCancelShowsNoError() async {
        let d = makeDefaults("applock.cancel")
        let first = AppLock(defaults: d, authenticator: { _ in .success(true) })
        _ = await first.enable()
        let relaunched = AppLock(
            defaults: d,
            authenticator: { _ in .failure(LAError(.userCancel)) })
        await relaunched.unlock()
        XCTAssertTrue(relaunched.isLocked)
        XCTAssertNil(relaunched.lastError,
                     "cancelling on purpose isn't an error worth shouting about")
    }

    func testSignOutDropsTheLock() async {
        let (lock, _) = makeLock { .success(true) }
        _ = await lock.enable()
        lock.resetOnSignOut()
        XCTAssertFalse(lock.isEnabled,
                       "the next person to sign in must not inherit a lock they can't pass")
        XCTAssertFalse(lock.isLocked)
    }
}
