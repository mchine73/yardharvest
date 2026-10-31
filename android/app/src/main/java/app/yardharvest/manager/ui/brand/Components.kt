package app.yardharvest.manager.ui.brand

import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.BoxWithConstraints
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.R
import app.yardharvest.manager.core.Haptics
import java.time.Instant

// The shared visual vocabulary, one-for-one with ios/YardHarvest/Brand/*.swift.

/** `.dark` (ink, primary CTA), `.ghost` (white, ink border), `.lime` (accent CTA). */
enum class YHButtonStyle { Dark, Ghost, Lime }

@Composable
fun YHButton(
    title: String,
    modifier: Modifier = Modifier,
    icon: ImageVector? = null,
    style: YHButtonStyle = YHButtonStyle.Dark,
    isLoading: Boolean = false,
    fullWidth: Boolean = true,
    enabled: Boolean = true,
    onClick: () -> Unit,
) {
    val fg = when (style) { YHButtonStyle.Dark -> Color.White; else -> YH.ink }
    val bg = when (style) { YHButtonStyle.Dark -> YH.ink; YHButtonStyle.Ghost -> YH.canvas; YHButtonStyle.Lime -> YH.lime }
    val borderColor = when (style) { YHButtonStyle.Dark -> YH.ink; YHButtonStyle.Ghost -> YH.border; YHButtonStyle.Lime -> YH.lime }
    val interaction = remember { MutableInteractionSource() }
    val pressed by interaction.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.985f else 1f, YH.Motion.snappy(), label = "press")
    val shape = RoundedCornerShape(YH.Radius.md)
    val active = enabled && !isLoading
    Row(
        modifier = modifier
            .then(if (fullWidth) Modifier.fillMaxWidth() else Modifier)
            .scale(scale)
            .alpha(if (enabled) 1f else 0.45f)
            .clip(shape)
            .background(bg)
            .border(1.dp, borderColor, shape)
            .clickable(interactionSource = interaction, indication = null, enabled = active) {
                Haptics.tap()
                onClick()
            }
            .padding(horizontal = 18.dp, vertical = 14.dp),
        horizontalArrangement = Arrangement.spacedBy(YH.Space.xs, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (isLoading) {
            CircularProgressIndicator(Modifier.size(18.dp), color = fg, strokeWidth = 2.dp)
        } else {
            if (icon != null) Icon(icon, null, tint = fg, modifier = Modifier.size(18.dp))
            Text(title, color = fg, fontSize = 16.sp, fontWeight = FontWeight.SemiBold)
        }
    }
}

/** Brand card surface — white on canvas, hairline border, 16dp radius. */
@Composable
fun YHCard(
    modifier: Modifier = Modifier,
    padding: Dp = YH.Space.md,
    radius: Dp = YH.Radius.lg,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val shape = RoundedCornerShape(radius)
    Column(
        modifier
            .fillMaxWidth()
            .clip(shape)
            .background(YH.canvas)
            .border(1.dp, YH.border, shape)
            .then(if (onClick != null) Modifier.clickable { Haptics.tap(); onClick() } else Modifier)
            .padding(padding),
        content = content,
    )
}

enum class YHBandTint { Lime, Dark }

/** Full-bleed colored band used as a hero or callout. */
@Composable
fun YHBand(
    modifier: Modifier = Modifier,
    tint: YHBandTint = YHBandTint.Lime,
    content: @Composable ColumnScope.() -> Unit,
) {
    Column(
        modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(18.dp))
            .background(if (tint == YHBandTint.Dark) YH.ink else YH.lime)
            .padding(YH.Space.lg),
        content = content,
    )
}

/** Bento stat tile — big number, lime icon chip. */
@Composable
fun YHStatTile(
    label: String,
    value: String,
    modifier: Modifier = Modifier,
    detail: String? = null,
    icon: ImageVector,
    onClick: (() -> Unit)? = null,
) {
    YHCard(modifier, onClick = onClick) {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(label.uppercase(), style = YHType.captionMed, letterSpacing = 0.5.sp, color = YH.muted, modifier = Modifier.weight(1f))
                Box(
                    Modifier.clip(RoundedCornerShape(9.dp)).background(YH.lime).padding(8.dp),
                ) { Icon(icon, null, tint = YH.ink, modifier = Modifier.size(14.dp)) }
            }
            Text(value, fontSize = 28.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.6).sp, color = YH.ink, maxLines = 1)
            if (detail != null) Text(detail, style = YHType.caption, color = YH.muted, maxLines = 2)
        }
    }
}

/** Circular avatar — lime fill with ink initials, or an icon. */
@Composable
fun YHAvatar(
    name: String? = null,
    icon: ImageVector? = null,
    size: Dp = 44.dp,
    background: Color = YH.lime,
    foreground: Color = YH.ink,
) {
    Box(
        Modifier.size(size).clip(CircleShape).background(background),
        contentAlignment = Alignment.Center,
    ) {
        if (icon != null) {
            Icon(icon, null, tint = foreground, modifier = Modifier.size(size * 0.48f))
        } else {
            Text(initials(name ?: ""), color = foreground, fontWeight = FontWeight.Bold, fontSize = (size.value * 0.36f).sp)
        }
    }
}

/** Up-to-two-character initials, the same heuristic as iOS. */
fun initials(name: String): String {
    val parts = name.split(" ").filter { it.isNotBlank() }.take(2)
    val chars = parts.mapNotNull { it.firstOrNull()?.toString() }.joinToString("")
    return if (chars.isEmpty()) "?" else chars.uppercase()
}

/** Pill-shaped status indicator. */
@Composable
fun YHPill(
    text: String,
    icon: ImageVector? = null,
    tint: Color = YH.ink,
    background: Color? = null,
) {
    Row(
        Modifier
            .clip(RoundedCornerShape(50))
            .background(background ?: tint.copy(alpha = 0.12f))
            .padding(horizontal = 10.dp, vertical = 4.dp),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) Icon(icon, null, tint = tint, modifier = Modifier.size(12.dp))
        Text(text, color = tint, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1)
    }
}

/** Lime badge — outer pill + inner lime number. */
@Composable
fun YHLimeBadge(label: String, value: String) {
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(YH.surface).padding(end = 10.dp),
        horizontalArrangement = Arrangement.spacedBy(6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            value, color = YH.ink, fontSize = 12.sp, fontWeight = FontWeight.SemiBold,
            modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 9.dp, vertical = 3.dp),
        )
        Text(label, color = YH.ink, fontSize = 13.sp, fontWeight = FontWeight.Medium)
    }
}

/** Small surface-gray rounded square wrapping an icon — the standard row prefix. */
@Composable
fun YHIconTile(
    icon: ImageVector,
    size: Dp = 28.dp,
    background: Color = YH.surface,
    foreground: Color = YH.ink,
    iconSize: Dp? = null,
) {
    Box(
        Modifier.size(size).clip(RoundedCornerShape(size * 0.29f)).background(background),
        contentAlignment = Alignment.Center,
    ) { Icon(icon, null, tint = foreground, modifier = Modifier.size(iconSize ?: size * 0.5f)) }
}

/** Card section header — icon tile + title + optional trailing text + chevron. */
@Composable
fun YHSectionHeader(
    title: String,
    icon: ImageVector? = null,
    trailing: String? = null,
    showsChevron: Boolean = false,
    titleStyle: TextStyle = YHType.headline,
) {
    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(10.dp)) {
        if (icon != null) YHIconTile(icon)
        Text(title, style = titleStyle, color = YH.ink, modifier = Modifier.weight(1f))
        if (trailing != null) Text(trailing, style = YHType.captionMed, color = YH.muted)
        if (showsChevron) Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted, modifier = Modifier.size(18.dp))
    }
}

/** Calendar-style date tile — month over a big day number. */
@Composable
fun YHDateChip(date: Instant, lime: Boolean = false, size: Dp = 50.dp) {
    Column(
        Modifier.size(size).clip(RoundedCornerShape(size * 0.2f)).background(if (lime) YH.lime else YH.surface),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text(Fmt.monthAbbrev(date), fontSize = (size.value * 0.2f).sp, fontWeight = FontWeight.Bold, letterSpacing = 0.6.sp, color = if (lime) YH.ink else YH.muted)
        Text(Fmt.day(date), fontSize = (size.value * 0.4f).sp, fontWeight = FontWeight.Bold, color = YH.ink, lineHeight = (size.value * 0.44f).sp)
    }
}

/** Horizontal segmented pill row. */
@Composable
fun <T> YHFilterChips(selection: T, options: List<T>, label: (T) -> String, onSelect: (T) -> Unit) {
    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
        options.forEach { option ->
            val selected = option == selection
            Text(
                label(option),
                fontSize = 13.sp,
                fontWeight = FontWeight.SemiBold,
                color = if (selected) Color.White else YH.ink,
                modifier = Modifier
                    .clip(RoundedCornerShape(50))
                    .background(if (selected) YH.ink else YH.surface)
                    .clickable { Haptics.selection(); onSelect(option) }
                    .padding(horizontal = 14.dp, vertical = 7.dp),
            )
        }
    }
}

// ---- Skeletons ---------------------------------------------------------------

/** Phase of the skeleton shimmer sweep, -1 → 1, looping. */
@Composable
private fun shimmerOffset(): Float {
    val transition = rememberInfiniteTransition(label = "shimmer")
    val v by transition.animateFloat(
        initialValue = -1f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1400, easing = LinearEasing), RepeatMode.Restart),
        label = "phase",
    )
    return v
}

@Composable
fun YHSkeletonBlock(modifier: Modifier = Modifier, height: Dp = 14.dp, radius: Dp = 6.dp) {
    val phase = shimmerOffset()
    BoxWithConstraints(modifier.fillMaxWidth().height(height).clip(RoundedCornerShape(radius)).background(YH.surface)) {
        val w = constraints.maxWidth.toFloat()
        Box(
            Modifier.fillMaxSize().background(
                Brush.horizontalGradient(
                    listOf(Color.Transparent, Color.White.copy(alpha = 0.55f), Color.Transparent),
                    startX = phase * w * 1.6f,
                    endX = phase * w * 1.6f + w * 1.6f,
                ),
            ),
        )
    }
}

@Composable
fun YHSkeletonCard(rows: Int = 2) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHSkeletonBlock(height = 16.dp)
            repeat(rows) { YHSkeletonBlock(height = 12.dp) }
        }
    }
}

/** Skeleton bento grid used while the dashboard loads. */
@Composable
fun YHSkeletonBento() {
    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
        repeat(2) {
            Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                repeat(2) {
                    YHCard(Modifier.weight(1f)) {
                        Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            YHSkeletonBlock(height = 10.dp)
                            YHSkeletonBlock(Modifier.width(80.dp), height = 22.dp)
                            YHSkeletonBlock(Modifier.width(60.dp), height = 10.dp)
                        }
                    }
                }
            }
        }
        YHSkeletonCard(rows = 3)
        YHSkeletonCard(rows = 2)
    }
}

// ---- States --------------------------------------------------------------------

/** Lime circle + icon with a gentle pop-in, shared by empty states and reveals. */
@Composable
fun YHHeroIcon(icon: ImageVector) {
    var appeared by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { appeared = true }
    val s by animateFloatAsState(if (appeared) 1f else 0.7f, YH.Motion.bounce(), label = "pop")
    Box(Modifier.scale(s).clip(CircleShape).background(YH.lime).padding(20.dp)) {
        Icon(icon, null, tint = YH.ink, modifier = Modifier.size(42.dp))
    }
}

/** Empty state — icon, ink title, muted body, optional action. */
@Composable
fun YHEmpty(
    icon: ImageVector,
    title: String,
    message: String,
    modifier: Modifier = Modifier,
    actionTitle: String? = null,
    action: (() -> Unit)? = null,
) {
    Column(
        modifier.fillMaxSize().padding(horizontal = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(YH.Space.md, Alignment.CenterVertically),
    ) {
        YHHeroIcon(icon)
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text(title, style = YHType.title3, color = YH.ink, textAlign = TextAlign.Center)
            Text(message, style = YHType.subheadline, color = YH.muted, textAlign = TextAlign.Center)
        }
        if (actionTitle != null && action != null) {
            YHButton(actionTitle, fullWidth = false, onClick = action, modifier = Modifier.padding(top = 4.dp))
        }
    }
}

/** Error state — warning icon + retry. */
@Composable
fun YHErrorState(message: String, modifier: Modifier = Modifier, retry: (() -> Unit)? = null) {
    Column(
        modifier.fillMaxSize().padding(horizontal = 32.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(YH.Space.md, Alignment.CenterVertically),
    ) {
        Icon(Icons.Rounded.WarningAmber, null, tint = YH.danger, modifier = Modifier.size(40.dp))
        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(6.dp)) {
            Text("Something went sideways", style = YHType.title3, color = YH.ink)
            Text(message, style = YHType.subheadline, color = YH.muted, textAlign = TextAlign.Center)
        }
        if (retry != null) YHButton("Try Again", fullWidth = false, onClick = retry, modifier = Modifier.padding(top = 4.dp))
    }
}

/**
 * The four-state list shell: skeleton while loading, error with retry, empty
 * placeholder, or real content.
 */
@Composable
fun YHLoadable(
    isLoading: Boolean,
    isEmpty: Boolean,
    errorMessage: String?,
    onRetry: () -> Unit,
    skeletonCards: Int = 4,
    skeletonRows: Int = 2,
    empty: @Composable () -> Unit,
    content: @Composable () -> Unit,
) {
    when {
        isEmpty && isLoading -> Column(
            Modifier.fillMaxSize().padding(YH.Space.md),
            verticalArrangement = Arrangement.spacedBy(YH.Space.sm),
        ) { repeat(skeletonCards) { YHSkeletonCard(rows = skeletonRows) } }
        isEmpty && errorMessage != null -> YHErrorState(errorMessage, retry = onRetry)
        isEmpty -> empty()
        else -> content()
    }
}

/** The sunflower mark on its forest tile. */
@Composable
fun YHLogo(size: Dp = 72.dp) {
    Image(
        painterResource(R.drawable.sunflower), contentDescription = "YardHarvest",
        modifier = Modifier.size(size).clip(RoundedCornerShape(size * 0.22f)),
    )
}

/** Inline divider in the brand hairline color. */
@Composable
fun YHDivider() = HorizontalDivider(color = YH.border, thickness = 1.dp)

/** A row with a leading icon tile, title, optional trailing badge and chevron. */
@Composable
fun YHNavRow(
    title: String,
    icon: ImageVector,
    badge: Int = 0,
    trailing: (@Composable RowScope.() -> Unit)? = null,
    showsChevron: Boolean = true,
    onClick: () -> Unit,
) {
    val shape = RoundedCornerShape(YH.Radius.md)
    Row(
        Modifier
            .fillMaxWidth()
            .clip(shape)
            .background(YH.canvas)
            .border(1.dp, YH.border, shape)
            .clickable { Haptics.tap(); onClick() }
            .padding(start = YH.Space.md, end = YH.Space.md, top = 14.dp, bottom = 14.dp),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        YHIconTile(icon)
        Text(title, style = YHType.bodyMedium, color = YH.ink, modifier = Modifier.weight(1f))
        if (badge > 0) {
            Text(
                "$badge", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = YH.ink,
                modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.lime).padding(horizontal = 8.dp, vertical = 2.dp),
            )
        }
        trailing?.invoke(this)
        if (showsChevron) Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted, modifier = Modifier.size(18.dp))
    }
}

/** Uppercase muted section label above a group of rows. */
@Composable
fun YHSectionLabel(text: String, modifier: Modifier = Modifier) {
    Text(
        text.uppercase(), style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.muted,
        modifier = modifier.padding(horizontal = 4.dp),
    )
}

/** Error line used under forms. */
@Composable
fun YHInlineError(message: String) {
    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.fillMaxWidth().padding(top = 4.dp)) {
        Icon(Icons.Rounded.WarningAmber, null, tint = YH.danger, modifier = Modifier.size(18.dp))
        Text(message, style = YHType.subheadline, color = YH.danger)
    }
}

/** Spacer helper so screens read like the SwiftUI stacks they mirror. */
@Composable
fun VSpace(h: Dp) = Spacer(Modifier.height(h))

/** Which screens have already played their intro this app session. */
private val revealMemory = mutableSetOf<String>()

/**
 * Plays the lime-circle intro once per [id] per session, then reveals the
 * content — so list screens arrive with the same moment as their empty state,
 * without replaying it on every tab switch.
 */
@Composable
fun YHContentReveal(icon: ImageVector, id: String, caption: String? = null, content: @Composable () -> Unit) {
    var showContent by remember(id) { mutableStateOf(id in revealMemory) }
    LaunchedEffect(id) {
        if (id in revealMemory) { showContent = true; return@LaunchedEffect }
        kotlinx.coroutines.delay(800)
        revealMemory += id
        showContent = true
    }
    androidx.compose.animation.Crossfade(showContent, label = "reveal") { ready ->
        if (ready) {
            content()
        } else {
            Column(
                Modifier.fillMaxSize(),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(YH.Space.md, Alignment.CenterVertically),
            ) {
                YHHeroIcon(icon)
                if (caption != null) Text(caption, style = YHType.subheadline, color = YH.muted)
            }
        }
    }
}
