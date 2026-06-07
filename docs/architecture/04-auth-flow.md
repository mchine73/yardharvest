# 04 - Authentication Flows

YardHarvest supports two auth mechanisms against the same API:
- **Web**: Flask-Login session cookies (SameSite=Lax, HttpOnly, Secure in prod).
- **Mobile**: JWT access (1h) + refresh (30d) tokens via `Authorization: Bearer`.

The `@token_or_session` decorator and `get_current_user()` accept either, so
most endpoints serve both clients.

## Web session login

```mermaid
sequenceDiagram
    actor U as User (browser)
    participant FE as React SPA
    participant BE as Flask /api/auth
    participant DB as Postgres

    U->>FE: enter email + password
    FE->>BE: POST /api/auth/login (withCredentials)
    BE->>DB: User.query by email
    DB-->>BE: user row
    BE->>BE: check_password() then session.clear() (anti-fixation)
    BE->>BE: login_user(user) -> sets session cookie
    BE-->>FE: 200 user_to_dict + Set-Cookie (session)
    FE->>FE: AuthContext stores user
    Note over FE,BE: Subsequent /api/* calls send the<br/>session cookie automatically.
    FE->>BE: GET /api/auth/me (cookie)
    BE-->>FE: current user
```

## Mobile JWT login + refresh

```mermaid
sequenceDiagram
    actor M as Mobile app
    participant BE as Flask /api/auth
    participant DB as Postgres

    M->>BE: POST /api/auth/token (email,password)
    BE->>DB: User.query by email, check_password
    BE->>BE: generate_tokens() -> access(1h)+refresh(30d)<br/>payload embeds tv=token_version
    BE-->>M: { user, access_token, refresh_token, expires_in }

    Note over M,BE: Authenticated request
    M->>BE: GET /api/... (Authorization: Bearer access)
    BE->>BE: _get_user_from_token(): decode + verify tv >= user.token_version
    BE-->>M: 200 resource

    Note over M,BE: Access token expired
    M->>BE: POST /api/auth/token/refresh (refresh_token)
    BE->>BE: decode_token(type=refresh), load user, check active
    BE-->>M: new access + refresh tokens

    Note over M,BE: Logout / revoke
    M->>BE: POST /api/auth/logout (Bearer)
    BE->>DB: user.token_version += 1 (invalidates all old JWTs)
    BE-->>M: 200
```

## Role-gated registration (marketplace hidden)

The allowed signup roles depend on the admin `marketplace_enabled` flag in
`SiteEmailConfig`. When the marketplace is hidden, signup offers only the two
garden roles.

```mermaid
sequenceDiagram
    actor U as New user
    participant FE as React SPA
    participant BE as Flask /api/auth/register
    participant Geo as Nominatim geocoder
    participant DB as Postgres

    U->>FE: open Register
    FE->>BE: GET marketplace status (SiteEmailConfig.marketplace_enabled)
    BE-->>FE: marketplace_enabled = true/false
    alt marketplace_enabled = true
        FE-->>U: role choices: buyer / seller / both
    else marketplace hidden
        FE-->>U: role choices: manager / gardener
    end

    U->>FE: submit username,email,password,role,address
    FE->>BE: POST /api/auth/register
    BE->>BE: validate_password() + username regex
    BE->>DB: check email/username uniqueness
    BE->>BE: allowed_signup_roles() — reject role not in allowlist
    Note right of BE: marketplace ON -> (buyer,seller,both)<br/>marketplace OFF -> (manager,gardener)
    BE->>Geo: geocode_address(address,city,state,zip)
    Geo-->>BE: lat, lon
    BE->>DB: create User (hashed pw, lat/lon)
    BE->>BE: login_user() (web) — token_register returns JWTs (mobile)
    BE-->>FE: 201 user_to_dict
```

## Notes

- Origin-header validation (`before_request` in `app/__init__.py`) protects
  state-changing `/api/*` requests; Bearer-token requests skip it.
- Password reset uses a single-use JWT that embeds the first 16 chars of the
  password hash — once the password changes, old reset links stop verifying.
