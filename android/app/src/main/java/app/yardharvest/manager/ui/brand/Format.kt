package app.yardharvest.manager.ui.brand

import android.text.format.DateUtils
import java.text.NumberFormat
import java.time.Instant
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.time.format.FormatStyle
import java.util.Locale

/** Date and number formatting matching the iOS `.formatted(...)` call sites. */
object Fmt {
    private val zone: ZoneId get() = ZoneId.systemDefault()

    /** "Nov 2, 2026" — iOS `date: .abbreviated, time: .omitted`. */
    fun date(i: Instant): String = DateTimeFormatter.ofLocalizedDate(FormatStyle.MEDIUM).format(i.atZone(zone))

    /** "9:30 AM" — iOS `date: .omitted, time: .shortened`. */
    fun time(i: Instant): String = DateTimeFormatter.ofLocalizedTime(FormatStyle.SHORT).format(i.atZone(zone))

    /** "Nov 2, 2026, 9:30 AM" — iOS `date: .abbreviated, time: .shortened`. */
    fun dateTime(i: Instant): String = "${date(i)}, ${time(i)}"

    /** "Sat, Nov 2" */
    fun weekdayDate(i: Instant): String = DateTimeFormatter.ofPattern("EEE, MMM d").format(i.atZone(zone))

    /** "Saturday, November 2" */
    fun longWeekdayDate(i: Instant): String = DateTimeFormatter.ofPattern("EEEE, MMMM d").format(i.atZone(zone))

    fun monthAbbrev(i: Instant): String = DateTimeFormatter.ofPattern("MMM").format(i.atZone(zone)).uppercase()
    fun day(i: Instant): String = i.atZone(zone).dayOfMonth.toString()

    /** "2 hours ago", "Yesterday" — iOS `.relative(presentation: .named)`. */
    fun relative(i: Instant): String =
        DateUtils.getRelativeTimeSpanString(
            i.toEpochMilli(), System.currentTimeMillis(), DateUtils.MINUTE_IN_MILLIS,
            DateUtils.FORMAT_ABBREV_RELATIVE,
        ).toString()

    private val currency: NumberFormat get() = NumberFormat.getCurrencyInstance(Locale.US)

    /** "$35.00" */
    fun money(dollars: Double): String = currency.format(dollars)

    /** For the finance figures the API sends as integer cents. */
    fun moneyCents(cents: Int): String = currency.format(cents / 100.0)

    /** "$35.00" with an explicit sign when negative ("−$5.00"). */
    fun signedMoney(dollars: Double, outgoing: Boolean): String =
        if (outgoing) "−${money(kotlin.math.abs(dollars))}" else money(dollars)

    /** Pounds: one decimal under 10, none above — the iOS harvest formatter. */
    fun pounds(v: Double): String {
        val f = NumberFormat.getNumberInstance()
        f.maximumFractionDigits = if (v < 10) 1 else 0
        return f.format(v)
    }
}
