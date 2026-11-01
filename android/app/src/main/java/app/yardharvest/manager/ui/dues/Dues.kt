package app.yardharvest.manager.ui.dues

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.rounded.AttachMoney
import androidx.compose.material.icons.rounded.CheckCircle
import androidx.compose.material.icons.rounded.CreditCard
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
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.api.confirmDuesPayment
import app.yardharvest.manager.api.myDues
import app.yardharvest.manager.api.payDues
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.core.userMessage
import app.yardharvest.manager.model.DuesPaymentIntent
import app.yardharvest.manager.model.DuesRecord
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.ui.brand.Fmt
import app.yardharvest.manager.ui.brand.YH
import app.yardharvest.manager.ui.brand.YHButton
import app.yardharvest.manager.ui.brand.YHButtonStyle
import app.yardharvest.manager.ui.brand.YHCard
import app.yardharvest.manager.ui.brand.YHEmpty
import app.yardharvest.manager.ui.brand.YHInlineError
import app.yardharvest.manager.ui.brand.YHLoadable
import app.yardharvest.manager.ui.brand.YHPill
import app.yardharvest.manager.ui.brand.YHRefreshable
import app.yardharvest.manager.ui.brand.YHScreen
import app.yardharvest.manager.ui.brand.YHType
import com.stripe.android.PaymentConfiguration
import com.stripe.android.paymentsheet.PaymentSheet
import com.stripe.android.paymentsheet.PaymentSheetResult
import kotlinx.coroutines.launch

/**
 * My dues: one card per season with a Pay button on anything owed. Pay →
 * the backend creates a Stripe PaymentIntent → Stripe's PaymentSheet → on
 * success, confirm-payment marks it paid.
 */
@Composable
fun MyDuesScreen(garden: Garden) {
    val context = LocalContext.current
    var dues by remember { mutableStateOf<List<DuesRecord>>(emptyList()) }
    var loading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var info by remember { mutableStateOf<String?>(null) }
    var target by remember { mutableStateOf<DuesRecord?>(null) }
    var pendingIntent by remember { mutableStateOf<DuesPaymentIntent?>(null) }
    var creatingIntent by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()

    suspend fun load(spinner: Boolean = true) {
        if (spinner) loading = true
        error = null
        try { dues = ApiClient.myDues(garden.id) } catch (e: Exception) { error = e.userMessage } finally { loading = false }
    }
    LaunchedEffect(garden.id) { load() }

    suspend fun confirm(record: DuesRecord, intent: DuesPaymentIntent) {
        val pid = intent.paymentIntentId ?: return
        try {
            info = ApiClient.confirmDuesPayment(garden.id, record.id, pid)
            Haptics.success()
            load(false)
        } catch (_: Exception) {
            // Stripe took the payment but the confirm call failed. The webhook
            // reconciles it; say so rather than alarming anyone.
            info = "Payment received — your record will update in a moment."
            Haptics.success()
        }
        target = null
        pendingIntent = null
    }

    val paymentSheet = remember { PaymentSheet.Builder { result ->
        val record = target
        val intent = pendingIntent
        when (result) {
            is PaymentSheetResult.Completed -> if (record != null && intent != null) scope.launch { confirm(record, intent) }
            is PaymentSheetResult.Canceled -> { target = null; pendingIntent = null }
            is PaymentSheetResult.Failed -> {
                error = "Payment didn't go through — ${result.error.localizedMessage ?: "please try again."}"
                target = null
                pendingIntent = null
                Haptics.error()
            }
        }
    } }.build()

    fun beginPayment(record: DuesRecord) {
        scope.launch {
            target = record
            creatingIntent = true
            try {
                val intent = ApiClient.payDues(garden.id, record.id)
                val secret = intent.clientSecret
                if (intent.isDevMode || secret == null) {
                    error = "Payments aren't fully configured for this garden yet — try again once the organizer finishes payout onboarding."
                    Haptics.warning()
                    return@launch
                }
                // The backend issues the publishable key, so live vs test mode
                // is decided server-side without a new build.
                intent.publishableKey?.let { PaymentConfiguration.init(context, it) }
                pendingIntent = intent
                paymentSheet.presentWithPaymentIntent(secret, sheetConfig(garden.name))
            } catch (e: Exception) {
                error = e.userMessage
                Haptics.error()
            } finally {
                creatingIntent = false
            }
        }
    }

    YHScreen("My Dues") {
        YHLoadable(loading, dues.isEmpty(), error, { scope.launch { load() } }, skeletonCards = 2, skeletonRows = 3,
            empty = { YHEmpty(Icons.Rounded.AttachMoney, "No dues yet", "The garden organizer hasn't generated dues for you yet.") }) {
            YHRefreshable({ load(false) }) {
                Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(YH.Space.md), verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
                    info?.let {
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(YH.Radius.md)).background(YH.lime).padding(YH.Space.md),
                            verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp),
                        ) {
                            Icon(Icons.Rounded.CheckCircle, null, tint = YH.ink)
                            Text(it, style = YHType.subheadline, color = YH.ink)
                        }
                    }
                    if (error != null && dues.isNotEmpty()) YHInlineError(error!!)
                    dues.forEach { record ->
                        DuesCard(record, isWorking = target?.id == record.id && creatingIntent) { beginPayment(record) }
                    }
                }
            }
        }
    }
}

/** Brand the Stripe-rendered sheet to match the app. */
private fun sheetConfig(payeeName: String): PaymentSheet.Configuration =
    PaymentSheet.Configuration.Builder("YardHarvest · $payeeName")
        .allowsDelayedPaymentMethods(true)
        .appearance(
            PaymentSheet.Appearance(
                colorsLight = PaymentSheet.Colors(
                    primary = YH.ink.toArgb(),
                    surface = YH.canvas.toArgb(),
                    component = YH.surface.toArgb(),
                    componentBorder = YH.border.toArgb(),
                    componentDivider = YH.border.toArgb(),
                    onComponent = YH.ink.toArgb(),
                    onSurface = YH.ink.toArgb(),
                    subtitle = YH.muted.toArgb(),
                    placeholderText = YH.muted.toArgb(),
                    appBarIcon = YH.ink.toArgb(),
                    error = YH.danger.toArgb(),
                ),
                colorsDark = PaymentSheet.Colors.defaultDark,
                shapes = PaymentSheet.Shapes(cornerRadiusDp = 14f, borderStrokeWidthDp = 1f),
                typography = PaymentSheet.Typography.default,
                primaryButton = PaymentSheet.PrimaryButton(),
            ),
        )
        .build()

@Composable
private fun DuesCard(record: DuesRecord, isWorking: Boolean, onPay: () -> Unit) {
    YHCard {
        Column(verticalArrangement = Arrangement.spacedBy(YH.Space.sm)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text("${record.seasonYear}", style = YHType.title2, color = YH.ink, modifier = Modifier.weight(1f))
                DuesStatusPill(record.status)
            }
            Row(verticalAlignment = Alignment.Bottom) {
                Column(Modifier.weight(1f)) {
                    Text("BALANCE", style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.muted)
                    Text(if (record.balance > 0) Fmt.money(record.balance) else "Paid in full",
                        fontSize = 26.sp, fontWeight = FontWeight.Bold, letterSpacing = (-0.4).sp, color = YH.ink)
                }
                if (record.amountPaid > 0) {
                    Column(horizontalAlignment = Alignment.End) {
                        Text("PAID", style = YHType.captionMed, letterSpacing = 0.6.sp, color = YH.muted)
                        Text(Fmt.money(record.amountPaid), style = YHType.bodyMedium, color = YH.muted)
                    }
                }
            }
            if (record.balance > 0) {
                YHButton("Pay ${Fmt.money(record.balance)}", icon = Icons.Rounded.CreditCard, style = YHButtonStyle.Lime, isLoading = isWorking, onClick = onPay)
            }
            record.paymentDate?.let { Text("Paid ${Fmt.date(it)}", style = YHType.caption, color = YH.muted) }
        }
    }
}

@Composable
fun DuesStatusPill(status: String) {
    when (status) {
        "paid" -> YHPill("Paid", tint = YH.ink, background = YH.lime)
        "partial" -> YHPill("Partial", tint = YH.ink, background = YH.surface)
        "waived" -> YHPill("Waived", tint = YH.muted, background = YH.surface)
        "comp" -> YHPill("Comp", tint = YH.muted, background = YH.surface)
        else -> YHPill("Unpaid", tint = Color.White, background = YH.danger)
    }
}
