# YardHarvest Android

Native Android companion app for community-garden organizers and members —
the same app as `ios/`, screen for screen, on the same `/api` backend and the
same lime / Onest design tokens. Kotlin + Jetpack Compose, Android 8.0+
(API 26), targets API 36.

## Feature parity with iOS

| iOS | Android |
|---|---|
| Sign in, register, forgot password, connection settings | Same |
| Garden picker, manager dashboard, member home | Same; the picker also lists gardens you help run (co-organizer roles) |
| Plots, plot detail, maintenance | Same |
| Events + RSVP, shifts + sign-up, announcements, waitlist | Same |
| Harvest log (quick add, history) | Same |
| Community wall, photos, moderation queue, reviews, blocked members | Same |
| Inbox, threads, notifications, badges | Same |
| Dues: My Dues (Stripe PaymentSheet), roster, collect, ad-hoc charge, Money | Same |
| Tap to Pay (Stripe Terminal) | Same SDK, Android flavor — see below |
| Tool library: QR scan, Phomemo / JADENS label printing over BLE | Same wire formats, byte for byte |
| Roles and permissions | Same |
| Face ID app lock | Biometric / device-credential lock with the same 60 s grace |
| Push notifications (APNs) | FCM — needs Firebase setup, below |
| "Log Harvest" App Intent (Siri / Shortcuts) | Launcher shortcuts: **Log harvest** and **Scan a tool** (long-press the icon) |

One deliberate difference: event and shift times the server sends without a
time zone are shown as the garden's wall-clock time, and bare dates as that
calendar day. (The iOS client reads every naive timestamp as UTC, which can
shift a 9 am workday or a due date when the phone is west of UTC.)

## Build

Needs JDK 17 and the Android SDK (platform 36). Android Studio bundles both;
open the `android/` folder and run the `app` configuration.

From a shell:

```bash
cd android
./gradlew :app:assembleDebug
```

The APK lands in `app/build/outputs/apk/debug/`. Unit tests and lint:

```bash
./gradlew :app:testDebugUnitTest :app:lintDebug
```

CI (`.github/workflows/android.yml`) runs the same three tasks on every PR
that touches `android/` and attaches the debug APK to the run.

### Local backend

Debug and release builds both talk to `https://www.yardharvest.app`. To point
the app at a dev server, tap the gear on the sign-in screen → **Connection** →
**Use Local Server (Emulator)**, which is `http://10.0.2.2:5000` — the host
machine as seen from the Android emulator. Cleartext HTTP is allowed only for
`localhost`, `10.0.2.2` and `127.0.0.1`.

## Push notifications (Firebase)

Push is off until both halves are configured; the app runs fine without it.

1. In the [Firebase console](https://console.firebase.google.com), create a
   project (or reuse one) and add an Android app with package
   `app.yardharvest.manager`.
2. Download `google-services.json` into `android/app/`. It is gitignored; the
   build applies the Google services plugin only when the file is present.
3. In Project settings → Service accounts, generate a private key. Paste the
   whole JSON into Render as `FCM_SERVICE_ACCOUNT_JSON` (or upload it as a
   Secret File and set `FCM_SERVICE_ACCOUNT_FILE` to its path).
4. Check it: `GET /api/health/config` should report `"fcm_configured": true`,
   then sign in on a phone, allow notifications, and run
   `flask push-test you@example.com` from the Render shell.

The backend routes each user's push by the platform their app registered
(`ios` → APNs, `android` → FCM); see `app/push_service.py`.

## Tap to Pay

Stripe's Tap to Pay on Android needs NFC, Google Play services, Android 11 or
later, and location permission (Stripe requires it to know where a payment
is taken). Whether a phone qualifies is Stripe's SDK's call at runtime; the
app asks for location on the Payments screen and shows why Tap to Pay is
unavailable on phones that can't run it.

**Debug builds always use Stripe's simulated reader** — Stripe refuses real
Tap to Pay in a debuggable app — so charges in a debug build go through
Stripe's test flow. Real cards need a signed release build installed from the
Play Store (or sideloaded), on a garden whose Stripe account has Tap to Pay
enabled.

## Release signing

Release builds are minified with R8 and signed from an untracked
`android/keystore.properties`:

```properties
storeFile=../yardharvest-release.jks
storePassword=…
keyAlias=yardharvest
keyPassword=…
```

Without that file `assembleRelease` produces an unsigned APK. Keep the
keystore and its passwords out of the repo and backed up: Play requires every
update to be signed with the same key (or enrol in Play App Signing).

## Project layout

```
android/
├── app/
│   ├── build.gradle.kts
│   ├── proguard-rules.pro
│   └── src/
│       ├── main/java/app/yardharvest/manager/
│       │   ├── MainActivity.kt, YardHarvestApp.kt
│       │   ├── core/        # ApiClient, tokens, auth, stores, push, app lock,
│       │   │                # Tap to Pay, Phomemo BLE printing, dates
│       │   ├── api/         # Endpoint extensions (one per iOS endpoint)
│       │   ├── model/       # @Serializable API types
│       │   └── ui/          # brand/ (tokens + components), nav/, one folder per feature
│       └── test/            # JVM unit tests
├── gradle/libs.versions.toml
└── settings.gradle.kts
```
