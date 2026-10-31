package app.yardharvest.manager

import app.yardharvest.manager.core.PhomemoModel
import app.yardharvest.manager.core.PhomemoRaster
import org.junit.Assert.assertArrayEquals
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * The printer wire formats, byte for byte. These must match the iOS driver:
 * a label that prints from one phone has to print from the other.
 */
class PhomemoRasterTest {
    private fun bytes(vararg v: Int) = ByteArray(v.size) { v[it].toByte() }
    private fun ByteArray.startsWith(prefix: ByteArray) = size >= prefix.size && copyOfRange(0, prefix.size).contentEquals(prefix)
    private fun ByteArray.endsWith(suffix: ByteArray) = size >= suffix.size && copyOfRange(size - suffix.size, size).contentEquals(suffix)

    @Test fun `pack sets a bit for every dark pixel, MSB first`() {
        // 16 px wide, 1 row: first pixel dark, ninth pixel dark, rest light.
        val grey = IntArray(16) { 255 }.also { it[0] = 0; it[8] = 100 }
        val r = PhomemoRaster.pack(grey, 16, 1)
        assertEquals(16, r.width)
        assertArrayEquals(bytes(0x80, 0x80), r.data)
    }

    @Test fun `pack rounds the width up to whole bytes`() {
        val r = PhomemoRaster.pack(IntArray(10) { 0 }, 10, 1)
        assertEquals(16, r.width)
        assertArrayEquals(bytes(0xFF, 0xC0), r.data)
    }

    private val tiny = PhomemoRaster.Raster(16, 2, bytes(0xF0, 0x0F, 0xAA, 0x55))

    @Test fun `M02 stream is ESC-POS raster plus the vendor end-of-job`() {
        val s = PhomemoRaster.commandStream(tiny, 16, PhomemoModel.M02)
        assertTrue(s.startsWith(bytes(0x1B, 0x40, 0x1B, 0x61, 0x01, 0x1B, 0x33, 0x00, 0x1D, 0x76, 0x30, 0x00, 2, 0, 2, 0, 0xF0, 0x0F, 0xAA, 0x55)))
        assertTrue(s.endsWith(bytes(0x1F, 0x11, 0x08, 0x0A, 0x1B, 0x64, 0x06)))
    }

    @Test fun `M110 stream carries the 4-byte print mode, end-of-job, feed and form feed`() {
        val s = PhomemoRaster.commandStream(tiny, 16, PhomemoModel.M110)
        assertTrue(s.startsWith(bytes(0x1B, 0x40, 0x1F, 0x11, 0x02, 0x04, 0x1D, 0x76, 0x30, 0x00, 2, 0, 2, 0)))
        assertTrue(s.endsWith(bytes(0x1F, 0x11, 0x08, 0x1B, 0x4A, 0x60, 0x0C)))
    }

    @Test fun `generic ESC-POS has no Phomemo flush byte`() {
        val s = PhomemoRaster.commandStream(tiny, 16, PhomemoModel.Generic)
        assertTrue(s.endsWith(bytes(0xAA, 0x55, 0x0A, 0x1B, 0x64, 0x06)))
        assertTrue(s.indices.none { i -> i + 2 < s.size && s[i] == 0x1F.toByte() && s[i + 1] == 0x11.toByte() && s[i + 2] == 0x08.toByte() })
    }

    @Test fun `dimensions are little-endian`() {
        val tall = PhomemoRaster.Raster(384, 300, ByteArray(48 * 300))
        val s = PhomemoRaster.commandStream(tall, 384, PhomemoModel.Generic)
        val header = s.copyOfRange(8, 16)
        assertArrayEquals(bytes(0x1D, 0x76, 0x30, 0x00, 48, 0, 300 and 0xFF, 300 shr 8), header)
    }

    @Test fun `JADENS speaks TSPL with the bitmap inverted`() {
        val s = PhomemoRaster.commandStream(tiny, 16, PhomemoModel.Jadens)
        val text = String(s, Charsets.ISO_8859_1)
        assertTrue(text.startsWith("SIZE 2 mm,1 mm\r\nGAP 2 mm,0 mm\r\nDENSITY 8\r\nSPEED 4\r\nDIRECTION 0\r\nREFERENCE 0,0\r\nCLS\r\n"))
        val marker = "BITMAP 0,0,2,2,0,"
        val at = text.indexOf(marker) + marker.length
        // TSPL prints 0 bits: every byte must be the inverse of the raster.
        assertArrayEquals(bytes(0x0F, 0xF0, 0x55, 0xAA), s.copyOfRange(at, at + 4))
        assertTrue(text.endsWith("\r\nPRINT 1,1\r\n"))
    }

    @Test fun `the JADENS test page is pure ASCII text, everyone else gets a 64-row band`() {
        val tspl = String(PhomemoRaster.testPagePayload(320, PhomemoModel.Jadens), Charsets.US_ASCII)
        assertTrue(tspl.contains("TEXT 24,40,\"3\",0,2,2,\"YARDHARVEST\""))
        assertTrue(tspl.endsWith("PRINT 1,1\r\n"))

        val band = PhomemoRaster.testPagePayload(384, PhomemoModel.M02)
        // 48 bytes per row × 64 rows of solid black, between header and trailer.
        assertEquals(16 + 48 * 64 + 7, band.size)
    }

    @Test fun `model detection follows the advertised name`() {
        assertEquals(PhomemoModel.Jadens, PhomemoModel.detect("JD-2x BLE"))
        assertEquals(PhomemoModel.M110, PhomemoModel.detect("M110-A1B2"))
        assertEquals(PhomemoModel.M02, PhomemoModel.detect("M02 Pro"))
        assertEquals(null, PhomemoModel.detect("Headphones"))
    }
}
