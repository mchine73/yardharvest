package app.yardharvest.manager

import app.yardharvest.manager.api.dashboard
import app.yardharvest.manager.api.login
import app.yardharvest.manager.api.me
import app.yardharvest.manager.core.ApiClient
import app.yardharvest.manager.core.ApiError
import app.yardharvest.manager.core.AppEnvironment
import app.yardharvest.manager.core.TokenStore
import app.yardharvest.manager.model.GardenStripeBalance
import app.yardharvest.manager.model.InPersonPaymentIntent
import kotlinx.coroutines.async
import kotlinx.coroutines.awaitAll
import kotlinx.coroutines.runBlocking
import okhttp3.mockwebserver.Dispatcher
import okhttp3.mockwebserver.MockResponse
import okhttp3.mockwebserver.MockWebServer
import okhttp3.mockwebserver.RecordedRequest
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Assert.fail
import org.junit.Before
import org.junit.Test
import java.util.concurrent.atomic.AtomicInteger

class ApiClientTest {
    private lateinit var server: MockWebServer
    private val refreshes = AtomicInteger()

    private val user = """{"id":7,"username":"sam","email":"sam@example.com","role":"gardener"}"""

    @Before fun setUp() {
        server = MockWebServer()
        server.start()
        AppEnvironment.testBaseUrl = server.url("/").toString()
        TokenStore.backend = TokenStore.InMemory()
        refreshes.set(0)
    }

    @After fun tearDown() {
        server.shutdown()
        AppEnvironment.testBaseUrl = null
    }

    /** /me answers 401 for the stale token and 200 for the refreshed one. */
    private fun refreshingDispatcher(refreshStatus: Int = 200) = object : Dispatcher() {
        override fun dispatch(request: RecordedRequest): MockResponse = when (request.path) {
            "/api/auth/token/refresh" -> {
                refreshes.incrementAndGet()
                Thread.sleep(50) // long enough for concurrent callers to pile up
                if (refreshStatus == 200) MockResponse().setBody("""{"access_token":"fresh","refresh_token":"r2"}""")
                else MockResponse().setResponseCode(refreshStatus)
            }
            "/api/auth/me" ->
                if (request.getHeader("Authorization") == "Bearer fresh") MockResponse().setBody(user)
                else MockResponse().setResponseCode(401)
            else -> MockResponse().setResponseCode(404)
        }
    }

    @Test fun `a 401 refreshes the token and replays the request once`() = runBlocking {
        TokenStore.set("stale", TokenStore.Key.AccessToken)
        TokenStore.set("r1", TokenStore.Key.RefreshToken)
        server.dispatcher = refreshingDispatcher()
        assertEquals(7, ApiClient.me().id)
        assertEquals("fresh", TokenStore.get(TokenStore.Key.AccessToken))
        assertEquals("r2", TokenStore.get(TokenStore.Key.RefreshToken))
        assertEquals(1, refreshes.get())
    }

    @Test fun `concurrent 401s share a single refresh`() = runBlocking {
        TokenStore.set("stale", TokenStore.Key.AccessToken)
        TokenStore.set("r1", TokenStore.Key.RefreshToken)
        server.dispatcher = refreshingDispatcher()
        val users = (1..5).map { async { ApiClient.me() } }.awaitAll()
        assertTrue(users.all { it.id == 7 })
        assertEquals(1, refreshes.get())
    }

    @Test fun `a failed refresh signs the session out`() = runBlocking {
        TokenStore.set("stale", TokenStore.Key.AccessToken)
        TokenStore.set("r1", TokenStore.Key.RefreshToken)
        server.dispatcher = refreshingDispatcher(refreshStatus = 401)
        try {
            ApiClient.me()
            fail("expected Unauthorized")
        } catch (e: ApiError.Unauthorized) {
        }
        assertNull(TokenStore.get(TokenStore.Key.AccessToken))
        assertNull(TokenStore.get(TokenStore.Key.RefreshToken))
    }

    @Test fun `sign-in maps 401 and 403 to wording that fits a sign-in form`() = runBlocking {
        server.enqueue(MockResponse().setResponseCode(401))
        try { ApiClient.login("a@b.c", "x"); fail() } catch (e: ApiError) { assertEquals(ApiError.InvalidCredentials, e) }
        server.enqueue(MockResponse().setResponseCode(403))
        try { ApiClient.login("a@b.c", "x"); fail() } catch (e: ApiError) { assertEquals(ApiError.AccountDeactivated, e) }
    }

    @Test fun `sign-in stores both tokens`() = runBlocking {
        server.enqueue(MockResponse().setBody("""{"user":$user,"access_token":"a1","refresh_token":"r1"}"""))
        assertEquals("sam", ApiClient.login("sam@example.com", "pw").user.username)
        assertEquals("a1", TokenStore.get(TokenStore.Key.AccessToken))
        val sent = server.takeRequest()
        assertEquals("POST", sent.method)
        assertTrue(sent.getHeader("User-Agent")!!.startsWith("YardHarvest-Android/"))
        assertNull(sent.getHeader("Authorization"))
    }

    @Test fun `server errors surface the API's own message`() = runBlocking {
        TokenStore.set("t", TokenStore.Key.AccessToken)
        server.enqueue(MockResponse().setResponseCode(422).setBody("""{"error":"Post held for review: personal info."}"""))
        try { ApiClient.dashboard(1); fail() } catch (e: ApiError.Server) {
            assertEquals(422, e.status)
            assertEquals("Post held for review: personal info.", e.message)
        }
        server.enqueue(MockResponse().setResponseCode(429))
        try { ApiClient.dashboard(1); fail() } catch (e: ApiError) { assertEquals(ApiError.RateLimited, e) }
    }

    @Test fun `no token means no request`() = runBlocking {
        try { ApiClient.me(); fail() } catch (e: ApiError) { assertEquals(ApiError.MissingToken, e) }
        assertEquals(0, server.requestCount)
    }

    @Test fun `an ad-hoc sale intent decodes without a dues id`() {
        // Both in-person endpoints share this type; a required dues_id made
        // every New Sale fail to decode on iOS once.
        val pi = ApiClient.json.decodeFromString(InPersonPaymentIntent.serializer(),
            """{"client_secret":"pi_1_secret","payment_intent_id":"pi_1","amount":500,"currency":"usd"}""")
        assertNull(pi.duesId)
        assertEquals(500, pi.amount)
    }

    @Test fun `Stripe balance stays in cents`() {
        val b = ApiClient.json.decodeFromString(GardenStripeBalance.serializer(), """{"available":-250,"pending":1250}""")
        assertEquals(1000, b.total)
    }
}
