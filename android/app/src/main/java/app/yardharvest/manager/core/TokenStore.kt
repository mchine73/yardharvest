package app.yardharvest.manager.core

import android.content.Context
import android.security.keystore.KeyGenParameterSpec
import android.security.keystore.KeyProperties
import android.util.Base64
import androidx.core.content.edit
import java.security.KeyStore
import javax.crypto.Cipher
import javax.crypto.KeyGenerator
import javax.crypto.SecretKey
import javax.crypto.spec.GCMParameterSpec

/**
 * Storage for the access + refresh JWTs — the Android counterpart of the iOS
 * KeychainStore. Values are sealed with an AES-GCM key that lives in the
 * Android Keystore and never leaves it, so the preference file on its own is
 * useless off this device.
 */
object TokenStore {
    enum class Key(val raw: String) {
        AccessToken("yh.auth.accessToken"),
        RefreshToken("yh.auth.refreshToken"),
    }

    interface Backend {
        fun get(key: Key): String?
        fun set(key: Key, value: String?)
    }

    /** Replaced with [InMemory] in unit tests, where there is no Keystore. */
    @Volatile var backend: Backend = InMemory()

    fun init(context: Context) {
        backend = KeystoreBackend(context.applicationContext)
    }

    fun get(key: Key): String? = backend.get(key)
    fun set(value: String?, key: Key) = backend.set(key, value)

    fun clear() {
        backend.set(Key.AccessToken, null)
        backend.set(Key.RefreshToken, null)
    }

    class InMemory : Backend {
        private val values = mutableMapOf<Key, String>()
        @Synchronized override fun get(key: Key) = values[key]
        @Synchronized override fun set(key: Key, value: String?) {
            if (value == null) values.remove(key) else values[key] = value
        }
    }

    private class KeystoreBackend(context: Context) : Backend {
        private val prefs = context.getSharedPreferences("yh.secure", Context.MODE_PRIVATE)
        private val alias = "yh.session.key"

        private fun key(): SecretKey {
            val ks = KeyStore.getInstance("AndroidKeyStore").apply { load(null) }
            (ks.getEntry(alias, null) as? KeyStore.SecretKeyEntry)?.let { return it.secretKey }
            val gen = KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES, "AndroidKeyStore")
            gen.init(
                KeyGenParameterSpec.Builder(alias, KeyProperties.PURPOSE_ENCRYPT or KeyProperties.PURPOSE_DECRYPT)
                    .setBlockModes(KeyProperties.BLOCK_MODE_GCM)
                    .setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE)
                    .setKeySize(256)
                    .build()
            )
            return gen.generateKey()
        }

        @Synchronized override fun get(key: Key): String? {
            val stored = prefs.getString(key.raw, null) ?: return null
            return try {
                val bytes = Base64.decode(stored, Base64.NO_WRAP)
                val cipher = Cipher.getInstance("AES/GCM/NoPadding")
                cipher.init(Cipher.DECRYPT_MODE, key(), GCMParameterSpec(128, bytes, 0, 12))
                String(cipher.doFinal(bytes, 12, bytes.size - 12), Charsets.UTF_8)
            } catch (e: Exception) {
                // A key wiped by a lock-screen change, or a restored file from
                // another device: the value is unrecoverable, so drop it and
                // let the person sign in again.
                prefs.edit { remove(key.raw) }
                null
            }
        }

        @Synchronized override fun set(key: Key, value: String?) {
            if (value == null) {
                prefs.edit { remove(key.raw) }
                return
            }
            val cipher = Cipher.getInstance("AES/GCM/NoPadding")
            cipher.init(Cipher.ENCRYPT_MODE, key())
            val sealed = cipher.iv + cipher.doFinal(value.toByteArray(Charsets.UTF_8))
            prefs.edit { putString(key.raw, Base64.encodeToString(sealed, Base64.NO_WRAP)) }
        }
    }
}
