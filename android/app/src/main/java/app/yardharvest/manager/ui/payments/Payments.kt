package app.yardharvest.manager.ui.payments

import android.Manifest
import android.content.Intent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.KeyboardArrowRight
import androidx.compose.material.icons.automirrored.rounded.ShowChart
import androidx.compose.material.icons.automirrored.rounded.Undo
import androidx.compose.material.icons.rounded.AccountBalance
import androidx.compose.material.icons.rounded.AddCircle
import androidx.compose.material.icons.rounded.ArrowCircleDown
import androidx.compose.material.icons.rounded.AttachMoney
import androidx.compose.material.icons.rounded.Business
import androidx.compose.material.icons.rounded.Cancel
import androidx.compose.material.icons.rounded.Check
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.Close
import androidx.compose.material.icons.rounded.Contactless
import androidx.compose.material.icons.rounded.CreditCard
import androidx.compose.material.icons.rounded.Eco
import androidx.compose.material.icons.rounded.GppMaybe
import androidx.compose.material.icons.rounded.HourglassTop
import androidx.compose.material.icons.rounded.HowToReg
import androidx.compose.material.icons.rounded.Link
import androidx.compose.material.icons.rounded.MobileOff
import androidx.compose.material.icons.rounded.Public
import androidx.compose.material.icons.rounded.Schedule
import androidx.compose.material.icons.rounded.SettingsInputAntenna
import androidx.compose.material.icons.rounded.Verified
import androidx.compose.material.icons.rounded.VerifiedUser
import androidx.compose.material.icons.rounded.WarningAmber
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
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
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.net.toUri
import app.yardharvest.manager.api.adminListDues
import app.yardharvest.manager.api.createInPersonCharge
import app.yardharvest.manager.api.createInPersonDuesPaymentIntent
import app.yardharvest.manager.api.finalizeInPersonDues
import app.yardharvest.manager.api.gardenMoneyFeed
import app.yardharvest.manager.api.gardenPayouts
import app.yardharvest.manager.api.gardenStripeStatus
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.TerminalManager
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.AdminDuesRecord
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.GardenMoneyEvent
import app.yardharvest.manager.model.GardenMoneyFeed
import app.yardharvest.manager.model.GardenMoneyTotals
import app.yardharvest.manager.model.GardenPayoutSummary
import app.yardharvest.manager.model.GardenStripeBalance
import app.yardharvest.manager.model.GardenStripeStatus
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHAvatar
import app.yardharvest.manager.ui.brand.YHBand
import app.yardharvest.manager.ui.brand.YHBandTint
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHDivider
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHFilterChips
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHSectionHeader
import app.yardharvest.manager.ui.brand.YHSectionLabel
import app.yardharvest.manager.ui.brand.YHStatTile
import app.yardharvest.manager.ui.brand.YHTextField
import app.yardharvest.manager.ui.brand.YHType
import app.yardharvest.manager.ui.dues.DuesStatusPill
import app.yardharvest.manager.ui.nav.Dest
import app.yardharvest.manager.ui.nav.LocalNav
import java.text.NumberFormat
import java.util.Currency
import java.util.Locale
import kotlinx.coroutines.launch

// ---- Hub -----------------------------------------------------------------------------

/** Payments hub: Collect Dues, New Sale, and Money — what Stripe did with it afterwards. */
@Composable
fun PaymentHubScreen(garden: Garden) {
    val nav = LocalNav.current
    val context = LocalContext.current
    // Connected-account health, visible BEFORE a charge in front of a member.
    var status by remember { mutableStateOf<GardenStripeStatus?>(null) }
    LaunchedEffect(garden.id) { status = runCatching { ApiClient.gardenStripeStatus(garden.id) }.getOrNull() }
    val unavailable = remember { TerminalManager.tapToPayUnavailableReason(context) }

    YHScreen("Payments") {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHBand {
                Text("TAP TO PAY", style = YHType.captionMed, letterSpacing = 0.8.sp, color = YH.ink)
                Text("Take payments without a card reader.", fontSize = 22.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, color = YH.ink,
                    modifier = Modifier.padding(top = 6.dp))
                Text("Your phone becomes the reader. Funds land in your garden's Stripe Connect account, minus the platform fee.",
                    style = YHType.subheadline, color = YH.ink.copy(alpha = 0.75f), modifier = Modifier.padding(top = 6.dp))
            }
            status?.takeIf { it.needsAttention }?.let { StripeStatusBanner(it, compact = true) }
            unavailable?.let { UnsupportedNotice(it) }
            HubCard("Collect Dues", "Pick a member and charge their annual fee.", Icons.Rounded.HowToReg, lime = true) { nav.push(Dest.AdminDuesList(garden)) }
            HubCard("New Sale", "Tap to Pay for plant starts, deposits, or anything else.", Icons.Rounded.Contactless, lime = false) { nav.push(Dest.AdHocCharge(garden)) }
            HubCard("Money", "Payments, refunds, and when Stripe deposits it.", Icons.AutoMirrored.Rounded.ShowChart, lime = true) { nav.push(Dest.Money(garden)) }
            YHCard {
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                    Icon(Icons.Rounded.AccountBalance, null, tint = YH.muted, modifier = Modifier.size(14.dp))
                    Text("Where the money goes", style = YHType.captionMed, color = YH.muted)
                }
                Text(
                    "All in-person collections route to your garden's Stripe Connect account, minus a small platform fee. Open Money to see every payment, refund and bank deposit without leaving the app.",
                    style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 6.dp),
                )
            }
        }
    }
}

@Composable
private fun HubCard(title: String, subtitle: String, icon: ImageVector, lime: Boolean, onClick: () -> Unit) {
    YHCard(onClick = onClick) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(14.dp)) {
            Box(Modifier.size(56.dp).clip(RoundedCornerShape(14.dp)).background(if (lime) YH.lime else YH.ink), contentAlignment = Alignment.Center) {
                Icon(icon, null, tint = if (lime) YH.ink else YH.lime, modifier = Modifier.size(26.dp))
            }
            Column(Modifier.weight(1f)) {
                Text(title, style = YHType.title3, color = YH.ink)
                Text(subtitle, style = YHType.subheadline, color = YH.muted)
            }
            Icon(Icons.AutoMirrored.Rounded.KeyboardArrowRight, null, tint = YH.muted)
        }
    }
}

@Composable
private fun UnsupportedNotice(reason: String) {
    YHCard {
        Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Box(Modifier.size(32.dp).clip(RoundedCornerShape(9.dp)).background(YH.warning.copy(alpha = 0.15f)), contentAlignment = Alignment.Center) {
                Icon(Icons.Rounded.WarningAmber, null, tint = YH.warning, modifier = Modifier.size(18.dp))
            }
            Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                Text("Tap to Pay unavailable", style = YHType.bodyMedium, color = YH.ink)
                Text(reason, style = YHType.caption, color = YH.muted)
            }
        }
    }
}

/** Shown whenever Stripe says the connected account can't fully do its job. Deliberately loud. */
@Composable
fun StripeStatusBanner(status: GardenStripeStatus, compact: Boolean = false) {
    val context = LocalContext.current
    val tint = if (status.state == "restricted") YH.danger else YH.warning
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                Box(Modifier.size(32.dp).clip(RoundedCornerShape(9.dp)).background(tint.copy(alpha = 0.15f)), contentAlignment = Alignment.Center) {
                    Icon(if (status.state == "not_started") Icons.Rounded.AccountBalance else Icons.Rounded.WarningAmber, null, tint = tint, modifier = Modifier.size(18.dp))
                }
                Column(verticalArrangement = Arrangement.spacedBy(3.dp)) {
                    Text(
                        when (status.state) {
                            "restricted" -> "Stripe paused your payouts"
                            "not_started" -> "No payout account yet"
                            else -> "Stripe needs more information"
                        },
                        style = YHType.bodyMedium, color = YH.ink,
                    )
                    Text(status.message, style = YHType.caption, color = YH.muted)
                }
            }
            if (!compact && status.requirementsDue.isNotEmpty()) {
                Text("Stripe still needs: " + status.requirementsDue.take(3).joinToString(", ") { humanize(it) }, style = YHType.caption, color = YH.muted)
            }
            if (!compact) status.dashboardUrl?.let { url ->
                Text("Open Stripe", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = YH.lime,
                    modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.ink)
                        .clickable { runCatching { context.startActivity(Intent(Intent.ACTION_VIEW, url.toUri())) } }
                        .padding(horizontal = 14.dp, vertical = 7.dp))
            }
        }
    }
}

/** `individual.verification.document` → `Individual verification document`. */
fun humanize(requirement: String): String {
    val words = requirement.replace('.', ' ').replace('_', ' ')
    return words.replaceFirstChar(Char::uppercase)
}

// ---- Dues roster -----------------------------------------------------------------------

private enum class DuesFilter(val label: String) { All("All"), Unpaid("Unpaid"), Paid("Paid") }

/** Every dues record for the garden; each row pushes the Tap to Pay flow. */
@Composable
fun AdminDuesListScreen(garden: Garden) {
    val nav = LocalNav.current
    var dues by remember { mutableStateOf<List<AdminDuesRecord>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(DuesFilter.Unpaid) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { dues = ApiClient.adminListDues(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }
    val filtered = when (filter) {
        DuesFilter.All -> dues
        DuesFilter.Unpaid -> dues.filter { !it.isSettled && it.balance > 0 }
        DuesFilter.Paid -> dues.filter { it.isSettled }
    }

    YHScreen("Collect Dues") {
        YHLoadable(loading, dues.isEmpty(), error, { scope.launch { load() } },
            empty = { YHEmpty(Icons.Rounded.AttachMoney, "No dues yet", "Generate dues for this season on the website to start collecting.") }) {
            YHRefreshable({ load(false) }) {
                LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    item { YHFilterChips(filter, DuesFilter.entries, { it.label }) { filter = it } }
                    items(filtered, key = { it.id }) { r ->
                        YHCard(onClick = { nav.push(Dest.CollectDues(garden, r) { scope.launch { load(false) } }) }) {
                            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                YHAvatar(r.userName, size = 42.dp, background = if (r.isSettled) YH.surface else YH.lime)
                                Column(Modifier.weight(1f)) {
                                    Text(r.userName, style = YHType.bodyMedium, color = YH.ink)
                                    Text(
                                        "${r.seasonYear} · " + if (r.balance > 0) "${Fmt.money(r.balance)} due" else "${Fmt.money(r.amountPaid)} paid",
                                        style = YHType.caption, color = YH.muted,
                                    )
                                }
                                DuesStatusPill(r.status)
                            }
                        }
                    }
                    if (filtered.isEmpty()) item {
                        YHCard { Text(if (filter == DuesFilter.Unpaid) "No unpaid dues 🎉" else "No ${filter.label.lowercase()} dues to show.", style = YHType.subheadline, color = YH.muted) }
                    }
                }
            }
        }
    }
}

// ---- Shared Tap to Pay plumbing ----------------------------------------------------------

private data class PhaseLook(val title: String, val body: String, val icon: ImageVector, val active: Boolean)

/** Charge-flow status copy, shared by the dues and sale screens. */
private fun look(phase: TerminalManager.Phase, quietSetup: Boolean): PhaseLook = when (phase) {
    TerminalManager.Phase.Idle -> PhaseLook("Ready to charge",
        if (quietSetup) "They can pay with a card, Google Pay, or Apple Pay." else "Enter an amount and tap Charge to start.", Icons.Rounded.Contactless, false)
    TerminalManager.Phase.Discovering -> if (quietSetup) look(TerminalManager.Phase.Idle, true)
        else PhaseLook("Finding reader…", "Locating the Tap to Pay reader (your phone).", Icons.Rounded.SettingsInputAntenna, true)
    TerminalManager.Phase.Connecting -> if (quietSetup) look(TerminalManager.Phase.Idle, true)
        else PhaseLook("Connecting…", "Establishing the secure session.", Icons.Rounded.Link, true)
    TerminalManager.Phase.Ready -> if (quietSetup) look(TerminalManager.Phase.Idle, true)
        else PhaseLook("Reader connected", "Setting up payment…", Icons.Rounded.CheckCircle, false)
    TerminalManager.Phase.Collecting -> PhaseLook("Tap card here",
        "Hold the customer's card or contactless phone against the back of this phone, near the NFC area.", Icons.Rounded.Contactless, true)
    TerminalManager.Phase.Processing -> PhaseLook("Processing…", "Stripe is finalizing the charge — keep this screen open.", Icons.Rounded.HourglassTop, true)
    is TerminalManager.Phase.Succeeded -> PhaseLook("Payment received", "Funds will land in the garden's Connect account.", Icons.Rounded.Verified, false)
    TerminalManager.Phase.Canceled -> PhaseLook("Canceled", "Tap Charge to try again.", Icons.Rounded.Cancel, false)
    is TerminalManager.Phase.Failed -> PhaseLook(if (quietSetup) "Couldn't collect" else "Couldn't charge", phase.message, Icons.Rounded.WarningAmber, false)
}

@Composable
private fun StatusBand(phase: TerminalManager.Phase, quietSetup: Boolean) {
    val l = look(phase, quietSetup)
    val failed = phase is TerminalManager.Phase.Failed || phase == TerminalManager.Phase.Canceled
    val pulse = rememberInfiniteTransition(label = "pulse")
    val a by pulse.animateFloat(1f, 0.35f, infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "a")
    YHBand(tint = if (failed) YHBandTint.Dark else YHBandTint.Lime) {
        val fg = if (failed) Color.White else YH.ink
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
            Icon(l.icon, null, tint = fg, modifier = Modifier.size(26.dp).alpha(if (l.active) a else 1f))
            Column {
                Text(l.title, style = YHType.title3, color = fg)
                Text(l.body, style = YHType.subheadline, color = fg.copy(alpha = 0.75f))
            }
        }
    }
}

private val TerminalManager.Phase.isChargeable: Boolean
    get() = when (this) {
        TerminalManager.Phase.Idle, TerminalManager.Phase.Canceled, is TerminalManager.Phase.Failed,
        TerminalManager.Phase.Discovering, TerminalManager.Phase.Connecting, TerminalManager.Phase.Ready -> true
        else -> false
    }

/**
 * Run [action] once the location permission Stripe Terminal requires is
 * granted, asking for it first if needed.
 */
@Composable
private fun rememberWithLocation(onDenied: () -> Unit): (() -> Unit) -> Unit {
    val context = LocalContext.current
    var pending by remember { mutableStateOf<(() -> Unit)?>(null) }
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { grants ->
        val action = pending
        pending = null
        if (grants.values.any { it }) action?.invoke() else onDenied()
    }
    return { action ->
        if (TerminalManager.hasLocationPermission(context)) action()
        else {
            pending = action
            launcher.launch(arrayOf(Manifest.permission.ACCESS_FINE_LOCATION, Manifest.permission.ACCESS_COARSE_LOCATION))
        }
    }
}

private const val LOCATION_DENIED = "Tap to Pay needs location access — card networks require it for fraud protection. Allow it for YardHarvest in Settings, then try again."

// ---- Collect dues -----------------------------------------------------------------------

/**
 * Tap to Pay for one dues record. The reader connects in the background when
 * the screen appears, so the manager sees one Charge button and then the
 * card prompt — the phone *is* the reader.
 */
@Composable
fun AdminCollectDuesScreen(garden: Garden, record: AdminDuesRecord, onChange: () -> Unit) {
    val nav = LocalNav.current
    val context = LocalContext.current
    val terminal = remember { TerminalManager() }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var launching by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val supported = remember { TerminalManager.deviceSupportsTapToPay(context) }
    val withLocation = rememberWithLocation { error = LOCATION_DENIED }
    LaunchedEffect(Unit) { terminal.prepare(context, garden.id) }

    fun begin() {
        // A second tap mid-charge would overlap collects and wedge the SDK.
        if (launching) return
        withLocation {
            scope.launch {
                launching = true
                error = null
                info = null
                try {
                    TerminalManager.currentGardenId = garden.id
                    terminal.connectLocalReader()
                    val intent = ApiClient.createInPersonDuesPaymentIntent(garden.id, record.id)
                    val pid = terminal.collect(intent.clientSecret)
                    info = ApiClient.finalizeInPersonDues(garden.id, record.id, pid)
                    Haptics.success()
                    onChange()
                } catch (e: Exception) {
                    error = TerminalManager.describe(e)
                    Haptics.error()
                } finally {
                    launching = false
                }
            }
        }
    }

    YHScreen("Tap to Pay") {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Member", Modifier.padding(start = 0.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        YHAvatar(record.userName, size = 48.dp)
                        Column {
                            Text(record.userName, style = YHType.bodyMedium, color = YH.ink)
                            Text("${record.seasonYear} season", style = YHType.caption, color = YH.muted)
                        }
                    }
                    YHDivider()
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text("AMOUNT", style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.muted, modifier = Modifier.weight(1f))
                        Text(Fmt.money(record.balance), fontSize = 32.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, color = YH.ink)
                    }
                }
            }
            StatusBand(terminal.phase, quietSetup = true)
            when {
                record.isSettled -> YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Rounded.Verified, null, tint = YH.ink)
                        Text("This record is already settled.", style = YHType.bodyMedium, color = YH.ink)
                    }
                }
                !supported -> YHCard {
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Icon(Icons.Rounded.MobileOff, null, tint = YH.ink)
                        Text("Tap to Pay isn't available", style = YHType.bodyMedium, color = YH.ink)
                    }
                    Text(TerminalManager.tapToPayUnavailableReason(context) ?: "", style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 6.dp))
                    Text("Record the payment manually on the website instead.", style = YHType.caption, color = YH.muted, modifier = Modifier.padding(top = 2.dp))
                }
                terminal.phase is TerminalManager.Phase.Succeeded -> YHButton("Done", icon = Icons.Rounded.Check) { onChange(); nav.pop() }
                terminal.phase.isChargeable -> YHButton("Charge ${Fmt.money(record.balance)}", icon = Icons.Rounded.Contactless,
                    style = YHButtonStyle.Lime, isLoading = launching) { begin() }
                else -> YHButton("Cancel", icon = Icons.Rounded.Close, style = YHButtonStyle.Ghost) { terminal.cancelInFlight() }
            }
            info?.let { Text(it, style = YHType.subheadline, color = YH.ink) }
            error?.let { YHInlineError(it) }
        }
    }
}

// ---- Ad-hoc sale ---------------------------------------------------------------------------

/**
 * "Plain terminal": an ad-hoc Tap to Pay charge for any amount and memo —
 * plant starts, tool deposits, workshop fees. Stripe is the receipt trail.
 */
@Composable
fun AdHocChargeScreen(garden: Garden) {
    val nav = LocalNav.current
    val context = LocalContext.current
    val terminal = remember { TerminalManager() }
    var amountText by remember { mutableStateOf("") }
    var memo by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var launching by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    val supported = remember { TerminalManager.deviceSupportsTapToPay(context) }
    val withLocation = rememberWithLocation { error = LOCATION_DENIED }
    LaunchedEffect(Unit) { terminal.prepare(context, garden.id) }

    // Stripe's 50¢ minimum and a $10,000 ceiling; the backend enforces both.
    val amountCents = amountText.replace(",", "").toDoubleOrNull()?.let { Math.round(it * 100).toInt() } ?: 0
    val canCharge = amountCents in 50..1_000_000 && terminal.phase != TerminalManager.Phase.Processing && supported

    fun begin() {
        if (launching) return
        withLocation {
            scope.launch {
                launching = true
                error = null
                info = null
                try {
                    TerminalManager.currentGardenId = garden.id
                    terminal.connectLocalReader()
                    val intent = ApiClient.createInPersonCharge(garden.id, amountCents, memo.trim())
                    terminal.collect(intent.clientSecret)
                    info = "Charged ${Fmt.moneyCents(amountCents)}."
                    Haptics.success()
                } catch (e: Exception) {
                    error = TerminalManager.describe(e)
                    Haptics.error()
                } finally {
                    launching = false
                }
            }
        }
    }

    YHScreen("New Sale") {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
            if (!supported) TerminalManager.tapToPayUnavailableReason(context)?.let { UnsupportedNotice(it) }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Amount", Modifier.padding(start = 0.dp))
                    Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text("$", fontSize = 36.sp, fontWeight = FontWeight.Bold, color = YH.muted)
                        BasicTextField(
                            amountText, { amountText = it.filter { c -> c.isDigit() || c == '.' || c == ',' } }, singleLine = true,
                            textStyle = TextStyle(fontSize = 36.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.5).sp, color = YH.ink),
                            cursorBrush = SolidColor(YH.ink), keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                            modifier = Modifier.weight(1f),
                            decorationBox = { inner ->
                                if (amountText.isEmpty()) Text("0.00", fontSize = 36.sp, fontWeight = FontWeight.Bold, color = YH.muted.copy(alpha = 0.4f))
                                inner()
                            },
                        )
                    }
                    Row(Modifier.horizontalScroll(rememberScrollState()), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        listOf(5, 10, 20, 50, 100).forEach { d ->
                            Text("$$d", fontSize = 13.sp, fontWeight = FontWeight.SemiBold, color = YH.ink,
                                modifier = Modifier.clip(RoundedCornerShape(50)).background(YH.surface)
                                    .clickable { Haptics.selection(); amountText = "$d.00" }.padding(horizontal = 12.dp, vertical = 6.dp))
                        }
                    }
                }
            }
            YHCard {
                Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    YHSectionLabel("Memo", Modifier.padding(start = 0.dp))
                    YHTextField(memo, { memo = it }, placeholder = "What's this for? (e.g. 4 tomato starts)", singleLine = false,
                        textStyle = YHType.body.copy(color = YH.ink), autoCorrect = true)
                    Text("Shows up on the cardholder's receipt + your Stripe dashboard.", style = YHType.caption, color = YH.muted)
                }
            }
            StatusBand(terminal.phase, quietSetup = false)
            when {
                terminal.phase is TerminalManager.Phase.Succeeded -> {
                    YHButton("New Sale", icon = Icons.Rounded.AddCircle, style = YHButtonStyle.Lime) {
                        amountText = ""; memo = ""; info = null; terminal.reset()
                    }
                    YHButton("Done", icon = Icons.Rounded.Check, style = YHButtonStyle.Ghost) { nav.pop() }
                }
                terminal.phase.isChargeable -> YHButton(
                    if (amountCents < 50) "Enter an amount" else "Charge ${Fmt.moneyCents(amountCents)}",
                    icon = Icons.Rounded.Contactless, style = YHButtonStyle.Lime, isLoading = launching, enabled = canCharge,
                ) { begin() }
                else -> YHButton("Cancel", icon = Icons.Rounded.Close, style = YHButtonStyle.Ghost) { terminal.cancelInFlight() }
            }
            info?.let { Text(it, style = YHType.subheadline, color = YH.ink) }
            error?.let { YHInlineError(it) }
        }
    }
}

// ---- Money ---------------------------------------------------------------------------------

private enum class MoneyFilter(val label: String, val kinds: String?) {
    All("All", null), Collected("Collected", "payment,payment_failed"), Out("Refunds & disputes", "refund,dispute"), Deposits("Deposits", "payout"),
}

/**
 * What Stripe actually did with this garden's money. Every row comes from a
 * webhook, so it reflects what happened rather than what this phone last saw.
 */
@Composable
fun MoneyScreen(garden: Garden) {
    var feed by remember { mutableStateOf<GardenMoneyFeed?>(null) }
    var payouts by remember { mutableStateOf<GardenPayoutSummary?>(null) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var filter by remember { mutableStateOf(MoneyFilter.All) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true, refreshPayouts: Boolean = false) {
        if (spinner) loading = true
        error = null
        try { feed = ApiClient.gardenMoneyFeed(garden.id, kind = filter.kinds) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
        // Payouts are account-level and don't change with the filter.
        if (payouts == null || refreshPayouts) payouts = runCatching { ApiClient.gardenPayouts(garden.id) }.getOrNull()
    }
    LaunchedEffect(garden.id, filter) { load() }
    val events = feed?.events.orEmpty()

    val empty: @Composable () -> Unit = {
        YHEmpty(Icons.Rounded.CreditCard, "No card activity yet",
            "Dues paid online and anything you collect with Tap to Pay will show up here, along with your bank deposits.")
    }

    YHScreen("Money") {
        YHLoadable(loading, events.isEmpty() && feed == null, error, { scope.launch { load() } }, skeletonCards = 5, skeletonRows = 2, empty = empty) {
            YHRefreshable({ load(spinner = false, refreshPayouts = true) }) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(start = YH.Space.md, end = YH.Space.md, top = YH.Space.md, bottom = YH.Space.xl),
                    verticalArrangement = Arrangement.spacedBy(YH.Space.md)) {
                    feed?.stripeStatus?.takeIf { it.needsAttention }?.let { StripeStatusBanner(it) }
                    feed?.totals?.let { MoneyBento(it, payouts?.balance) }
                    payouts?.let { PayoutCard(it) }
                    YHFilterChips(filter, MoneyFilter.entries, { it.label }) { filter = it }
                    if (events.isEmpty()) {
                        Box(Modifier.heightIn(min = 200.dp)) { empty() }
                    } else {
                        YHCard {
                            events.forEachIndexed { i, e ->
                                MoneyRow(e)
                                if (i < events.lastIndex) Box(Modifier.padding(vertical = 10.dp)) { YHDivider() }
                            }
                        }
                    }
                    Text("Showing the last ${feed?.windowDays ?: 90} days.", style = YHType.caption, color = YH.tertiary,
                        modifier = Modifier.fillMaxWidth(), textAlign = androidx.compose.ui.text.style.TextAlign.Center)
                }
            }
        }
    }
}

/** Dollars, with cents under $100 — the iOS money format. */
private fun money(v: Double): String {
    val f = NumberFormat.getCurrencyInstance(Locale.US)
    val digits = if (kotlin.math.abs(v) < 100) 2 else 0
    f.minimumFractionDigits = digits
    f.maximumFractionDigits = digits
    return f.format(v)
}

/**
 * Balance figures arrive in CENTS, unlike every other money field. A separate
 * function keeps the two from ever being confused at a call site.
 */
private fun moneyCents(cents: Int) = money(cents / 100.0)

@Composable
private fun MoneyBento(t: GardenMoneyTotals, balance: GardenStripeBalance?) {
    // False when not one payment's Stripe fee is known: a dash is the honest rendering.
    val netKnown = t.paymentCount == 0 || t.unknownFeeCount < t.paymentCount
    val keptDetail = when {
        !netKnown -> "no Stripe fees looked up yet"
        !t.feesComplete -> "at most - some fees unknown"
        else -> {
            val parts = buildList {
                if (t.stripeFees > 0) add("Stripe fees")
                if (t.fees > 0) add("platform fee")
                if (t.refunded > 0) add("refunds")
            }
            if (parts.isEmpty()) "nothing deducted" else "after " + parts.joinToString(" and ")
        }
    }
    Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
        Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHStatTile("Charged", money(t.collected), Modifier.weight(1f), detail = if (t.paymentCount == 1) "1 payment" else "${t.paymentCount} payments", icon = Icons.Rounded.ArrowCircleDown)
            YHStatTile("Net received", if (netKnown) money(t.kept) else "-", Modifier.weight(1f), detail = keptDetail, icon = Icons.Rounded.Eco)
        }
        Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            YHStatTile("Stripe fees", money(t.stripeFees) + if (t.feesComplete) "" else "+", Modifier.weight(1f),
                detail = if (t.feesComplete) "card processing" else "${t.unknownFeeCount} not looked up yet", icon = Icons.Rounded.CreditCard)
            // YardHarvest charges no platform fee on garden collections; the tile
            // appears only when there is actually something on it.
            if (t.showsPlatformFee) YHStatTile("Platform fee", money(t.fees), Modifier.weight(1f), detail = "YardHarvest", icon = Icons.Rounded.Business)
            else Box(Modifier.weight(1f))
        }
        // Stripe's own count of what it holds — answers "what will I be paid"
        // even when no webhook ever arrived.
        balance?.let { b ->
            Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                YHStatTile("Available", moneyCents(b.available), Modifier.weight(1f), detail = if (b.available < 0) "owed to Stripe" else "ready for payout", icon = Icons.Rounded.CheckCircle)
                YHStatTile("Pending", moneyCents(b.pending), Modifier.weight(1f), detail = "still settling", icon = Icons.Rounded.Schedule)
            }
        }
        if (t.refunded > 0 || t.disputed > 0) {
            Row(horizontalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                YHStatTile("Refunded", money(t.refunded), Modifier.weight(1f), detail = "returned to payers", icon = Icons.AutoMirrored.Rounded.Undo)
                YHStatTile("Disputed", money(t.disputed), Modifier.weight(1f), detail = "held by Stripe", icon = Icons.Rounded.GppMaybe)
            }
        }
    }
}

@Composable
private fun PayoutCard(s: GardenPayoutSummary) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.xs)) {
            YHSectionHeader("To your bank", icon = Icons.Rounded.AccountBalance, trailing = money(s.paidTotal))
            s.balance?.let { b ->
                var text = "Stripe holds ${moneyCents(b.total)} for you — ${moneyCents(b.available)} available, ${moneyCents(b.pending)} pending."
                s.schedule?.description?.takeIf { it.isNotEmpty() }?.let { text += " $it" }
                Text(text, style = YHType.subheadline, color = YH.ink)
                if (b.available < 0) {
                    Text(
                        "A negative available balance means Stripe is owed that much, usually after a refund or fee landed before there were cleared funds to cover it. It comes out of the pending money as that settles — there is nothing for you to pay.",
                        style = YHType.caption, color = YH.muted,
                    )
                }
            }
            val last = s.lastPayoutAt
            if (last != null) {
                Text(
                    "Last deposit ${money(s.lastPayoutAmount)} ${Fmt.relative(last)} — ${money(s.paidTotal)} across ${s.paidCount} ${if (s.paidCount == 1) "deposit" else "deposits"} in this window.",
                    style = YHType.subheadline, color = YH.muted,
                )
            } else {
                Text("No deposits yet in this window. Stripe pays out on its own schedule once your account is verified.", style = YHType.subheadline, color = YH.muted)
            }
            if (s.failedCount > 0) YHPill(if (s.failedCount == 1) "1 failed payout" else "${s.failedCount} failed payouts", icon = Icons.Rounded.WarningAmber, tint = YH.danger)
            // Payouts belong to the Stripe account, which may span several gardens.
            Text("Deposits cover everything on your Stripe account, which may include your other gardens.", style = YHType.caption, color = YH.tertiary)
        }
    }
}

/** One money event; the label is server-rendered so the wording matches web and push. */
@Composable
private fun MoneyRow(e: GardenMoneyEvent) {
    val tint = when {
        e.isTrouble -> YH.danger
        e.kind == "payout" -> YH.success
        else -> YH.ink
    }
    val icon = when (e.kind) {
        "payment" -> if (e.source == "dues_online") Icons.Rounded.Public else Icons.Rounded.Contactless
        "payment_failed" -> Icons.Rounded.Cancel
        "refund" -> Icons.AutoMirrored.Rounded.Undo
        "dispute" -> Icons.Rounded.GppMaybe
        "payout" -> Icons.Rounded.AccountBalance
        else -> Icons.Rounded.VerifiedUser
    }
    Row(verticalAlignment = Alignment.Top, horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        Box(Modifier.size(34.dp).clip(RoundedCornerShape(10.dp)).background(tint.copy(alpha = 0.14f)), contentAlignment = Alignment.Center) {
            Icon(icon, null, tint = tint, modifier = Modifier.size(18.dp))
        }
        Column(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(2.dp)) {
            Text(e.label, style = YHType.bodyMedium, color = YH.ink)
            val meta = listOfNotNull(e.occurredAt?.let { Fmt.dateTime(it) }, if (e.scope == "account") "account-wide" else null)
            if (meta.isNotEmpty()) Text(meta.joinToString(" · "), style = YHType.caption, color = YH.muted)
            if (!e.description.isNullOrEmpty()) Text(e.description, style = YHType.caption, color = YH.tertiary, maxLines = 2)
        }
        if (e.kind != "account") {
            val f = NumberFormat.getCurrencyInstance(Locale.US).apply {
                runCatching { currency = Currency.getInstance((e.currency ?: "usd").uppercase()) }
            }
            val value = f.format(e.amount)
            Text(if (e.isOutgoing) "-$value" else value, fontSize = 15.sp, fontWeight = FontWeight.SemiBold,
                color = if (e.isOutgoing) YH.danger else YH.ink)
        }
    }
}
