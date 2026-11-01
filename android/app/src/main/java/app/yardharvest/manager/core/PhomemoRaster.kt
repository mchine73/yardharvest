package app.yardharvest.manager.core

import android.graphics.Bitmap
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import androidx.core.graphics.createBitmap

/**
 * Which printer family we're talking to. The families speak mutually
 * unintelligible protocols: the wrong pick connects fine, accepts every byte,
 * and prints nothing. Mirrors `PhomemoModel` in the iOS driver.
 */
enum class PhomemoModel(val label: String, val detailedLabel: String, val defaultPrintWidth: Int, val defaultLabelHeight: Int) {
    /** Phomemo M02 family — 80 mm receipt (M02, M02S, M02 Pro, T02, PR02). */
    M02("M02", "Phomemo M02 (80 mm receipt)", 384, 384),
    /** Phomemo M110 family — 40 mm label with peeler (M110, M120, M200, M220, D110, D11). */
    M110("M110", "Phomemo M110 (40 mm label)", 320, 240),
    /** Generic ESC/POS 58 mm BLE thermal printers (NETUM, GOOJPRT, Rongta, MTP…). */
    Generic("Generic", "Generic ESC/POS (58 mm receipt)", 384, 384),
    /** JADENS BT-series sticker printers — TSPL2, not ESC/POS. */
    Jadens("JADENS", "JADENS BT-series (40 × 30 mm sticker, TSPL)", 320, 240);

    companion object {
        /**
         * Family detection from the advertised name; null when the name
         * doesn't clearly identify one, in which case the picker choice stands.
         */
        fun detect(name: String): PhomemoModel? {
            val u = name.uppercase()
            if (listOf("JADENS", "BT203", "BT201", "BT420", "BT460", "JD-").any { u.contains(it) }) return Jadens
            if (listOf("M110", "M120", "M200", "M220", "D110", "D11 ", "D30", "D35").any { u.contains(it) }) return M110
            if (listOf("M02", "M03", "T02", "PR02").any { u.contains(it) }) return M02
            return null
        }
    }
}

/**
 * The printers' wire formats — byte-for-byte the same streams the iOS
 * `PhomemoRaster` emits, so a label that prints from one phone prints from
 * the other. Pure functions, unit-tested in PhomemoRasterTest.
 */
object PhomemoRaster {
    /** 1-bit packed raster, MSB-first, row-major; 1 = black. */
    class Raster(val width: Int, val height: Int, val data: ByteArray)

    /** Pack 8-bit grey pixels (0 = black … 255 = white) into a 1-bit raster. */
    fun pack(grey: IntArray, widthPixels: Int, height: Int): Raster {
        val widthBytes = (widthPixels + 7) / 8
        val packed = ByteArray(widthBytes * height)
        for (y in 0 until height) {
            for (xByte in 0 until widthBytes) {
                var byte = 0
                for (bit in 0 until 8) {
                    val x = xByte * 8 + bit
                    if (x < widthPixels && grey[y * widthPixels + x] < 128) byte = byte or (0x80 ushr bit)
                }
                packed[y * widthBytes + xByte] = byte.toByte()
            }
        }
        return Raster(widthBytes * 8, height, packed)
    }

    /** Scale [image] to the head width on a white canvas and threshold it to 1-bit. */
    fun encode(image: Bitmap, width: Int): Raster {
        val widthPixels = ((width + 7) / 8) * 8
        val scale = widthPixels.toFloat() / maxOf(image.width, 1)
        val height = maxOf(1, Math.round(image.height * scale))
        val canvasBitmap = createBitmap(widthPixels, height)
        Canvas(canvasBitmap).apply {
            drawColor(Color.WHITE)
            drawBitmap(image, null, Rect(0, 0, widthPixels, height), Paint(Paint.FILTER_BITMAP_FLAG))
        }
        val argb = IntArray(widthPixels * height)
        canvasBitmap.getPixels(argb, 0, widthPixels, 0, 0, widthPixels, height)
        canvasBitmap.recycle()
        val grey = IntArray(argb.size) { i ->
            val c = argb[i]
            ((Color.red(c) * 299 + Color.green(c) * 587 + Color.blue(c) * 114) / 1000)
        }
        return pack(grey, widthPixels, height)
    }

    /** The full byte stream for one job, in the model's dialect. */
    fun commandStream(raster: Raster, widthPixels: Int, model: PhomemoModel): ByteArray = when (model) {
        PhomemoModel.M02 -> m02Stream(raster, widthPixels)
        PhomemoModel.M110 -> m110Stream(raster, widthPixels)
        PhomemoModel.Generic -> genericEscPosStream(raster, widthPixels)
        PhomemoModel.Jadens -> jadensTsplStream(raster, widthPixels)
    }

    private fun ByteArrayBuilder.rasterHeader(widthPixels: Int, height: Int) {
        val widthBytes = widthPixels / 8
        add(0x1D, 0x76, 0x30, 0x00) // GS v 0 0
        add(widthBytes and 0xFF, (widthBytes shr 8) and 0xFF, height and 0xFF, (height shr 8) and 0xFF)
    }

    /**
     * JADENS BT-series speak TSPL2: ASCII setup lines, then BITMAP with the
     * width in BYTES and the raster inverted — TSPL's 0 prints, the inverse of
     * ESC/POS. Without the inversion the solid test band feeds out blank.
     */
    private fun jadensTsplStream(raster: Raster, widthPixels: Int): ByteArray {
        val widthBytes = widthPixels / 8
        val labelWidthMm = maxOf(1, widthPixels / 8)
        val labelHeightMm = maxOf(1, raster.height / 8)
        return ByteArrayBuilder().apply {
            ascii("SIZE $labelWidthMm mm,$labelHeightMm mm\r\n")
            ascii("GAP 2 mm,0 mm\r\n")
            ascii("DENSITY 8\r\n")
            ascii("SPEED 4\r\n")
            ascii("DIRECTION 0\r\n")
            ascii("REFERENCE 0,0\r\n")
            ascii("CLS\r\n")
            ascii("BITMAP 0,0,$widthBytes,${raster.height},0,")
            bytes(ByteArray(raster.data.size) { (raster.data[it].toInt().inv()).toByte() })
            ascii("\r\n")
            ascii("PRINT 1,1\r\n")
        }.toByteArray()
    }

    /** Vanilla ESC/POS for generic 58 mm printers: the M02 stream without the vendor flush. */
    private fun genericEscPosStream(raster: Raster, widthPixels: Int): ByteArray = ByteArrayBuilder().apply {
        add(0x1B, 0x40)       // init
        add(0x1B, 0x61, 0x01) // center
        add(0x1B, 0x33, 0x00) // line spacing 0
        rasterHeader(widthPixels, raster.height)
        bytes(raster.data)
        add(0x0A)             // LF flushes cheap firmwares
        add(0x1B, 0x64, 0x06) // feed 6 lines
    }.toByteArray()

    /** M02 family: ESC/POS raster plus the vendor END-OF-JOB that fires the head. */
    private fun m02Stream(raster: Raster, widthPixels: Int): ByteArray = ByteArrayBuilder().apply {
        add(0x1B, 0x40)
        add(0x1B, 0x61, 0x01)
        add(0x1B, 0x33, 0x00)
        rasterHeader(widthPixels, raster.height)
        bytes(raster.data)
        add(0x1F, 0x11, 0x08)
        add(0x0A)
        add(0x1B, 0x64, 0x06)
    }.toByteArray()

    /**
     * M110 family: init, the 4-byte print-mode command, raster, END-OF-JOB,
     * a 96-dot feed past the peeler, then a form feed. The label gap must be
     * calibrated once on the printer itself before the first print.
     */
    private fun m110Stream(raster: Raster, widthPixels: Int): ByteArray = ByteArrayBuilder().apply {
        add(0x1B, 0x40)
        add(0x1F, 0x11, 0x02, 0x04)
        rasterHeader(widthPixels, raster.height)
        bytes(raster.data)
        add(0x1F, 0x11, 0x08)
        add(0x1B, 0x4A, 0x60)
        add(0x0C)
    }.toByteArray()

    /** A solid band of [rows], used by the test page and the protocol sweep. */
    fun band(rows: Int, width: Int, model: PhomemoModel): ByteArray {
        val widthBytes = width / 8
        val data = ByteArray(widthBytes * rows) { 0xFF.toByte() }
        return commandStream(Raster(width, rows, data), width, model)
    }

    /**
     * A self-contained test print. JADENS gets pure-ASCII TSPL with built-in
     * TEXT, so the test bisects transport from bitmap; everyone else gets a
     * 64-row black band.
     */
    fun testPagePayload(widthPixels: Int, model: PhomemoModel): ByteArray {
        if (model == PhomemoModel.Jadens) {
            return ("SIZE 40 mm,30 mm\r\nGAP 2 mm,0 mm\r\nDENSITY 8\r\nCLS\r\n" +
                "TEXT 24,40,\"3\",0,2,2,\"YARDHARVEST\"\r\nTEXT 24,110,\"2\",0,1,1,\"TSPL test OK\"\r\nPRINT 1,1\r\n")
                .toByteArray(Charsets.US_ASCII)
        }
        return band(64, widthPixels, model)
    }

    private class ByteArrayBuilder {
        private val out = java.io.ByteArrayOutputStream()
        fun add(vararg b: Int) = b.forEach { out.write(it) }
        fun bytes(b: ByteArray) = out.write(b)
        fun ascii(s: String) = out.write(s.toByteArray(Charsets.US_ASCII))
        fun toByteArray(): ByteArray = out.toByteArray()
    }
}
