package app.yardharvest.manager.ui.brand

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.rounded.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import app.yardharvest.manager.core.Haptics
import app.yardharvest.manager.ui.nav.LocalNav
import kotlinx.coroutines.launch

/**
 * The inline navigation bar every pushed screen wears: back on the left,
 * centered title, actions on the right. Mirrors `.navigationBarTitleDisplayMode(.inline)`.
 */
@Composable
fun YHTopBar(
    title: String,
    onBack: (() -> Unit)? = null,
    leading: (@Composable RowScope.() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
) {
    Box(
        Modifier
            .fillMaxWidth()
            .background(YH.canvas)
            .windowInsetsPadding(WindowInsets.statusBars)
            .height(52.dp)
            .padding(horizontal = 4.dp),
    ) {
        Row(Modifier.align(Alignment.CenterStart), verticalAlignment = Alignment.CenterVertically) {
            if (onBack != null) {
                Box(
                    Modifier.size(44.dp).clip(RoundedCornerShape(50)).clickable { Haptics.tap(); onBack() },
                    contentAlignment = Alignment.Center,
                ) { Icon(Icons.AutoMirrored.Rounded.ArrowBack, "Back", tint = YH.ink) }
            }
            leading?.invoke(this)
        }
        Text(
            title, style = YHType.headline, color = YH.ink, maxLines = 1, overflow = TextOverflow.Ellipsis,
            textAlign = TextAlign.Center,
            modifier = Modifier.align(Alignment.Center).padding(horizontal = 96.dp),
        )
        Row(Modifier.align(Alignment.CenterEnd), verticalAlignment = Alignment.CenterVertically, content = actions)
    }
}

/** A pushed screen: top bar plus content on the canvas. Back pops the enclosing stack. */
@Composable
fun YHScreen(
    title: String,
    showBack: Boolean = true,
    leading: (@Composable RowScope.() -> Unit)? = null,
    actions: @Composable RowScope.() -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    val nav = LocalNav.current
    Column(Modifier.fillMaxSize().background(YH.canvas)) {
        YHTopBar(title, onBack = if (showBack && nav.canPop) ({ nav.pop() }) else null, leading = leading, actions = actions)
        Column(Modifier.fillMaxSize(), content = content)
    }
}

/** Text action for a top bar ("Done", "Save", "Mark all read"). */
@Composable
fun YHBarButton(text: String, enabled: Boolean = true, bold: Boolean = true, color: Color = YH.ink, onClick: () -> Unit) {
    Text(
        text,
        color = if (enabled) color else YH.muted.copy(alpha = 0.5f),
        fontSize = 15.sp,
        fontWeight = if (bold) FontWeight.SemiBold else FontWeight.Normal,
        modifier = Modifier
            .clip(RoundedCornerShape(8.dp))
            .clickable(enabled = enabled) { Haptics.tap(); onClick() }
            .padding(horizontal = 12.dp, vertical = 10.dp),
    )
}

/** Icon action for a top bar. */
@Composable
fun YHBarIcon(icon: androidx.compose.ui.graphics.vector.ImageVector, description: String, tint: Color = YH.muted, onClick: () -> Unit) {
    Box(
        Modifier.size(44.dp).clip(RoundedCornerShape(50)).clickable { Haptics.tap(); onClick() },
        contentAlignment = Alignment.Center,
    ) { Icon(icon, description, tint = tint, modifier = Modifier.size(22.dp)) }
}

/**
 * A full-height modal sheet with its own inline bar — the `.sheet { NavigationStack {…} }`
 * pattern. [leading] and [trailing] are usually Cancel and Save/Done.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YHSheet(
    onDismiss: () -> Unit,
    title: String? = null,
    leading: (@Composable RowScope.() -> Unit)? = null,
    trailing: @Composable RowScope.() -> Unit = {},
    content: @Composable ColumnScope.() -> Unit,
) {
    val state = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = state,
        containerColor = YH.canvas,
        dragHandle = null,
        shape = RoundedCornerShape(topStart = 20.dp, topEnd = 20.dp),
        contentWindowInsets = { WindowInsets(0) },
    ) {
        Column(Modifier.fillMaxWidth().fillMaxSize(0.94f).imePadding().navigationBarsPadding()) {
            Box(Modifier.fillMaxWidth().height(52.dp).padding(horizontal = 4.dp)) {
                Row(Modifier.align(Alignment.CenterStart), verticalAlignment = Alignment.CenterVertically) { leading?.invoke(this) }
                if (title != null) {
                    Text(title, style = YHType.headline, color = YH.ink, maxLines = 1, overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.align(Alignment.Center).padding(horizontal = 96.dp))
                }
                Row(Modifier.align(Alignment.CenterEnd), verticalAlignment = Alignment.CenterVertically, content = trailing)
            }
            Column(Modifier.fillMaxSize(), content = content)
        }
    }
}

/** Pull-to-refresh around scrollable content, the `.refreshable` modifier. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YHRefreshable(onRefresh: suspend () -> Unit, modifier: Modifier = Modifier, content: @Composable () -> Unit) {
    var refreshing by remember { mutableStateOf(false) }
    val scope = rememberCoroutineScope()
    PullToRefreshBox(
        isRefreshing = refreshing,
        onRefresh = {
            scope.launch {
                refreshing = true
                try { onRefresh() } finally { refreshing = false }
            }
        },
        modifier = modifier.fillMaxSize(),
    ) { content() }
}

/** The bordered surface field used on every form in the app. */
@Composable
fun YHTextField(
    value: String,
    onValueChange: (String) -> Unit,
    modifier: Modifier = Modifier,
    label: String? = null,
    placeholder: String = "",
    keyboardType: KeyboardType = KeyboardType.Text,
    capitalization: KeyboardCapitalization = KeyboardCapitalization.None,
    autoCorrect: Boolean = false,
    isPassword: Boolean = false,
    singleLine: Boolean = true,
    minLines: Int = 1,
    imeAction: ImeAction = ImeAction.Default,
    onImeAction: (() -> Unit)? = null,
    textStyle: TextStyle = TextStyle(fontSize = 17.sp, fontWeight = FontWeight.Medium, color = YH.ink),
    minHeight: Dp = 0.dp,
) {
    Column(modifier, verticalArrangement = Arrangement.spacedBy(6.dp)) {
        if (label != null) Text(label, style = YHType.captionMed, color = YH.muted)
        val shape = RoundedCornerShape(YH.Radius.md)
        BasicTextField(
            value = value,
            onValueChange = onValueChange,
            singleLine = singleLine,
            minLines = minLines,
            textStyle = textStyle,
            cursorBrush = SolidColor(YH.ink),
            visualTransformation = if (isPassword) PasswordVisualTransformation() else VisualTransformation.None,
            keyboardOptions = KeyboardOptions(
                capitalization = capitalization,
                autoCorrectEnabled = autoCorrect,
                keyboardType = if (isPassword) KeyboardType.Password else keyboardType,
                imeAction = imeAction,
            ),
            keyboardActions = KeyboardActions(onAny = { onImeAction?.invoke() }),
            modifier = Modifier.fillMaxWidth(),
            decorationBox = { inner ->
                Box(
                    Modifier
                        .fillMaxWidth()
                        .heightIn(min = minHeight)
                        .clip(shape)
                        .background(YH.surface)
                        .border(1.dp, YH.border, shape)
                        .padding(14.dp),
                ) {
                    if (value.isEmpty() && placeholder.isNotEmpty()) {
                        Text(placeholder, style = textStyle.copy(color = YH.muted.copy(alpha = 0.6f), fontWeight = FontWeight.Normal))
                    }
                    inner()
                }
            },
        )
    }
}

/** Brand-colored switch. */
@Composable
fun YHSwitch(checked: Boolean, onCheckedChange: (Boolean) -> Unit, enabled: Boolean = true) {
    Switch(
        checked = checked, onCheckedChange = onCheckedChange, enabled = enabled,
        colors = SwitchDefaults.colors(
            checkedThumbColor = YH.ink, checkedTrackColor = YH.lime, checkedBorderColor = YH.lime,
            uncheckedThumbColor = Color.White, uncheckedTrackColor = YH.border, uncheckedBorderColor = YH.border,
        ),
    )
}

/** A two-button confirmation, the `.alert` / `.confirmationDialog` with one action. */
@Composable
fun YHConfirmDialog(
    title: String,
    message: String? = null,
    confirmText: String,
    destructive: Boolean = false,
    cancelText: String = "Cancel",
    onConfirm: () -> Unit,
    onDismiss: () -> Unit,
) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = YH.canvas,
        title = { Text(title, style = YHType.headline, color = YH.ink) },
        text = message?.let { { Text(it, style = YHType.subheadline, color = YH.muted) } },
        confirmButton = {
            TextButton(onClick = { onDismiss(); onConfirm() }) {
                Text(confirmText, color = if (destructive) YH.danger else YH.ink, fontWeight = FontWeight.SemiBold)
            }
        },
        dismissButton = { TextButton(onClick = onDismiss) { Text(cancelText, color = YH.muted) } },
    )
}

/** A one-button notice, the plain `.alert`. */
@Composable
fun YHNoticeDialog(title: String, message: String?, onDismiss: () -> Unit) {
    AlertDialog(
        onDismissRequest = onDismiss,
        containerColor = YH.canvas,
        title = { Text(title, style = YHType.headline, color = YH.ink) },
        text = message?.let { { Text(it, style = YHType.subheadline, color = YH.muted) } },
        confirmButton = { TextButton(onClick = onDismiss) { Text("OK", color = YH.ink, fontWeight = FontWeight.SemiBold) } },
    )
}

data class SheetAction(val label: String, val destructive: Boolean = false, val onClick: () -> Unit)

/** A list of actions from the bottom — `.confirmationDialog` with several buttons. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun YHActionSheet(title: String?, message: String? = null, actions: List<SheetAction>, onDismiss: () -> Unit) {
    ModalBottomSheet(onDismissRequest = onDismiss, containerColor = YH.canvas) {
        Column(Modifier.fillMaxWidth().navigationBarsPadding().padding(bottom = 12.dp)) {
            if (title != null) {
                Text(title, style = YHType.headline, color = YH.ink, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp))
            }
            if (message != null) {
                Text(message, style = YHType.caption, color = YH.muted, textAlign = TextAlign.Center,
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp, vertical = 8.dp))
            }
            actions.forEach { a ->
                Text(
                    a.label,
                    color = if (a.destructive) YH.danger else YH.ink,
                    fontSize = 17.sp,
                    textAlign = TextAlign.Center,
                    modifier = Modifier
                        .fillMaxWidth()
                        .clickable { Haptics.tap(); onDismiss(); a.onClick() }
                        .padding(vertical = 16.dp),
                )
            }
            Text(
                "Cancel", color = YH.muted, fontSize = 17.sp, fontWeight = FontWeight.SemiBold, textAlign = TextAlign.Center,
                modifier = Modifier.fillMaxWidth().clickable { onDismiss() }.padding(vertical = 16.dp),
            )
        }
    }
}
