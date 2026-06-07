# 03 - Data Model (ERD)

Entity-relationship diagram of the core SQLAlchemy models in `app/models.py`.
Only the load-bearing columns and relationships are shown. The model set is
split into two ER diagrams (Marketplace and Community Gardens) for readability,
both centered on `User`. A third diagram covers cross-cutting billing/platform
entities.

## Marketplace domain

```mermaid
erDiagram
    USER ||--o{ LISTING : sells
    USER ||--o{ CART_ITEM : has
    USER ||--o{ ORDER : "buys (buyer_id)"
    USER ||--o{ ORDER : "fulfills (seller_id)"
    USER ||--o{ REVIEW : "writes (reviewer_id)"
    USER ||--o{ REVIEW : "receives (seller_id)"
    USER ||--o{ MESSAGE : "sends/receives"
    USER ||--o{ SUBSCRIPTION_PLAN : offers
    USER ||--o{ SUBSCRIPTION : subscribes
    USER ||--o{ SELLER_PLANTING : plants
    LISTING ||--o{ CART_ITEM : "in"
    LISTING ||--o{ ORDER_ITEM : "in"
    ORDER ||--o{ ORDER_ITEM : contains
    ORDER ||--o| REVIEW : "rated by"
    SUBSCRIPTION_PLAN ||--o{ SUBSCRIPTION : has
    SUBSCRIPTION_PLAN ||--o{ BOX_PREVIEW : has
    SELLER_PLANTING }o--o| LISTING : "links to"

    USER {
        int id PK
        string username
        string email
        string role "buyer|seller|both|manager|gardener"
        bool is_admin
        string stripe_customer_id
        string stripe_connect_account_id
        bool stripe_onboarding_complete
        float latitude
        float longitude
    }
    LISTING {
        int id PK
        int seller_id FK
        string title
        float price
        float base_price
        int quantity_available
        bool smart_pricing_enabled
        bool is_active
    }
    CART_ITEM {
        int id PK
        int buyer_id FK
        int listing_id FK
        int quantity
    }
    ORDER {
        int id PK
        int buyer_id FK
        int seller_id FK
        float total_price
        float subtotal
        float platform_commission
        float seller_earnings
        string status
        string stripe_payment_intent_id
        string payment_status
        int promo_code_id FK
    }
    ORDER_ITEM {
        int id PK
        int order_id FK
        int listing_id FK
        int quantity
        float unit_price
    }
    REVIEW {
        int id PK
        int reviewer_id FK
        int seller_id FK
        int order_id FK
        int rating
    }
    MESSAGE {
        int id PK
        string thread_id
        int sender_id FK
        int recipient_id FK
        int listing_id FK
    }
    SUBSCRIPTION_PLAN {
        int id PK
        int seller_id FK
        float price
        string frequency
    }
    SUBSCRIPTION {
        int id PK
        int plan_id FK
        int buyer_id FK
        string status
    }
    BOX_PREVIEW {
        int id PK
        int plan_id FK
        date week_of
    }
    SELLER_PLANTING {
        int id PK
        int seller_id FK
        string category
        date planted_date
        int linked_listing_id FK
    }
```

## Community gardens domain

```mermaid
erDiagram
    USER ||--o{ COMMUNITY_GARDEN : organizes
    USER ||--o{ GARDEN_MEMBERSHIP : "member of"
    COMMUNITY_GARDEN ||--o{ GARDEN_MEMBERSHIP : has
    COMMUNITY_GARDEN ||--o{ GARDEN_PLOT : has
    COMMUNITY_GARDEN ||--o{ GARDEN_EVENT : hosts
    COMMUNITY_GARDEN ||--o{ VOLUNTEER_SHIFT : schedules
    COMMUNITY_GARDEN ||--o{ GARDEN_DUES_RECORD : bills
    COMMUNITY_GARDEN ||--o{ GARDEN_EXPENSE : tracks
    COMMUNITY_GARDEN ||--o{ GARDEN_ANNOUNCEMENT : posts
    COMMUNITY_GARDEN ||--o{ SHARED_RESOURCE : lends
    COMMUNITY_GARDEN ||--o{ HARVEST_LOG : records
    COMMUNITY_GARDEN ||--o| GARDEN_SUBSCRIPTION : "billed via (Garden Pro)"
    GARDEN_PLOT ||--o{ PLOT_ASSIGNMENT_HISTORY : "history"
    GARDEN_PLOT }o--o| USER : "assigned_to / reserved_by"
    GARDEN_EVENT ||--o{ EVENT_RSVP : has
    VOLUNTEER_SHIFT ||--o{ SHIFT_SIGNUP : has
    SHARED_RESOURCE ||--o{ RESOURCE_CHECKOUT_LOG : logs
    USER ||--o{ GARDEN_DUES_RECORD : owes
    USER ||--o{ EVENT_RSVP : rsvps
    USER ||--o{ SHIFT_SIGNUP : signs_up

    COMMUNITY_GARDEN {
        int id PK
        string name
        string slug
        int organizer_id FK
        int total_plots
        float plot_fee_annual
        string subscription_status "none|trialing|active|expired"
    }
    GARDEN_MEMBERSHIP {
        int id PK
        int garden_id FK
        int user_id FK
        string role "organizer|treasurer|member..."
    }
    GARDEN_PLOT {
        int id PK
        int garden_id FK
        string plot_number
        string status
        int assigned_to_id FK
        int reserved_by_id FK
    }
    PLOT_ASSIGNMENT_HISTORY {
        int id PK
        int plot_id FK
        int user_id FK
        int season_year
    }
    GARDEN_EVENT {
        int id PK
        int garden_id FK
        datetime event_date
    }
    EVENT_RSVP {
        int id PK
        int event_id FK
        int user_id FK
        string status
    }
    VOLUNTEER_SHIFT {
        int id PK
        int garden_id FK
        date shift_date
    }
    SHIFT_SIGNUP {
        int id PK
        int shift_id FK
        int user_id FK
        float hours_logged
    }
    GARDEN_DUES_RECORD {
        int id PK
        int garden_id FK
        int user_id FK
        int season_year
        float amount_due
        float amount_paid
        string status
    }
    GARDEN_EXPENSE {
        int id PK
        int garden_id FK
        float amount
        string category
    }
    GARDEN_ANNOUNCEMENT {
        int id PK
        int garden_id FK
        int author_id FK
    }
    SHARED_RESOURCE {
        int id PK
        int garden_id FK
        string qr_code_token
        int checked_out_to_id FK
    }
    RESOURCE_CHECKOUT_LOG {
        int id PK
        int resource_id FK
        int user_id FK
    }
    HARVEST_LOG {
        int id PK
        int garden_id FK
        int user_id FK
        float quantity_lbs
    }
    GARDEN_SUBSCRIPTION {
        int id PK
        int garden_id FK
        string billing_cycle
        string status
        string stripe_subscription_id
        datetime trial_end
        datetime current_period_end
    }
```

## Platform / billing / cross-cutting

```mermaid
erDiagram
    USER ||--o{ SELLER_PAYOUT : "paid via"
    USER ||--o{ NOTIFICATION : receives
    USER ||--o{ PROMO_CODE : "created (admin)"
    USER ||--o{ REFUND : "initiated (admin)"
    ORDER ||--o{ REFUND : "refunds"
    GARDEN_SUBSCRIPTION ||--o{ REFUND : "refunds"
    PROMO_CODE ||--o{ PROMO_CODE_USAGE : has
    ORDER ||--o| PROMO_CODE_USAGE : "applied to"
    GARDEN_SUBSCRIPTION ||--o| PROMO_CODE_USAGE : "applied to"
    USER ||--o{ NEIGHBORHOOD_GROUP : creates
    NEIGHBORHOOD_GROUP ||--o{ GROUP_MEMBERSHIP : has
    NEIGHBORHOOD_GROUP ||--o{ GROUP_POST : has
    GROUP_POST ||--o{ GROUP_POST_COMMENT : has
    USER ||--o{ GROUP_MEMBERSHIP : joins

    SELLER_PAYOUT {
        int id PK
        int seller_id FK
        float amount
        string status
        string stripe_transfer_id
    }
    PRICING_CONFIG {
        int id PK
        float platform_commission_pct
        bool garden_pro_enabled
        int garden_pro_monthly_cents
        int garden_pro_yearly_cents
        int garden_pro_trial_days
    }
    SITE_EMAIL_CONFIG {
        int id PK
        bool marketplace_enabled
        string from_name
        bool analytics_enabled
    }
    NOTIFICATION {
        int id PK
        int user_id FK
        string type
        bool is_read
        int garden_id FK
    }
    PROMO_CODE {
        int id PK
        string code
        string discount_type
        float discount_value
        string scope
    }
    PROMO_CODE_USAGE {
        int id PK
        int promo_code_id FK
        int user_id FK
        int order_id FK
        int garden_subscription_id FK
    }
    REFUND {
        int id PK
        int order_id FK
        int garden_subscription_id FK
        string refund_type
        float amount
        string stripe_refund_id
        string stripe_reversal_id
    }
    NEIGHBORHOOD_GROUP {
        int id PK
        string slug
        int created_by_id FK
    }
    GROUP_MEMBERSHIP {
        int id PK
        int group_id FK
        int user_id FK
        string role
    }
    GROUP_POST {
        int id PK
        int group_id FK
        int author_id FK
        string post_type
    }
    GROUP_POST_COMMENT {
        int id PK
        int post_id FK
        int author_id FK
    }
    ANALYTICS_EVENT {
        int id PK
        string session_id
        int user_id FK
        string event_type
    }
```

## Notes

- `PRICING_CONFIG` and `SITE_EMAIL_CONFIG` are effectively singletons (one row),
  queried with `.first()`. `SITE_EMAIL_CONFIG.marketplace_enabled` is the master
  flag toggling the marketplace vs garden-only product surface.
- `REFUND` and `PROMO_CODE_USAGE` each polymorphically reference either an
  `ORDER` (marketplace) or a `GARDEN_SUBSCRIPTION` (Garden Pro) via nullable FKs.
- Additional smaller models exist (e.g. `GardenWaitlist`, `GardenWeatherAlert`,
  `GardenMessage`, `GardenPhoto`/`GardenPhotoComment`/`GardenPhotoLike`,
  `GardenEmailConfig`, `GardenKnowledgeArticle`, `GardenLayoutDraft`,
  `HarvestInterest`, `PlantingGuide`, `Photo`) — omitted here to keep the
  diagrams readable.
