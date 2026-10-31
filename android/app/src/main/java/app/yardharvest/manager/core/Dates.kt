package app.yardharvest.manager.core

import kotlinx.serialization.ExperimentalSerializationApi
import kotlinx.serialization.KSerializer
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import java.time.Instant
import java.time.LocalDate
import java.time.LocalDateTime
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter
import java.time.format.DateTimeParseException

/**
 * The date shapes Flask emits: ISO 8601 with an offset (with or without
 * fractional seconds), a naive datetime, or a bare date.
 *
 * A naive datetime is ambiguous on this backend. Timestamps (`created_at`,
 * `paid_at`…) are stored as UTC without an offset, while scheduled times
 * (`event_date`) are the garden's wall-clock time. The two serializers below
 * differ only in how they read that case. A bare date is always the local
 * calendar day, so a shift on the 2nd never shows up on the 1st west of UTC.
 */
object Dates {
    fun parse(s: String, naiveZone: ZoneId): Instant? {
        val str = s.trim()
        if (str.isEmpty()) return null
        try { return OffsetDateTime.parse(str).toInstant() } catch (_: DateTimeParseException) {}
        try { return Instant.parse(str) } catch (_: DateTimeParseException) {}
        try { return LocalDateTime.parse(str).atZone(naiveZone).toInstant() } catch (_: DateTimeParseException) {}
        // "2026-05-01 09:30:00" — a space instead of the T.
        try {
            return LocalDateTime.parse(str.replace(' ', 'T')).atZone(naiveZone).toInstant()
        } catch (_: DateTimeParseException) {}
        try { return LocalDate.parse(str).atStartOfDay(ZoneId.systemDefault()).toInstant() } catch (_: DateTimeParseException) {}
        return null
    }

    /** UTC for naive timestamps — matches the iOS client. */
    fun parseTimestamp(s: String): Instant? = parse(s, ZoneOffset.UTC)

    /** Device-local for naive scheduled times. */
    fun parseWallClock(s: String): Instant? = parse(s, ZoneId.systemDefault())

    private val isoDate: DateTimeFormatter = DateTimeFormatter.ISO_LOCAL_DATE

    /** `yyyy-MM-dd` in the device's zone — the shape date-only request fields take. */
    fun ymd(instant: Instant): String = isoDate.format(instant.atZone(ZoneId.systemDefault()))
    fun ymd(date: LocalDate): String = isoDate.format(date)
}

@OptIn(ExperimentalSerializationApi::class) // decodeNotNullMark: a nullable primitive serializer
abstract class FlexibleInstantSerializer(private val parser: (String) -> Instant?) : KSerializer<Instant?> {
    override val descriptor: SerialDescriptor = PrimitiveSerialDescriptor(javaClass.name, PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): Instant? {
        if (!decoder.decodeNotNullMark()) return decoder.decodeNull()
        return parser(decoder.decodeString())
    }

    override fun serialize(encoder: Encoder, value: Instant?) {
        if (value == null) encoder.encodeNull() else encoder.encodeString(value.toString())
    }
}

/** Server timestamps: naive means UTC. */
object TimestampSerializer : FlexibleInstantSerializer(Dates::parseTimestamp)

/** Scheduled wall-clock times and bare dates: naive means local. */
object WallClockSerializer : FlexibleInstantSerializer(Dates::parseWallClock)
