package app.yardharvest.manager.ui.nav

import androidx.compose.runtime.Composable
import app.yardharvest.manager.model.AdminDuesRecord
import app.yardharvest.manager.model.Garden
import app.yardharvest.manager.model.InboxThread
import app.yardharvest.manager.model.Plot
import app.yardharvest.manager.ui.admin.AdminReviewsScreen
import app.yardharvest.manager.ui.admin.AdminWaitlistScreen
import app.yardharvest.manager.ui.admintools.AdminToolsScreen
import app.yardharvest.manager.ui.announcements.AnnouncementsScreen
import app.yardharvest.manager.ui.announcements.AnnouncementsTab
import app.yardharvest.manager.ui.community.CommunityScreen
import app.yardharvest.manager.ui.community.ModerationScreen
import app.yardharvest.manager.ui.dashboard.DashboardTab
import app.yardharvest.manager.ui.discover.BrowseGardensScreen
import app.yardharvest.manager.ui.discover.GardenDetailScreen
import app.yardharvest.manager.ui.dues.MyDuesScreen
import app.yardharvest.manager.ui.events.EventsScreen
import app.yardharvest.manager.ui.harvest.HarvestLogScreen
import app.yardharvest.manager.ui.inbox.InboxScreen
import app.yardharvest.manager.ui.inbox.ThreadScreen
import app.yardharvest.manager.ui.more.BlockedMembersScreen
import app.yardharvest.manager.ui.more.MoreTab
import app.yardharvest.manager.ui.more.RolesScreen
import app.yardharvest.manager.ui.notifications.NotificationsScreen
import app.yardharvest.manager.ui.payments.AdHocChargeScreen
import app.yardharvest.manager.ui.payments.AdminCollectDuesScreen
import app.yardharvest.manager.ui.payments.AdminDuesListScreen
import app.yardharvest.manager.ui.payments.MoneyScreen
import app.yardharvest.manager.ui.payments.PaymentHubScreen
import app.yardharvest.manager.ui.plots.PlotDetailScreen
import app.yardharvest.manager.ui.plots.PlotsScreen
import app.yardharvest.manager.ui.shifts.ShiftsScreen
import app.yardharvest.manager.ui.tools.ToolsTab

/**
 * Every pushable screen. Routes carry live objects (a Garden, a Plot) the way
 * the iOS views take them, plus change callbacks where a screen reports back.
 */
sealed interface Dest : Route {
    // Tab roots
    data object GardenTab : Dest
    data object ToolsTab : Dest
    data object AnnouncementsTab : Dest
    data object MoreTab : Dest

    data class Events(val garden: Garden) : Dest
    data class Announcements(val garden: Garden) : Dest
    data class Waitlist(val garden: Garden) : Dest
    data class Harvest(val garden: Garden, val autoCompose: Boolean = false) : Dest
    data class Plots(val garden: Garden) : Dest
    data class PlotDetail(val garden: Garden, val plot: Plot, val onChange: () -> Unit) : Dest
    data class Shifts(val garden: Garden) : Dest
    data class Payments(val garden: Garden) : Dest
    data class AdminDuesList(val garden: Garden) : Dest
    data class CollectDues(val garden: Garden, val record: AdminDuesRecord, val onChange: () -> Unit) : Dest
    data class AdHocCharge(val garden: Garden) : Dest
    data class Money(val garden: Garden) : Dest
    data class Community(val garden: Garden) : Dest
    data class Moderation(val garden: Garden) : Dest
    data class Reviews(val garden: Garden) : Dest
    data class MyDues(val garden: Garden) : Dest
    data class AdminTools(val garden: Garden) : Dest
    data class Roles(val garden: Garden) : Dest
    data object BrowseGardens : Dest
    data class GardenDetail(val gardenId: Int) : Dest
    data object Inbox : Dest
    data class Thread(
        val recipientId: Int,
        val recipientName: String,
        val thread: InboxThread?,
        val onChange: () -> Unit,
    ) : Dest
    data object Notifications : Dest
    data object BlockedMembers : Dest
}

/** The `navigationDestination` table: one screen per route. */
@Composable
fun RouteContent(route: Route) {
    when (route) {
        Dest.GardenTab -> DashboardTab()
        Dest.ToolsTab -> ToolsTab()
        Dest.AnnouncementsTab -> AnnouncementsTab()
        Dest.MoreTab -> MoreTab()
        is Dest.Events -> EventsScreen(route.garden)
        is Dest.Announcements -> AnnouncementsScreen(route.garden)
        is Dest.Waitlist -> AdminWaitlistScreen(route.garden)
        is Dest.Harvest -> HarvestLogScreen(route.garden, route.autoCompose)
        is Dest.Plots -> PlotsScreen(route.garden)
        is Dest.PlotDetail -> PlotDetailScreen(route.garden, route.plot, route.onChange)
        is Dest.Shifts -> ShiftsScreen(route.garden)
        is Dest.Payments -> PaymentHubScreen(route.garden)
        is Dest.AdminDuesList -> AdminDuesListScreen(route.garden)
        is Dest.CollectDues -> AdminCollectDuesScreen(route.garden, route.record, route.onChange)
        is Dest.AdHocCharge -> AdHocChargeScreen(route.garden)
        is Dest.Money -> MoneyScreen(route.garden)
        is Dest.Community -> CommunityScreen(route.garden)
        is Dest.Moderation -> ModerationScreen(route.garden)
        is Dest.Reviews -> AdminReviewsScreen(route.garden)
        is Dest.MyDues -> MyDuesScreen(route.garden)
        is Dest.AdminTools -> AdminToolsScreen(route.garden)
        is Dest.Roles -> RolesScreen(route.garden)
        Dest.BrowseGardens -> BrowseGardensScreen()
        is Dest.GardenDetail -> GardenDetailScreen(route.gardenId)
        Dest.Inbox -> InboxScreen()
        is Dest.Thread -> ThreadScreen(route.recipientId, route.recipientName, route.thread, route.onChange)
        Dest.Notifications -> NotificationsScreen()
        Dest.BlockedMembers -> BlockedMembersScreen()
    }
}
