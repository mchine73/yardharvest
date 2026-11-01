package app.yardharvest.manager.core

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager

/**
 * Centralized haptic feedback, mirroring the iOS `Haptics` enum so call sites
 * read the same on both platforms.
 */
// The EFFECT_* ids are compile-time ints; only API 29+ ever plays them.
@android.annotation.SuppressLint("InlinedApi")
object Haptics {
    private var vibrator: Vibrator? = null

    fun init(context: Context) {
        vibrator = if (Build.VERSION.SDK_INT >= 31) {
            (context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager)?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    private fun play(predefined: Int, fallbackMs: Long, amplitude: Int) {
        val v = vibrator ?: return
        if (!v.hasVibrator()) return
        try {
            if (Build.VERSION.SDK_INT >= 29) {
                v.vibrate(VibrationEffect.createPredefined(predefined))
            } else {
                v.vibrate(VibrationEffect.createOneShot(fallbackMs, amplitude))
            }
        } catch (_: SecurityException) {
        }
    }

    private fun pattern(timings: LongArray, amplitudes: IntArray) {
        val v = vibrator ?: return
        if (!v.hasVibrator()) return
        try { v.vibrate(VibrationEffect.createWaveform(timings, amplitudes, -1)) } catch (_: SecurityException) {}
    }

    /** Light tap for taps and selections. */
    fun tap() = play(VibrationEffect.EFFECT_TICK, 10, 60)

    /** Medium tap for confirmation actions. */
    fun confirm() = play(VibrationEffect.EFFECT_CLICK, 18, 140)

    /** Success: a quick double pulse. */
    fun success() = pattern(longArrayOf(0, 18, 60, 24), intArrayOf(0, 120, 0, 200))

    /** Warning: one firm pulse. */
    fun warning() = play(VibrationEffect.EFFECT_HEAVY_CLICK, 30, 200)

    /** Error: three short pulses. */
    fun error() = pattern(longArrayOf(0, 20, 50, 20, 50, 30), intArrayOf(0, 200, 0, 200, 0, 255))

    /** Selection click (segmented picker, filter chips). */
    fun selection() = play(VibrationEffect.EFFECT_TICK, 8, 40)
}
