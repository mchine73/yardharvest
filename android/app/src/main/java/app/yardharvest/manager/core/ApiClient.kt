package app.yardharvest.manager.core

import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.serialization.DeserializationStrategy
import kotlinx.serialization.SerializationException
import kotlinx.serialization.Serializable
import kotlinx.serialization.SerializationStrategy
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.serializer
import okhttp3.Call
import okhttp3.Callback
import okhttp3.HttpUrl.Companion.toHttpUrlOrNull
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import java.io.IOException
import java.util.concurrent.TimeUnit
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException

/** Typed errors surfaced by [ApiClient]. UI matches on these rather than raw IO errors. */
sealed class ApiError(override val message: String) : Exception(message) {
    object InvalidUrl : ApiError("Invalid request URL.")
    object InvalidResponse : ApiError("The server returned an unexpected response.")
    /** A 401 on a *background* request — the stored token is gone or stale. */
    object Unauthorized : ApiError("Your session has expired — please sign in again.")
    /** A 401 from the sign-in call itself: "your session expired" makes no sense there. */
    object InvalidCredentials : ApiError("Incorrect email or password.")
    /** A 403 from sign-in — right credentials, deactivated account. */
    object AccountDeactivated : ApiError("This account has been deactivated. Please contact support if you need it restored.")
    object Forbidden : ApiError("You don't have permission for this action.")
    object NotFound : ApiError("We couldn't find that.")
    object RateLimited : ApiError("Too many requests. Please slow down and try again.")
    class Server(val status: Int, val serverMessage: String?) : ApiError(serverMessage ?: "Server error ($status).")
    class Network(detail: String) : ApiError("Network error: $detail")
    class Decoding(detail: String) : ApiError("Couldn't read the server response. ($detail)")
    object MissingToken : ApiError("Not signed in.")
}

/** User-facing text for any failure, preferring the API's own wording. */
val Throwable.userMessage: String
    get() = (this as? ApiError)?.message ?: localizedMessage ?: "Something went wrong."

/**
 * REST client over OkHttp — the counterpart of the iOS actor-isolated
 * APIClient.
 *
 * - Auto-refreshes on 401 and replays the failed request once; concurrent
 *   401s share a single refresh.
 * - Bounded timeouts: the launch `/me` call gates the splash screen, and a
 *   request that never returns would leave the app on it forever.
 *
 * Endpoint methods live in extension files under `api/`.
 */
object ApiClient {
    val json = Json {
        ignoreUnknownKeys = true
        explicitNulls = false
        coerceInputValues = true
        isLenient = true
    }

    @PublishedApi internal var http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(20, TimeUnit.SECONDS)
        .writeTimeout(30, TimeUnit.SECONDS)
        .callTimeout(45, TimeUnit.SECONDS)
        .build()

    private val refreshMutex = Mutex()
    private val jsonType = "application/json; charset=utf-8".toMediaType()

    val userAgent: String get() = "YardHarvest-Android/${AppEnvironment.appVersion} (Android)"

    // ---- Public verbs ------------------------------------------------------

    suspend inline fun <reified R> get(
        path: String,
        query: Map<String, String> = emptyMap(),
        authenticated: Boolean = true,
    ): R = request("GET", path, query, null, authenticated, serializer<R>())

    suspend inline fun <reified B, reified R> post(path: String, body: B, authenticated: Boolean = true): R =
        request("POST", path, emptyMap(), encode(body), authenticated, serializer<R>())

    suspend inline fun <reified R> post(path: String, authenticated: Boolean = true): R =
        request("POST", path, emptyMap(), null, authenticated, serializer<R>())

    suspend inline fun <reified B, reified R> put(path: String, body: B, authenticated: Boolean = true): R =
        request("PUT", path, emptyMap(), encode(body), authenticated, serializer<R>())

    suspend inline fun <reified R> delete(path: String, authenticated: Boolean = true): R =
        request("DELETE", path, emptyMap(), null, authenticated, serializer<R>())

    /** For endpoints whose body we don't need. */
    suspend fun send(method: String, path: String, bodyJson: String? = null, authenticated: Boolean = true) {
        request<Unit>(method, path, emptyMap(), bodyJson, authenticated, null)
    }

    @PublishedApi internal inline fun <reified B> encode(body: B): String =
        json.encodeToString(serializer<B>() as SerializationStrategy<B>, body)

    /** Multipart upload for the photo endpoint. */
    suspend fun <R> uploadMultipart(
        path: String,
        fields: Map<String, String>,
        fileField: String,
        fileName: String,
        mimeType: String,
        fileData: ByteArray,
        deserializer: DeserializationStrategy<R>,
        authenticated: Boolean = true,
    ): R {
        val builder = MultipartBody.Builder().setType(MultipartBody.FORM)
        fields.forEach { (k, v) -> builder.addFormDataPart(k, v) }
        builder.addFormDataPart(fileField, fileName, fileData.toRequestBody(mimeType.toMediaType()))
        val body = builder.build()
        val req = buildRequest("POST", path, emptyMap(), body, authenticated)
        val (code, text) = execute(req)
        throwIfHttpError(code, text)
        return decode(deserializer, text)
    }

    // ---- Engine ------------------------------------------------------------

    @PublishedApi internal suspend fun <R> request(
        method: String,
        path: String,
        query: Map<String, String>,
        bodyJson: String?,
        authenticated: Boolean,
        deserializer: DeserializationStrategy<R>?,
    ): R {
        val tokenUsed = if (authenticated) TokenStore.get(TokenStore.Key.AccessToken) else null
        val first = buildRequest(method, path, query, bodyJson?.toRequestBody(jsonType), authenticated)
        var (code, text) = execute(first)
        if (code == 401 && authenticated) {
            refreshIfPossible(tokenUsed)
            val retried = buildRequest(method, path, query, bodyJson?.toRequestBody(jsonType), authenticated)
            val second = execute(retried)
            code = second.first
            text = second.second
        }
        throwIfHttpError(code, text)
        @Suppress("UNCHECKED_CAST")
        return if (deserializer == null) Unit as R else decode(deserializer, text)
    }

    private fun <R> decode(deserializer: DeserializationStrategy<R>, text: String): R = try {
        json.decodeFromString(deserializer, text.ifBlank { "{}" })
    } catch (e: SerializationException) {
        throw ApiError.Decoding(e.message ?: "unreadable")
    } catch (e: IllegalArgumentException) {
        throw ApiError.Decoding(e.message ?: "unreadable")
    }

    private fun buildRequest(
        method: String,
        path: String,
        query: Map<String, String>,
        body: RequestBody?,
        authenticated: Boolean,
    ): Request {
        val base = (AppEnvironment.baseUrl + path).toHttpUrlOrNull() ?: throw ApiError.InvalidUrl
        val url = base.newBuilder().apply { query.forEach { (k, v) -> addQueryParameter(k, v) } }.build()
        val builder = Request.Builder()
            .url(url)
            .header("Accept", "application/json")
            .header("User-Agent", userAgent)
        if (authenticated) {
            val token = TokenStore.get(TokenStore.Key.AccessToken) ?: throw ApiError.MissingToken
            builder.header("Authorization", "Bearer $token")
        }
        val needsBody = method == "POST" || method == "PUT" || method == "PATCH"
        builder.method(method, body ?: if (needsBody) "".toRequestBody(jsonType) else null)
        return builder.build()
    }

    private suspend fun execute(request: Request): Pair<Int, String> =
        suspendCancellableCoroutine { cont ->
            val call = http.newCall(request)
            cont.invokeOnCancellation { call.cancel() }
            call.enqueue(object : Callback {
                override fun onFailure(call: Call, e: IOException) {
                    cont.resumeWithException(ApiError.Network(e.localizedMessage ?: "offline"))
                }

                override fun onResponse(call: Call, response: Response) {
                    response.use {
                        val text = try { it.body?.string().orEmpty() } catch (e: IOException) {
                            cont.resumeWithException(ApiError.Network(e.localizedMessage ?: "read failed"))
                            return
                        }
                        cont.resume(it.code to text)
                    }
                }
            })
        }

    private fun throwIfHttpError(code: Int, text: String) {
        if (code in 200..299) return
        val serverMessage = try {
            val obj = json.parseToJsonElement(text) as? JsonObject
            (obj?.get("error") ?: obj?.get("message"))?.jsonPrimitive?.contentOrNull
        } catch (_: Exception) {
            null
        }
        throw when (code) {
            401 -> ApiError.Unauthorized
            403 -> ApiError.Forbidden
            404 -> ApiError.NotFound
            429 -> ApiError.RateLimited
            else -> ApiError.Server(code, serverMessage)
        }
    }

    /**
     * Single-flight refresh. A caller that waited on the lock while another
     * refreshed sees a newer access token than the one its request used, and
     * just retries with it.
     */
    private suspend fun refreshIfPossible(tokenUsed: String?) {
        refreshMutex.withLock {
            val current = TokenStore.get(TokenStore.Key.AccessToken)
            if (current != null && current != tokenUsed) return
            refresh()
        }
    }

    @Serializable private data class RefreshReq(val refresh_token: String)
    @Serializable private data class RefreshResp(val access_token: String, val refresh_token: String)

    private suspend fun refresh() {
        val refreshToken = TokenStore.get(TokenStore.Key.RefreshToken) ?: throw ApiError.Unauthorized
        val body = json.encodeToString(RefreshReq.serializer(), RefreshReq(refreshToken)).toRequestBody(jsonType)
        val req = buildRequest("POST", "/api/auth/token/refresh", emptyMap(), body, authenticated = false)
        val (code, text) = execute(req)
        if (code !in 200..299) {
            TokenStore.clear()
            throw ApiError.Unauthorized
        }
        val decoded = decode(RefreshResp.serializer(), text)
        TokenStore.set(decoded.access_token, TokenStore.Key.AccessToken)
        TokenStore.set(decoded.refresh_token, TokenStore.Key.RefreshToken)
    }
}
