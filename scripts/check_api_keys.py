#!/usr/bin/env python3
"""
Validate YardHarvest third-party API credentials supplied via environment
(GitHub Actions injects them from repo secrets).

For each provider: if the secret is unset or still the "REPLACE_ME" placeholder
-> SKIP. Otherwise make one lightweight authenticated call and PASS/FAIL on the
response. Stdlib only (no pip install needed). Exits non-zero if any *configured*
credential fails, so the workflow goes red.

Secret VALUES are never printed — only service name, status, and HTTP code.
"""
import base64
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.error
import urllib.request

results = []


def add(service, status, detail):
    results.append((service, status, detail))


def is_set(v):
    return bool(v) and v.strip() and v.strip().upper() != "REPLACE_ME"


def http(method, url, headers=None, timeout=20, data=None):
    req = urllib.request.Request(url, method=method, headers=headers or {},
                                 data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, e.reason
    except Exception as e:  # noqa: BLE001
        return None, str(e)[:80]


# ---- Stripe -------------------------------------------------------------
sk = os.environ.get("STRIPE_SECRET_KEY", "")
if is_set(sk):
    code, _ = http("GET", "https://api.stripe.com/v1/account",
                   {"Authorization": f"Bearer {sk}"})
    add("Stripe", "PASS" if code == 200 else "FAIL", f"HTTP {code}")
else:
    add("Stripe", "SKIP", "STRIPE_SECRET_KEY not set")

# ---- SendGrid -----------------------------------------------------------
sg = os.environ.get("SENDGRID_API_KEY", "")
if is_set(sg):
    code, _ = http("GET", "https://api.sendgrid.com/v3/scopes",
                   {"Authorization": f"Bearer {sg}"})
    add("SendGrid", "PASS" if code == 200 else "FAIL", f"HTTP {code}")
else:
    add("SendGrid", "SKIP", "SENDGRID_API_KEY not set")

# ---- Twilio -------------------------------------------------------------
sid = os.environ.get("TWILIO_ACCOUNT_SID", "")
tok = os.environ.get("TWILIO_AUTH_TOKEN", "")
if is_set(sid) and is_set(tok):
    auth = base64.b64encode(f"{sid}:{tok}".encode()).decode()
    code, _ = http("GET",
                   f"https://api.twilio.com/2010-04-01/Accounts/{sid}.json",
                   {"Authorization": f"Basic {auth}"})
    add("Twilio", "PASS" if code == 200 else "FAIL", f"HTTP {code}")
else:
    add("Twilio", "SKIP", "TWILIO_ACCOUNT_SID/AUTH_TOKEN not set")

# ---- OpenWeather --------------------------------------------------------
ow = os.environ.get("OPENWEATHER_API_KEY", "")
if is_set(ow):
    code, _ = http("GET",
                   "https://api.openweathermap.org/data/2.5/weather"
                   f"?q=London&appid={ow}")
    add("OpenWeather", "PASS" if code == 200 else "FAIL", f"HTTP {code}")
else:
    add("OpenWeather", "SKIP", "OPENWEATHER_API_KEY not set")

# ---- DoorDash Drive (HS256 JWT, stdlib) ---------------------------------
dd_dev = os.environ.get("DOORDASH_DEVELOPER_ID", "")
dd_key = os.environ.get("DOORDASH_KEY_ID", "")
dd_sec = os.environ.get("DOORDASH_SIGNING_SECRET", "")
if is_set(dd_dev) and is_set(dd_key) and is_set(dd_sec):
    try:
        def b64u(b):
            return base64.urlsafe_b64encode(b).rstrip(b"=")

        now = int(time.time())
        header = {"alg": "HS256", "typ": "JWT", "dd-ver": "DD-JWT-V1"}
        payload = {"aud": "doordash", "iss": dd_dev, "kid": dd_key,
                   "iat": now, "exp": now + 300}
        seg = (b64u(json.dumps(header, separators=(",", ":")).encode())
               + b"." + b64u(json.dumps(payload, separators=(",", ":")).encode()))
        secret = base64.urlsafe_b64decode(dd_sec + "=" * (-len(dd_sec) % 4))
        sig = b64u(hmac.new(secret, seg, hashlib.sha256).digest())
        token = (seg + b"." + sig).decode()
        # Hit a deliberately-missing delivery: 401/403 => bad creds;
        # 400/404 => auth accepted, resource just not found.
        code, _ = http("GET",
                       "https://openapi.doordash.com/drive/v2/deliveries/"
                       "yardharvest-keycheck",
                       {"Authorization": f"Bearer {token}",
                        "Accept": "application/json"})
        ok = code in (200, 400, 404)
        add("DoorDash", "PASS" if ok else "FAIL", f"HTTP {code}")
    except Exception as e:  # noqa: BLE001
        add("DoorDash", "FAIL", f"jwt/err {str(e)[:60]}")
else:
    add("DoorDash", "SKIP", "DOORDASH_* not set")

# ---- Zoho ZeptoMail (fallback email, transactional API) -----------------
# Validate the send-only token without dispatching mail: POST an empty body.
# Valid token + invalid payload -> 400 (auth accepted); bad token -> 401.
zm = os.environ.get("ZEPTOMAIL_TOKEN", "")
zm_url = os.environ.get("ZEPTOMAIL_API_URL", "") or "https://api.zeptomail.com/v1.1/email"
if is_set(zm):
    code, _ = http("POST", zm_url,
                   {"Authorization": f"Zoho-enczapikey {zm}",
                    "Content-Type": "application/json",
                    "Accept": "application/json"},
                   data=b"{}")
    # 400 = auth OK, payload rejected (expected); 200/201 = accepted (unlikely
    # with empty body). 401/403 = bad/again unauthorized token.
    ok = code in (200, 201, 400)
    add("ZeptoMail", "PASS" if ok else "FAIL", f"HTTP {code}")
else:
    add("ZeptoMail", "SKIP", "ZEPTOMAIL_TOKEN not set")

# ---- Report -------------------------------------------------------------
print(f"{'Service':14} {'Status':6} Detail")
print("-" * 52)
fails = 0
for svc, st, detail in results:
    print(f"{svc:14} {st:6} {detail}")
    if st == "FAIL":
        fails += 1
n_pass = sum(1 for _, s, _ in results if s == "PASS")
n_skip = sum(1 for _, s, _ in results if s == "SKIP")
print("-" * 52)
print(f"{n_pass} pass, {n_skip} skip, {fails} fail")
sys.exit(1 if fails else 0)
