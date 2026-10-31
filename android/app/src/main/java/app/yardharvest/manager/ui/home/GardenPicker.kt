package app.yardharvest.manager.ui.home

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Eco
import androidx.compose.material.icons.rounded.Place
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Shadow
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.LocalGardenStore
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHErrorState
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHSkeletonCard
import coil.compose.AsyncImage
import kotlinx.coroutines.launch

/** Garden picker — photo cards grouped by role. */
@Composable
fun GardenPickerSheet(onDismiss: () -> Unit) {
    val store = LocalGardenStore.current
    val scope = rememberCoroutineScope()
    YHSheet(onDismiss, title = "Switch Garden", trailing = { YHBarButton("Done", onClick = onDismiss) }) {
        val payload = store.gardens
        when {
            store.isLoading && payload == null -> Box(Modifier.padding(16.dp)) { YHSkeletonCard() }
            payload == null && store.lastError != null -> YHErrorState(store.lastError!!) { scope.launch { store.reload() } }
            payload != null && payload.all.isEmpty() -> YHEmpty(Icons.Rounded.Eco, "No gardens yet", "Join or create a garden on yardharvest.app to get started.")
            payload != null -> YHRefreshable({ store.reload() }) {
                LazyColumn(
                    Modifier.fillMaxSize(),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(YH.Space.md),
                    verticalArrangement = Arrangement.spacedBy(YH.Space.sm),
                ) {
                    fun section(title: String, gardens: List<Garden>, role: String) {
                        if (gardens.isEmpty()) return
                        item(key = "h-$title") { YHSectionLabel(title, Modifier.padding(top = 8.dp)) }
                        items(gardens, key = { "$title-${it.id}" }) { g ->
                            GardenCard(
                                g, role = role, selected = store.selectedGardenId == g.id, compact = true,
                                onClick = { Haptics.selection(); store.selectedGardenId = g.id; onDismiss() },
                            )
                        }
                    }
                    section("Organize", payload.organized, "Admin")
                    section("Helping", payload.helping ?: emptyList(), "Team")
                    section("Plot Holder", payload.plotHolder, "Member")
                    section("Waitlist", payload.waitlisted, "Waitlist")
                }
            }
        }
    }
}

/**
 * Photo-forward garden card with the name overlaid in white — picker row
 * (compact) and dashboard hero (full).
 */
@Composable
fun GardenCard(
    garden: Garden,
    modifier: Modifier = Modifier,
    role: String? = null,
    selected: Boolean = false,
    compact: Boolean = false,
    height: Dp? = null,
    onClick: (() -> Unit)? = null,
) {
    val shape = RoundedCornerShape(YH.Radius.lg)
    val h = height ?: if (compact) 132.dp else 220.dp
    val textShadow = Shadow(Color.Black.copy(alpha = 0.55f), blurRadius = 6f)
    Box(
        modifier
            .fillMaxWidth()
            .height(h)
            .clip(shape)
            .then(if (selected) Modifier.border(3.dp, YH.lime, shape) else Modifier)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier),
    ) {
        // Brand gradient underneath: shows while the photo loads, or if there's none.
        Box(Modifier.fillMaxSize().background(Brush.linearGradient(listOf(YH.forest, YH.forest.copy(alpha = 0.7f)))), contentAlignment = Alignment.Center) {
            Icon(Icons.Rounded.Eco, null, tint = Color.White.copy(alpha = 0.12f), modifier = Modifier.size(64.dp))
        }
        AppEnvironment.mediaUrl(garden.photoUrl)?.let {
            AsyncImage(it, null, contentScale = ContentScale.Crop, modifier = Modifier.fillMaxSize())
        }
        // Scrim concentrated in the bottom of the card so white text stays legible.
        Box(
            Modifier.fillMaxSize().background(
                Brush.verticalGradient(0f to Color.Transparent, 0.45f to Color.Black.copy(alpha = 0.10f), 1f to Color.Black.copy(alpha = 0.72f)),
            ),
        )
        Column(
            Modifier.align(Alignment.BottomStart)
                .padding(start = YH.Space.md, end = if (role != null || selected) 96.dp else YH.Space.md, top = YH.Space.md, bottom = if (compact) 16.dp else 22.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                garden.name,
                style = TextStyle(fontSize = if (compact) 18.sp else 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, shadow = textShadow),
                color = Color.White, maxLines = 2, overflow = TextOverflow.Ellipsis,
            )
            val location = garden.locationLine
            if (location.isNotEmpty()) {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Icon(Icons.Rounded.Place, null, tint = Color.White.copy(alpha = 0.95f), modifier = Modifier.size(if (compact) 12.dp else 14.dp))
                    Text(location, style = TextStyle(fontSize = if (compact) 12.sp else 14.sp, fontWeight = FontWeight.Medium, shadow = textShadow),
                        color = Color.White.copy(alpha = 0.95f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                }
            }
        }
        Row(Modifier.align(Alignment.TopEnd).padding(YH.Space.sm), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            if (selected) Icon(Icons.Rounded.CheckCircle, null, tint = Color.White, modifier = Modifier.size(20.dp).shadow(3.dp, RoundedCornerShape(50)))
            if (role != null) {
                Text(
                    role, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.SemiBold,
                    modifier = Modifier.clip(RoundedCornerShape(50)).background(Color.Black.copy(alpha = 0.35f)).padding(horizontal = 9.dp, vertical = 4.dp),
                )
            }
        }
    }
}
