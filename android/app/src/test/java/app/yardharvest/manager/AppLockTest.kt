package app.yardharvest.manager

import android.content.SharedPreferences
import app.yardharvest.manager.core.AppLock
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AppLockTest {
    private var now = 1_000_000L
    private var answer: Result<Boolean> = Result.success(true)
    private var prompts = 0

    private fun lock(prefs: FakePrefs = FakePrefs()) = AppLock(prefs, { prompts++; answer }, clock = { now })

    @Test fun `enabling requires passing the prompt first`() = runBlocking {
        val prefs = FakePrefs()
        val l = lock(prefs)
        answer = Result.success(false)
        assertFalse(l.enable())
        assertFalse(l.isEnabled)
        answer = Result.success(true)
        assertTrue(l.enable())
        assertTrue(l.isEnabled)
        assertFalse(l.isLocked)
    }

    @Test fun `a brief trip away doesn't lock`() = runBlocking {
        val l = lock()
        l.enable()
        l.didEnterBackground()
        now += 59_000
        l.didBecomeActive()
        assertFalse(l.isLocked)
    }

    @Test fun `a minute or more away locks, and unlocking clears it`() = runBlocking {
        val l = lock()
        l.enable()
        l.didEnterBackground()
        now += 60_000
        l.didBecomeActive()
        assertTrue(l.isLocked)
        l.unlock()
        assertFalse(l.isLocked)
    }

    @Test fun `a cold launch with the lock on starts locked`() = runBlocking {
        val prefs = FakePrefs()
        lock(prefs).enable()
        assertTrue(lock(prefs).isLocked)
    }

    @Test fun `a cancelled prompt says nothing, a lockout says why`() = runBlocking {
        val l = lock()
        l.enable()
        answer = Result.failure(AppLock.LockError(null))
        assertFalse(l.disable())
        assertNull(l.lastError)
        answer = Result.failure(AppLock.LockError("Too many attempts."))
        l.unlock()
        assertEquals("Too many attempts.", l.lastError)
    }

    @Test fun `signing out drops the lock for the next account`() = runBlocking {
        val prefs = FakePrefs()
        val l = lock(prefs)
        l.enable()
        l.didEnterBackground()
        now += 120_000
        l.resetOnSignOut()
        l.didBecomeActive()
        assertFalse(l.isLocked)
        assertFalse(l.isEnabled)
        assertFalse(lock(prefs).isLocked)
    }

    @Test fun `with the lock off nothing ever prompts`() = runBlocking {
        val l = lock()
        l.didEnterBackground()
        now += 600_000
        l.didBecomeActive()
        assertFalse(l.isLocked)
        assertEquals(0, prompts)
    }
}

/** Just enough SharedPreferences for the lock's one boolean. */
class FakePrefs : SharedPreferences {
    private val values = mutableMapOf<String, Any?>()
    override fun getAll(): MutableMap<String, *> = values
    override fun getString(key: String?, defValue: String?) = values[key] as? String ?: defValue
    override fun getStringSet(key: String?, defValues: MutableSet<String>?) = defValues
    override fun getInt(key: String?, defValue: Int) = values[key] as? Int ?: defValue
    override fun getLong(key: String?, defValue: Long) = values[key] as? Long ?: defValue
    override fun getFloat(key: String?, defValue: Float) = values[key] as? Float ?: defValue
    override fun getBoolean(key: String?, defValue: Boolean) = values[key] as? Boolean ?: defValue
    override fun contains(key: String?) = values.containsKey(key)
    override fun registerOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
    override fun unregisterOnSharedPreferenceChangeListener(l: SharedPreferences.OnSharedPreferenceChangeListener?) {}
    override fun edit(): SharedPreferences.Editor = object : SharedPreferences.Editor {
        override fun putString(key: String?, value: String?) = apply { values[key!!] = value }
        override fun putStringSet(key: String?, values: MutableSet<String>?) = this
        override fun putInt(key: String?, value: Int) = apply { values[key!!] = value }
        override fun putLong(key: String?, value: Long) = apply { values[key!!] = value }
        override fun putFloat(key: String?, value: Float) = apply { values[key!!] = value }
        override fun putBoolean(key: String?, value: Boolean) = apply { values[key!!] = value }
        override fun remove(key: String?) = apply { values.remove(key) }
        override fun clear() = apply { values.clear() }
        override fun commit() = true
        override fun apply() {}
    }
}
