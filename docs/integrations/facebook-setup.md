# Facebook (Meta) Integration — Setup Guide

The CRM can **publish posts to a Facebook Page** and manage the **Page inbox**
(Messenger). This requires a Meta Developer app that *you* create and submit for
App Review. Claude builds the integration; these are the one-time, human steps.

> You need: a Facebook account, a Facebook **Page** you administer, and (for go
> live beyond yourself) a **Meta Business** verification.

## 1. Create the Meta app
1. Go to <https://developers.facebook.com/apps/> → **Create app**.
2. Use case: **Other** → type **Business** → name it (e.g. "YardHarvest CRM").
3. Note the **App ID** and **App Secret** (Settings → Basic).

## 2. Add products
- **Facebook Login for Business** → Settings:
  - Valid OAuth Redirect URI: `https://www.yardharvest.app/crm/facebook/callback`
- **Webhooks** → subscribe the **Page** object to fields `messages` and `feed`:
  - Callback URL: `https://www.yardharvest.app/crm/api/facebook/webhook`
  - Verify token: the same random string you set as `FACEBOOK_WEBHOOK_VERIFY_TOKEN`.

## 3. Set environment variables (Render → web service → Environment)
| Var | Value |
|---|---|
| `FACEBOOK_APP_ID` | App ID from step 1 |
| `FACEBOOK_APP_SECRET` | App Secret from step 1 |
| `FACEBOOK_WEBHOOK_VERIFY_TOKEN` | any random string (must match the webhook UI) |

(Optional `FACEBOOK_GRAPH_VERSION`, defaults to `v21.0`.) Redeploy/restart.

## 4. Request permissions (App Review)
In **App Review → Permissions and Features**, request and justify:
`pages_show_list`, `pages_read_engagement`, `pages_manage_posts`,
`pages_messaging`, `pages_manage_metadata`, `pages_read_user_content`.

While in **Development mode** the app works for **app admins/testers only** — so
you can fully test the connect flow, publishing, and the inbox with your own
account *before* App Review. App Review is required only to let other people /
the public Page audience use it.

## 5. Connect in the CRM
CRM → **Integrations → Facebook → Connect Facebook Page**, sign in, pick the
Page. The CRM stores the long-lived Page token and subscribes the Page to the
webhook. The settings page shows connection + capability status.

## Notes
- The Page access token is stored in the `crm_facebook_account` table. Treat the
  database as sensitive; rotate by disconnecting + reconnecting.
- The webhook is authenticated by Meta's `X-Hub-Signature-256` (HMAC of the
  payload with the app secret) — unsigned/invalid requests are rejected.
- Tokens are long-lived (~60 days for user tokens; Page tokens derived from a
  long-lived user token don't expire while the app/permission stand). Reconnect
  if posting/inbox calls start returning auth errors.
