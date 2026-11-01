package app.yardharvest.manager.core

import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue

/**
 * Launcher-shortcut entry points — Android's counterpart of the iOS "Log
 * Harvest" App Intent. The home shell consumes [pending] once it exists.
 */
object DeepLinks {
    enum class Link { LogHarvest, Scan }

    var pending: Link? by mutableStateOf(null)

    fun from(uri: Uri?): Link? {
        if (uri == null || uri.scheme != "yardharvest") return null
        return when (uri.host) {
            "log-harvest" -> Link.LogHarvest
            "scan" -> Link.Scan
            else -> null
        }
    }
}
