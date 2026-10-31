package app.yardharvest.manager

import app.yardharvest.manager.core.Dates
import app.yardharvest.manager.model.GardenEvent
import app.yardharvest.manager.model.VolunteerShift
import app.yardharvest.manager.model.YHMessage
import app.yardharvest.manager.core.ApiClient
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.util.TimeZone
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Before
import org.junit.Test

/** The date shapes Flask emits, and which ones mean wall-clock vs UTC. */
class DatesTest {
    private val original = TimeZone.getDefault()

    @Before fun pinZone() = TimeZone.setDefault(TimeZone.getTimeZone("America/Chicago"))
    @After fun restoreZone() = TimeZone.setDefault(original)

    @Test fun `offset datetimes parse exactly, with or without fractions`() {
        assertEquals(Instant.parse("2026-05-01T14:30:00Z"), Dates.parseTimestamp("2026-05-01T09:30:00-05:00"))
        assertEquals(Instant.parse("2026-05-01T14:30:00.123456Z"), Dates.parseTimestamp("2026-05-01T14:30:00.123456+00:00"))
        assertEquals(Instant.parse("2026-05-01T14:30:00Z"), Dates.parseTimestamp("2026-05-01T14:30:00Z"))
    }

    @Test fun `a naive timestamp is UTC, like the iOS client`() {
        assertEquals(Instant.parse("2026-05-01T14:30:00Z"), Dates.parseTimestamp("2026-05-01T14:30:00"))
        assertEquals(Instant.parse("2026-05-01T14:30:00.500Z"), Dates.parseTimestamp("2026-05-01T14:30:00.500000"))
    }

    @Test fun `a naive scheduled time is the local wall clock`() {
        val parsed = Dates.parseWallClock("2026-05-01T09:00:00")!!
        assertEquals(LocalDateTime.of(2026, 5, 1, 9, 0), LocalDateTime.ofInstant(parsed, ZoneId.systemDefault()))
    }

    @Test fun `a bare date is the local calendar day in both readings`() {
        // West of UTC, a UTC-midnight reading would show the day before.
        for (parse in listOf(Dates::parseTimestamp, Dates::parseWallClock)) {
            val parsed = parse("2026-06-02")!!
            assertEquals(LocalDate.of(2026, 6, 2), parsed.atZone(ZoneId.systemDefault()).toLocalDate())
        }
    }

    @Test fun `garbage and blanks read as null rather than failing the payload`() {
        assertNull(Dates.parseTimestamp(""))
        assertNull(Dates.parseTimestamp("not a date"))
        val msg = ApiClient.json.decodeFromString(YHMessage.serializer(),
            """{"id":1,"thread_id":"t","sender_id":1,"recipient_id":2,"body":"hi","created_at":"soon"}""")
        assertNull(msg.createdAt)
    }

    @Test fun `models pick the right reading per field`() {
        val event = ApiClient.json.decodeFromString(GardenEvent.serializer(),
            """{"id":1,"garden_id":2,"title":"Workday","event_date":"2026-05-02T09:00:00","created_at":"2026-04-01T12:00:00"}""")
        assertEquals(LocalDateTime.of(2026, 5, 2, 9, 0), LocalDateTime.ofInstant(event.eventDate, ZoneId.systemDefault()))
        assertEquals(Instant.parse("2026-04-01T12:00:00Z"), event.createdAt)

        val shift = ApiClient.json.decodeFromString(VolunteerShift.serializer(),
            """{"id":1,"garden_id":2,"title":"Water","shift_date":"2026-05-03","start_time":"09:00","end_time":"11:00"}""")
        assertEquals(LocalDate.of(2026, 5, 3), shift.shiftDate!!.atZone(ZoneId.systemDefault()).toLocalDate())
        assertEquals("09:00–11:00", shift.timeRange)
    }

    @Test fun `ymd formats in the device zone`() {
        val lateEvening = LocalDateTime.of(2026, 7, 4, 23, 30).atZone(ZoneId.systemDefault()).toInstant()
        assertEquals("2026-07-04", Dates.ymd(lateEvening))
        assertEquals("2026-07-05", lateEvening.atOffset(ZoneOffset.UTC).toLocalDate().toString())
    }
}
