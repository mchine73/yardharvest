package app.yardharvest.manager.ui.brand

import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Design tokens mirroring the YardHarvest "lime / Onest" web system and the
 * iOS `YH` enum (ios/YardHarvest/Brand/Tokens.swift).
 */
object YH {
    /** Near-black `#22242a` — primary text, dark CTAs. */
    val ink = Color(0xFF22242A)
    /** Chartreuse `#e3ff8f` — the single accent. */
    val lime = Color(0xFFE3FF8F)
    /** Pale lime `#edf7cf` — soft surfaces. */
    val limeSoft = Color(0xFFEDF7CF)
    /** White — canvas. */
    val canvas = Color(0xFFFFFFFF)
    /** `#f2f3f3` — recessed surfaces. */
    val surface = Color(0xFFF2F3F3)
    /** `#f7f8f8`. */
    val surfaceAlt = Color(0xFFF7F8F8)
    /** Hairline `#e5e6e6`. */
    val border = Color(0xFFE5E6E6)
    /** `#6b6e76` — secondary text. */
    val muted = Color(0xFF6B6E76)
    /** Lighter secondary text, the counterpart of iOS `.tertiary`. */
    val tertiary = Color(0xFFA2A5AB)
    /** `#1b4d3e` — preserved for the sunflower logo backdrop. */
    val forest = Color(0xFF1B4D3E)

    val success = Color(0xFF1A9E52)
    /** Brand gold. */
    val warning = Color(0xFFD9992B)
    val danger = Color(0xFFE0574F)

    object Radius {
        val sm = 8.dp
        val md = 12.dp
        val lg = 16.dp
        val xl = 20.dp
    }

    object Space {
        val xxs = 4.dp
        val xs = 8.dp
        val sm = 12.dp
        val md = 16.dp
        val lg = 20.dp
        val xl = 28.dp
        val xxl = 40.dp
    }

    object Motion {
        fun <T> snappy() = spring<T>(dampingRatio = 0.85f, stiffness = Spring.StiffnessMediumLow)
        fun <T> bounce() = spring<T>(dampingRatio = 0.65f, stiffness = Spring.StiffnessLow)
    }
}

/**
 * Type scale tuned to the web's Onest treatment — semibold headlines with
 * tight tracking. Like iOS, this uses the platform face rather than bundling
 * a font, so launch stays fast and the app reads as native.
 */
object YHType {
    val display = TextStyle(fontSize = 40.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.8).sp, color = YH.ink)
    val title = TextStyle(fontSize = 30.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.6).sp)
    val title2 = TextStyle(fontSize = 24.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp)
    val title3 = TextStyle(fontSize = 20.sp, fontWeight = FontWeight.SemiBold)
    val headline = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.SemiBold)
    val body = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Normal)
    val bodyMedium = TextStyle(fontSize = 16.sp, fontWeight = FontWeight.Medium)
    val subheadline = TextStyle(fontSize = 14.sp, fontWeight = FontWeight.Normal)
    val caption = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.Normal)
    val captionMed = TextStyle(fontSize = 12.sp, fontWeight = FontWeight.SemiBold)
    val mono = TextStyle(fontSize = 14.sp, fontFamily = FontFamily.Monospace)
}
