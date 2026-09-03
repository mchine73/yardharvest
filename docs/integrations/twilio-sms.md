# Twilio SMS — setup and the opt-out loop

Three environment variables on the Render **web service**:

| Variable | Where it comes from |
|---|---|
| `TWILIO_ACCOUNT_SID` | Console → Account Info. Starts `AC`. **Not** an API Key SID (`SK…`) — the client authenticates with the account pair, not an API key. |
| `TWILIO_AUTH_TOKEN` | The same Account Info panel, behind the reveal control. 32 lowercase hex characters. |
| `TWILIO_PHONE_NUMBER` | The approved sending number, in E.164: `+1XXXXXXXXXX`. |

Both credentials must come from the **same project**. A subaccount's number
with the parent's SID authenticates as nothing.

## Verifying

```bash
curl -s https://www.yardharvest.app/api/health/sms
```

Reports each variable separately, whether the from-number is valid E.164,
whether the SID looks like an Account SID, and — when Twilio refuses the
credentials — Twilio's own error. `"invalid username"` means the SID is
wrong; a bare `"Authenticate"` means the SID is right and the token is not.

Booleans and error text only; it never echoes a credential.

Then one real message, as a platform admin:

```
POST /api/admin/test-sms   {"phone": "+1XXXXXXXXXX"}
```

That is the only send path that ignores opt-in, because you name the
recipient explicitly.

## Inbound: STOP, START, HELP

Configure the number's **A MESSAGE COMES IN** webhook (HTTP POST) as:

```
https://www.yardharvest.app/api/webhooks/twilio/sms
```

Twilio handles these keywords itself — it blocks or unblocks the number on its
side and sends the standard reply — and *also* posts the message to this
endpoint tagged with `OptOutType`, so YardHarvest can keep its own record
straight. Two consequences, both deliberate:

* **The endpoint replies with empty TwiML.** Twilio has already answered; a
  message from us would arrive right behind its own.
* **STOP clears `sms_opt_in`, START restores it.** Without that, a member's
  own preferences would claim they are subscribed while the carrier blocks
  every message — and we would retry forever, which on a 10DLC number is what
  gets a sender flagged.

`HELP` changes no preference.

**Every request is signature-checked** (`X-Twilio-Signature`, validated with
the auth token). Unsigned requests are refused. This matters more in one
direction than the other: a forged opt-*out* merely silences us, while a
forged opt-*in* resumes messaging someone who asked us to stop.

Outbound sends are belt-and-braces: a Twilio error **21610** (recipient replied
STOP) clears the opt-in too, so suppression works even if the inbound webhook
is misconfigured. Error **21211** (invalid number) deliberately does *not* —
that is a data problem, and treating it as consent would unsubscribe someone
over a typo.

## Phone numbers

Stored in E.164 or refused. `normalize_phone()` runs at every write point —
both registration paths, profile edit, notification preferences — and again
before each send. A bare ten digits is assumed US; anything international
needs its own `+` and country code.

Numbers written before this existed are in whatever shape their owner typed,
and Twilio rejects them:

```bash
flask normalize-phone-numbers --dry-run
flask normalize-phone-numbers
```

It repairs what it can and lists what it cannot, flagging any **opted-in**
member among them — those are people who believe they are subscribed and are
unreachable until someone fixes the number by hand.

## What sends today

`SiteEmailConfig` toggles gate each category, and a send also needs the
member's `sms_opt_in` and a phone number. Check the live state in the
`toggles` block of `/api/health/sms`.
