package app.yardharvest.manager.ui.auth

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowForward
import androidx.compose.material.icons.automirrored.rounded.Send
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.Info
import androidx.compose.material.icons.rounded.Key
import androidx.compose.material.icons.rounded.MarkEmailRead
import androidx.compose.material.icons.rounded.Settings
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.forgotPassword
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.ApiError
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.AuthManager
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBarButton
import app.yardharvest.manager.ui.brand.YHBarIcon
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLogo
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHSheet
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlin.random.Random

private enum class AuthSheet { Settings, Register, ForgotPassword }

/** Sign-in: lime hero band, then a clean form on canvas. */
@Composable
fun LoginScreen() {
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var submitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf(AuthManager.lastError) }
    var sheet by remember { mutableStateOf<AuthSheet?>(null) }
    val scope = rememberCoroutineScope()
    val focus = LocalFocusManager.current
    val passwordFocus = remember { FocusRequester() }

    fun submit() {
        if (submitting || email.isBlank() || password.isEmpty()) return
        scope.launch {
            submitting = true
            error = null
            try {
                AuthManager.signIn(email.trim(), password)
            } catch (e: Exception) {
                Haptics.error()
                error = e.userMessage
            } finally {
                submitting = false
            }
        }
    }

    Column(Modifier.fillMaxSize().background(YH.canvas).windowInsetsPadding(WindowInsets.statusBars).imePadding()) {
        Row(Modifier.fillMaxWidth().padding(horizontal = 4.dp), horizontalArrangement = Arrangement.End) {
            YHBarIcon(Icons.Rounded.Settings, "Connection settings") { sheet = AuthSheet.Settings }
        }
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState())
                .padding(start = YH.Space.lg, end = YH.Space.lg, bottom = YH.Space.xxl),
            verticalArrangement = Arrangement.spacedBy(YH.Space.xl),
        ) {
            YHBand {
                YHLogo(56.dp)
                Spacer(Modifier.height(YH.Space.md))
                Text("Your garden,", fontSize = 30.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.6).sp, color = YH.ink)
                Text("in your pocket.", fontSize = 30.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.6).sp, color = YH.ink)
                Spacer(Modifier.height(8.dp))
                Text(
                    "Sign up for shifts, log your harvests, scan tools, and keep up with the people you grow with.",
                    style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f),
                )
            }

            Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                YHTextField(
                    email, { email = it }, label = "Email", keyboardType = KeyboardType.Email,
                    imeAction = ImeAction.Next, onImeAction = { passwordFocus.requestFocus() },
                )
                YHTextField(
                    password, { password = it }, label = "Password", isPassword = true,
                    imeAction = ImeAction.Go, onImeAction = { submit() },
                    modifier = Modifier.focusRequester(passwordFocus),
                )
                AnimatedVisibility(error != null) { YHInlineError(error ?: "") }
                YHButton(
                    "Sign In", icon = Icons.AutoMirrored.Rounded.ArrowForward, isLoading = submitting,
                    enabled = email.isNotBlank() && password.isNotEmpty(),
                    modifier = Modifier.padding(top = YH.Space.xs),
                    onClick = { focus.clearFocus(); submit() },
                )
                Text(
                    "Forgot password?", style = YHType.subheadline, color = YH.muted,
                    textDecoration = TextDecoration.Underline,
                    modifier = Modifier.align(Alignment.CenterHorizontally).padding(top = YH.Space.xs)
                        .clip(RoundedCornerShape(6.dp))
                        .clickable { Haptics.tap(); focus.clearFocus(); sheet = AuthSheet.ForgotPassword }
                        .padding(6.dp),
                )
            }

            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(YH.Space.md),
                modifier = Modifier.fillMaxWidth().padding(top = YH.Space.md)) {
                Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("New here?", style = YHType.caption, color = YH.muted)
                    Text(
                        "Create an account", style = YHType.bodyMedium, color = YH.ink,
                        textDecoration = TextDecoration.Underline,
                        modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { Haptics.tap(); sheet = AuthSheet.Register }.padding(6.dp),
                    )
                }
                ManagerNote("Running a garden? Register your garden at ")
            }
        }
    }

    when (sheet) {
        AuthSheet.Settings -> ConnectionSettingsSheet { sheet = null }
        AuthSheet.Register -> RegisterSheet { sheet = null }
        AuthSheet.ForgotPassword -> ForgotPasswordSheet(email.trim()) { sheet = null }
        null -> {}
    }
}

@Composable
private fun ManagerNote(lead: String) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.md)).background(YH.surface)
            .padding(horizontal = YH.Space.md, vertical = YH.Space.sm),
        horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(Icons.Rounded.Info, null, tint = YH.muted, modifier = Modifier.size(14.dp))
        Text(
            buildAnnotatedString {
                append(lead)
                withStyle(SpanStyle(color = YH.ink, fontWeight = FontWeight.SemiBold)) { append("yardharvest.app") }
            },
            style = YHType.caption, color = YH.muted, textAlign = TextAlign.Center,
        )
    }
}

/**
 * Password recovery. The reset happens on the web — this only requests the
 * email. The server reports success for any well-formed address, so the
 * confirmation is deliberately non-committal.
 */
@Composable
fun ForgotPasswordSheet(initialEmail: String, onDismiss: () -> Unit) {
    var email by remember { mutableStateOf(initialEmail) }
    var submitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var sent by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val fieldFocus = remember { FocusRequester() }
    val canSubmit = !submitting && email.contains("@") && !email.startsWith("@")

    LaunchedEffect(Unit) {
        if (email.isEmpty()) { delay(400); runCatching { fieldFocus.requestFocus() } }
    }

    fun submit() {
        if (!canSubmit) return
        scope.launch {
            submitting = true
            error = null
            try {
                ApiClient.forgotPassword(email.trim().lowercase())
                Haptics.success()
                sent = true
            } catch (e: ApiError.RateLimited) {
                Haptics.error()
                error = "Too many reset requests. Please wait a while before trying again."
            } catch (e: Exception) {
                Haptics.error()
                error = e.userMessage
            } finally {
                submitting = false
            }
        }
    }

    YHSheet(
        onDismiss = onDismiss,
        title = if (sent) null else "Reset Password",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) },
    ) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = YH.Space.lg, vertical = YH.Space.lg),
            verticalArrangement = Arrangement.spacedBy(YH.Space.xl),
        ) {
            YHBand {
                Icon(if (sent) Icons.Rounded.MarkEmailRead else Icons.Rounded.Key, null, tint = YH.ink, modifier = Modifier.size(26.dp))
                Spacer(Modifier.height(YH.Space.sm))
                Text(if (sent) "Check your email." else "Forgot your password?", fontSize = 26.sp, fontWeight = FontWeight.SemiBold, letterSpacing = (-0.5).sp, color = YH.ink)
                Spacer(Modifier.height(YH.Space.sm))
                Text(
                    if (sent) "If an account exists for that address, we've sent a link to choose a new password. It expires in an hour."
                    else "Enter the email you signed up with and we'll send you a link to set a new one.",
                    style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f),
                )
            }
            if (sent) {
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.md)).background(YH.surface).padding(YH.Space.md),
                    horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(Icons.Rounded.Info, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                    Text("Didn't get it? Check your spam folder, or try again in a few minutes.", style = YHType.caption, color = YH.muted)
                }
                YHButton("Back to Sign In", onClick = onDismiss)
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHTextField(
                        email, { email = it }, label = "Email", keyboardType = KeyboardType.Email,
                        imeAction = ImeAction.Go, onImeAction = { submit() }, modifier = Modifier.focusRequester(fieldFocus),
                    )
                    error?.let { YHInlineError(it) }
                    YHButton("Send Reset Link", icon = Icons.AutoMirrored.Rounded.Send, isLoading = submitting, enabled = canSubmit,
                        modifier = Modifier.padding(top = YH.Space.xs), onClick = { submit() })
                }
            }
        }
    }
}

/** Gardener registration in two steps. Managers register on yardharvest.app. */
@Composable
fun RegisterSheet(onDismiss: () -> Unit) {
    var step by rememberSaveable { mutableIntStateOf(0) }
    var displayName by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var address by rememberSaveable { mutableStateOf("") }
    var city by rememberSaveable { mutableStateOf("") }
    var region by rememberSaveable { mutableStateOf("") }
    var zip by rememberSaveable { mutableStateOf("") }
    var submitting by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    val canAdvance = if (step == 0) displayName.isNotEmpty() && email.contains("@") && password.length >= 8
    else address.isNotEmpty() && city.isNotEmpty() && region.length == 2 && zip.length == 5

    /** Username from the email plus a small random tag, so similar signups don't collide. */
    fun makeUsername(): String {
        val prefix = email.substringBefore("@").ifEmpty { "gardener" }
        val cleaned = prefix.lowercase().filter { it.isLetterOrDigit() || it == '_' || it == '.' }
        return "${cleaned.take(20)}_${Random.nextInt(100, 1000)}"
    }

    fun advance() {
        if (!canAdvance || submitting) return
        if (step == 0) { step = 1; error = null; Haptics.tap(); return }
        scope.launch {
            submitting = true
            error = null
            try {
                AuthManager.signUp(
                    email.trim(), password, displayName.trim(), makeUsername(),
                    address.trim(), city.trim(), region.uppercase(), zip.trim(),
                )
                onDismiss()
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                submitting = false
            }
        }
    }

    YHSheet(onDismiss, title = "Create Account", leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) }) {
        Column(
            Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.lg),
            verticalArrangement = Arrangement.spacedBy(YH.Space.lg),
        ) {
            YHBand {
                Text("WELCOME TO YARDHARVEST", style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.ink)
                Spacer(Modifier.height(4.dp))
                Text(if (step == 0) "Let's set up your account." else "Where do you garden?",
                    fontSize = 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, color = YH.ink)
            }
            Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                repeat(2) { i ->
                    Box(Modifier.weight(1f).height(4.dp).clip(RoundedCornerShape(50)).background(if (i <= step) YH.ink else YH.surface))
                }
            }
            if (step == 0) {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHTextField(displayName, { displayName = it }, label = "Your name", placeholder = "What should we call you?",
                        capitalization = KeyboardCapitalization.Words, autoCorrect = true)
                    YHTextField(email, { email = it }, label = "Email", placeholder = "you@example.com", keyboardType = KeyboardType.Email)
                    YHTextField(password, { password = it }, label = "Password", placeholder = "At least 8 characters", isPassword = true)
                }
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHTextField(address, { address = it }, label = "Address", placeholder = "Street", capitalization = KeyboardCapitalization.Words)
                    Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                        YHTextField(city, { city = it }, label = "City", capitalization = KeyboardCapitalization.Words, modifier = Modifier.weight(1f))
                        YHTextField(region, { region = it.take(2) }, label = "State", capitalization = KeyboardCapitalization.Characters, modifier = Modifier.width(88.dp))
                    }
                    YHTextField(zip, { zip = it.filter(Char::isDigit).take(5) }, label = "ZIP", keyboardType = KeyboardType.Number)
                }
            }
            error?.let { YHInlineError(it) }
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                YHButton(
                    if (step == 0) "Continue" else "Create Account",
                    icon = if (step == 0) Icons.AutoMirrored.Rounded.ArrowForward else Icons.Rounded.Check,
                    style = if (step == 0) YHButtonStyle.Dark else YHButtonStyle.Lime,
                    isLoading = submitting, enabled = canAdvance, onClick = { advance() },
                )
                if (step == 1) {
                    Text("Back", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = YH.muted,
                        modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable { Haptics.tap(); step = 0 }.padding(8.dp))
                }
            }
            Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp),
                modifier = Modifier.fillMaxWidth().padding(top = YH.Space.sm)) {
                Text("By creating an account you agree to YardHarvest's terms.", style = YHType.caption, color = YH.muted, textAlign = TextAlign.Center)
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                    Icon(Icons.Rounded.Info, null, tint = YH.muted, modifier = Modifier.size(12.dp))
                    Text("Running a garden? Register it at yardharvest.app.", style = YHType.caption, color = YH.muted)
                }
            }
        }
    }
}

/** Runtime override for the API base URL — for QA and local backend testing. */
@Composable
fun ConnectionSettingsSheet(onDismiss: () -> Unit) {
    var url by remember { mutableStateOf(AppEnvironment.baseUrl) }
    YHSheet(
        onDismiss, title = "Connection",
        leading = { YHBarButton("Cancel", bold = false, color = YH.muted, onClick = onDismiss) },
        trailing = { YHBarButton("Save") { AppEnvironment.setBaseUrlOverride(url); onDismiss() } },
    ) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHSectionLabel("Base URL")
            YHTextField(url, { url = it }, placeholder = AppEnvironment.DEFAULT_BASE_URL, keyboardType = KeyboardType.Uri)
            YHButton("Use Production", style = YHButtonStyle.Ghost) { url = AppEnvironment.DEFAULT_BASE_URL }
            YHButton("Use Local Server (Emulator)", style = YHButtonStyle.Ghost) { url = "http://10.0.2.2:5000" }
            Text(
                "Reset to Default", color = YH.danger, fontWeight = FontWeight.SemiBold,
                modifier = Modifier.clip(RoundedCornerShape(6.dp)).clickable {
                    AppEnvironment.setBaseUrlOverride(null)
                    url = AppEnvironment.DEFAULT_BASE_URL
                }.padding(8.dp),
            )
            Text("Default targets the Render-hosted backend. Override only for local backend testing.", style = YHType.caption, color = YH.muted)
        }
    }
}
