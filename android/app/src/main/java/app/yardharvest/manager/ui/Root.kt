package app.yardharvest.manager.ui

import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.Fingerprint
import androidx.compose.material.icons.rounded.Lock
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import app.yardharvest.manager.core.AppLock
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.AuthState
import app.yardharvest.manager.ui.auth.LoginScreen
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHLogo
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.home.HomeShell
import kotlinx.coroutines.launch

/** Root auth gate: splash → login → tab shell, with the app lock above everything. */
@Composable
fun YardHarvestRoot() {
    MaterialTheme(
        colorScheme = lightColorScheme(
            primary = YH.ink, onPrimary = YH.canvas, secondary = YH.lime, onSecondary = YH.ink,
            background = YH.canvas, surface = YH.canvas, onSurface = YH.ink, onBackground = YH.ink,
            surfaceVariant = YH.surface, outline = YH.border, error = YH.danger,
        ),
    ) {
        LaunchedEffect(Unit) { AuthManager.bootstrap() }
        val state = AuthManager.state
        val lock = AppLock.shared
        Box(Modifier.fillMaxSize().background(YH.canvas)) {
            AnimatedContent(
                targetState = when (state) { AuthState.Unknown -> 0; AuthState.SignedOut -> 1; is AuthState.SignedIn -> 2 },
                transitionSpec = {
                    if (targetState == 1) (slideInVertically { it / 3 } + fadeIn()) togetherWith fadeOut()
                    else fadeIn() togetherWith fadeOut()
                },
                label = "auth",
            ) { key ->
                when (key) {
                    0 -> SplashScreen()
                    1 -> LoginScreen()
                    else -> (AuthManager.state as? AuthState.SignedIn)?.let { HomeShell(it.user) }
                }
            }
            // Only over a signed-in session: nothing to protect on the login
            // screen, and covering the splash would race the bootstrap.
            AnimatedVisibility(
                visible = lock.isLocked && state is AuthState.SignedIn,
                enter = fadeIn(), exit = fadeOut(),
            ) { LockScreen(lock) }
        }
    }
}

/** Sunflower mark with a gentle entrance while the auth bootstrap runs. */
@Composable
fun SplashScreen() {
    var appeared by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { appeared = true }
    val s by animateFloatAsState(if (appeared) 1f else 0.85f, YH.Motion.bounce(), label = "s")
    val a by animateFloatAsState(if (appeared) 1f else 0f, label = "a")
    Column(
        Modifier.fillMaxSize().background(YH.canvas),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(YH.Space.lg, Alignment.CenterVertically),
    ) {
        Box(Modifier.scale(s).alpha(a)) { YHLogo(104.dp) }
        Text("YardHarvest", style = YHType.title2, color = YH.ink, modifier = Modifier.alpha(a))
        CircularProgressIndicator(Modifier.size(22.dp).alpha(a), color = YH.ink, strokeWidth = 2.dp)
    }
}

/**
 * Covers the app while the lock is engaged. Deliberately opaque and
 * content-free. One automatic attempt on appear; the button is for after a
 * cancel or a failure.
 */
@Composable
fun LockScreen(lock: AppLock) {
    var working by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    suspend fun attempt() {
        if (working) return
        working = true
        try { lock.unlock() } finally { working = false }
    }
    LaunchedEffect(Unit) { attempt() }
    Column(
        Modifier.fillMaxSize().background(YH.canvas).navigationBarsPadding().padding(horizontal = YH.Space.lg),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Spacer(Modifier.weight(1f))
        Box(Modifier.clip(RoundedCornerShape(YH.Radius.lg)).background(YH.lime).padding(28.dp)) {
            Icon(Icons.Rounded.Lock, null, tint = YH.ink, modifier = Modifier.size(44.dp))
        }
        Spacer(Modifier.size(YH.Space.lg))
        Text("YardHarvest is locked", style = YHType.title2, color = YH.ink)
        Spacer(Modifier.size(6.dp))
        val ctx = LocalContext.current
        Text(
            "Unlock with ${AppLock.biometryName(ctx) ?: "your screen lock"} to carry on.",
            style = YHType.subheadline, color = YH.muted, textAlign = TextAlign.Center,
        )
        lock.lastError?.let {
            Spacer(Modifier.size(YH.Space.md))
            Text(it, style = YHType.caption, color = YH.danger, textAlign = TextAlign.Center)
        }
        Spacer(Modifier.weight(1f))
        YHButton("Unlock", icon = Icons.Rounded.Fingerprint, isLoading = working, onClick = { scope.launch { attempt() } })
        Spacer(Modifier.size(YH.Space.xl))
    }
}
