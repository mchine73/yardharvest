package app.yardharvest.manager.core

import android.content.Context
import android.content.SharedPreferences
import androidx.core.content.edit
import app.yardharvest.manager.BuildConfig

/**
 * Runtime configuration. Defaults to the live Render backend; can be
 * overridden from the gear on the sign-in screen for local backend testing.
 * Deliberately not offered once signed in: repointing the app at another
 * server is a development affordance, not something an organizer needs.
 */
object AppEnvironment {

    /** The canonical Render-hosted backend. */
    const val DEFAULT_BASE_URL = "https://www.yardharvest.app"

    private const val OVERRIDE_KEY = "yh.api.baseURL.override"

    /** Plain (non-secret) preferences shared across the app. Set in [init]. */
    lateinit var prefs: SharedPreferences
        private set

    /** Unit tests have no Context; they set [testBaseUrl] instead. */
    @Volatile var testBaseUrl: String? = null

    fun init(context: Context) {
        prefs = context.getSharedPreferences("yh.prefs", Context.MODE_PRIVATE)
    }

    /** Effective base URL the app should use right now, without a trailing slash. */
    val baseUrl: String
        get() {
            testBaseUrl?.let { return it.trimEnd('/') }
            val override = if (::prefs.isInitialized) prefs.getString(OVERRIDE_KEY, null) else null
            return (override?.takeIf { it.isNotBlank() } ?: DEFAULT_BASE_URL).trimEnd('/')
        }

    /** Persist a runtime override. Pass null or blank to clear. */
    fun setBaseUrlOverride(url: String?) {
        prefs.edit {
            if (url.isNullOrBlank()) remove(OVERRIDE_KEY) else putString(OVERRIDE_KEY, url.trim())
        }
    }

    val appVersion: String get() = BuildConfig.VERSION_NAME
    val buildNumber: String get() = BuildConfig.VERSION_CODE.toString()

    /**
     * Resolve a possibly-relative media path against the current backend.
     * Absolute URLs (starting with `http`) are returned as-is.
     */
    fun mediaUrl(path: String?): String? {
        if (path.isNullOrEmpty()) return null
        if (path.startsWith("http://") || path.startsWith("https://")) return path
        return baseUrl + if (path.startsWith("/")) path else "/$path"
    }
}
