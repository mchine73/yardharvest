package app.yardharvest.manager.ui.nav

import androidx.activity.compose.BackHandler
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.core.tween
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.animation.togetherWith
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.saveable.rememberSaveableStateHolder
import androidx.compose.runtime.staticCompositionLocalOf

/** A destination. Screens are plain data, so a route can carry the garden it's about. */
interface Route

/**
 * One NavigationStack's worth of history — the counterpart of SwiftUI's
 * `NavigationStack` + `navigationDestination`. Routes hold live objects (a
 * Garden, a Plot) rather than ids, exactly as the iOS screens take them.
 */
class NavStack(root: Route) {
    private var seq = 0
    private val entries = mutableStateListOf(Entry(root, seq++))

    data class Entry(val route: Route, val key: Int)

    val top: Entry get() = entries.last()
    val depth: Int get() = entries.size
    val canPop: Boolean get() = entries.size > 1

    fun push(route: Route) { entries.add(Entry(route, seq++)) }

    fun pop(): Boolean {
        if (entries.size <= 1) return false
        entries.removeAt(entries.lastIndex)
        return true
    }

    fun popToRoot() { while (entries.size > 1) entries.removeAt(entries.lastIndex) }

    /** Replace the root, e.g. when the selected garden changes underneath. */
    fun reset(root: Route) {
        entries.clear()
        entries.add(Entry(root, seq++))
    }
}

val LocalNav = staticCompositionLocalOf<NavStack> { error("No NavStack provided") }

/**
 * Renders the top of [stack] with a push/pop slide, keeps each entry's
 * remembered state while it's covered, and routes system back to [NavStack.pop].
 */
@Composable
fun NavHost(stack: NavStack, enableBack: Boolean = true, content: @Composable (Route) -> Unit) {
    val holder = rememberSaveableStateHolder()
    BackHandler(enabled = enableBack && stack.canPop) { stack.pop() }
    CompositionLocalProvider(LocalNav provides stack) {
        AnimatedContent(
            targetState = stack.top,
            transitionSpec = {
                // Keys only grow, so a newer top means a push.
                if (targetState.key > initialState.key) {
                    (slideInHorizontally(tween(260)) { it } + fadeIn(tween(200))) togetherWith
                        (slideOutHorizontally(tween(260)) { -it / 4 } + fadeOut(tween(200)))
                } else {
                    (slideInHorizontally(tween(260)) { -it / 4 } + fadeIn(tween(200))) togetherWith
                        (slideOutHorizontally(tween(260)) { it } + fadeOut(tween(200)))
                }
            },
            contentKey = { it.key },
            label = "nav",
        ) { entry ->
            holder.SaveableStateProvider(entry.key) { content(entry.route) }
        }
    }
}
