package app.yardharvest.manager

import app.yardharvest.manager.core.AppEnvironment
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

/** Media paths join against an explicit base, never whatever a hand-test left behind. */
class AppEnvironmentTest {

    @After fun tearDown() {
        AppEnvironment.testBaseUrl = null
    }

    @Test fun relativePathJoinsTheBase() {
        AppEnvironment.testBaseUrl = "https://www.yardharvest.app"
        assertEquals("https://www.yardharvest.app/uploads/a.jpg", AppEnvironment.mediaUrl("/uploads/a.jpg"))
    }

    @Test fun pathMissingItsLeadingSlashGetsOne() {
        AppEnvironment.testBaseUrl = "https://www.yardharvest.app"
        assertEquals("https://www.yardharvest.app/uploads/a.jpg", AppEnvironment.mediaUrl("uploads/a.jpg"))
    }

    @Test fun baseCarryingATrailingSlashDoesNotDoubleIt() {
        AppEnvironment.testBaseUrl = "http://10.0.2.2:5000/"
        assertEquals("http://10.0.2.2:5000/uploads/a.jpg", AppEnvironment.mediaUrl("/uploads/a.jpg"))
    }

    @Test fun absoluteUrlsPassThrough() {
        AppEnvironment.testBaseUrl = "https://www.yardharvest.app"
        assertEquals("https://cdn.example.com/a.jpg", AppEnvironment.mediaUrl("https://cdn.example.com/a.jpg"))
    }

    @Test fun emptyOrMissingIsNull() {
        assertNull(AppEnvironment.mediaUrl(null))
        assertNull(AppEnvironment.mediaUrl(""))
    }
}
