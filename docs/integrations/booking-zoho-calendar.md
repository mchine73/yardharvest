# Booking page → Zoho Calendar setup

The public scheduling page lives at **`/book`** and is configured at
**`/admin/booking`** (site-admin only). Bookings always save + email; connecting
Zoho Calendar additionally (a) writes each booking to your calendar with the
guest invited, and (b) lets availability hide times you're already busy.

Until the four env vars below are set, the page works fully minus calendar sync
(`zoho_sync_status = "skipped"`). This mirrors how Stripe/ZeptoMail/Twilio
degrade when unconfigured — no code change is needed to turn it on, just env.

**Only you can do this** — it requires signing into your Zoho account and
generating OAuth credentials. Claude cannot enter credentials.

## What you'll end up setting (Render → Environment)

| Env var | What it is |
|---|---|
| `ZOHO_CLIENT_ID` | OAuth client id (from api-console.zoho.com) |
| `ZOHO_CLIENT_SECRET` | OAuth client secret |
| `ZOHO_REFRESH_TOKEN` | Long-lived refresh token (generated once, below) |
| `ZOHO_CALENDAR_UID` | The calendar to write to (`GET /calendars`, or the admin button) |
| `ZOHO_ACCOUNTS_URL` | *(optional)* data-center override, e.g. `https://accounts.zoho.eu` |
| `ZOHO_CALENDAR_API_URL` | *(optional)* e.g. `https://calendar.zoho.eu/api/v1` |

Defaults target the **US** data center (`accounts.zoho.com` /
`calendar.zoho.com`). If your Zoho account is EU/IN/AU/JP, set the two optional
overrides to match — otherwise the token exchange returns `invalid_client`.

## Step 1 — Create a Self Client

1. Go to <https://api-console.zoho.com/> (sign in with the Zoho account whose
   calendar you want to write to).
2. **Add Client → Self Client → Create**. Accept.
3. Copy the **Client ID** and **Client Secret**.

## Step 2 — Generate a grant code

1. In the Self Client, open the **Generate Code** tab.
2. Scope: `ZohoCalendar.event.ALL`
   (this covers create + the free/busy read the conflict-check uses).
3. Time duration: `10 minutes`. Add any scope description. **Create**.
4. Copy the **grant code** (it expires quickly — do step 3 right away).

## Step 3 — Exchange the grant code for a refresh token

Run within the 10-minute window (swap in your values):

```bash
curl -X POST "https://accounts.zoho.com/oauth/v2/token" \
  -d "grant_type=authorization_code" \
  -d "client_id=YOUR_CLIENT_ID" \
  -d "client_secret=YOUR_CLIENT_SECRET" \
  -d "code=YOUR_GRANT_CODE"
```

The JSON response contains a **`refresh_token`** — save it. It's long-lived;
the app exchanges it for short-lived access tokens automatically.
(If you get `invalid_code`, the grant expired — regenerate it in step 2.)

## Step 4 — Find your calendar UID

Set `ZOHO_CLIENT_ID`, `ZOHO_CLIENT_SECRET`, `ZOHO_REFRESH_TOKEN` on Render and
redeploy, then in **`/admin/booking` → Zoho Calendar sync → "List my
calendars"** — each calendar shows its `uid`. Copy the one you want.

(Or by hand, with a fresh access token:
`curl "https://calendar.zoho.com/api/v1/calendars" -H "Authorization: Zoho-oauthtoken ACCESS_TOKEN"`.)

Set that value as `ZOHO_CALENDAR_UID` and redeploy.

## Step 5 — Verify

- `GET https://www.yardharvest.app/api/health/zoho-calendar` should return
  `{"configured": true, "auth_ok": true, "calendar_uid_set": true, ...}`.
- Book a test slot on `/book`. The event should appear on your Zoho calendar
  (with the guest invited), and `/admin/booking → Upcoming bookings` should show
  an **"on calendar"** badge.

## Notes

- **Availability is defined in your timezone** (`/admin/booking → Page settings
  → Your timezone`); visitors see slots converted to their own timezone.
- **Conflict check**: "Hide times I'm already busy on my Zoho calendar" (on by
  default) reads your events for the booking horizon and removes overlapping
  slots. If the read fails, it degrades to blocking only YardHarvest bookings —
  it never blocks the page.
- **Every booking upserts a CRM lead** (status *Engaged*, source *Booking*) and
  logs the meeting to that contact's timeline, feeding the BDR funnel.
- A cancellation (via the guest's manage link) deletes the calendar event and
  logs the cancellation to the CRM.
