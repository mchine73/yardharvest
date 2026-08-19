import secrets
from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timezone
from sqlalchemy import event, select
from werkzeug.security import generate_password_hash, check_password_hash

# Password hashing method, pinned explicitly so a future change to the library
# default can't silently weaken stored hashes. scrypt is Werkzeug's current
# strong (memory-hard) default. A login with a hash on any other scheme is
# transparently upgraded — see User.needs_password_rehash() + the auth flow.
PASSWORD_HASH_METHOD = 'scrypt'

# Opaque public identifiers exposed on public surfaces (URLs, UI, API payloads)
# instead of the sequential integer PK, so record counts/ordering aren't leaked.
# Prefixed, CSPRNG-generated tokens over an unambiguous base58-style alphabet
# (no 0/O/1/I/l), e.g. "usr_a9Kp2mQ4Lr8t" / "grd_7tWx4LrB2nKp".
_PUBLIC_ID_ALPHABET = '23456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
_PUBLIC_ID_LEN = 14


def as_utc(dt):
    """Normalize a possibly-naive datetime to aware UTC for safe comparison.

    Our db.DateTime columns are timezone-less, so SQLAlchemy hands back NAIVE
    datetimes (Postgres and SQLite alike) even though we always store UTC.
    Python-level arithmetic against ``datetime.now(timezone.utc)`` raises
    ``TypeError: can't subtract offset-naive and offset-aware datetimes``
    unless the column value is normalized first. SQL-level comparisons in
    query filters are unaffected. Passes aware datetimes through unchanged.
    """
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def generate_public_id(prefix):
    """Return a new opaque public id like ``usr_a9Kp2mQ4Lr8t`` (CSPRNG).

    ~14 chars over a 57-symbol alphabet is ~81 bits of entropy, so ids are
    unguessable and effectively never collide.
    """
    token = ''.join(secrets.choice(_PUBLIC_ID_ALPHABET) for _ in range(_PUBLIC_ID_LEN))
    return f'{prefix}_{token}'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


def _assign_public_id(connection, table, target, prefix):
    """Assign a unique opaque public_id (``<prefix>_<token>``) before insert.

    Public-facing surfaces use this non-sequential code instead of the
    auto-increment primary key, so record counts and ordering aren't leaked.
    The token is CSPRNG-generated (``secrets``); uniqueness is checked against
    the live transaction connection (no ORM autoflush) and retried, though a
    collision is astronomically unlikely.
    """
    if getattr(target, 'public_id', None):
        return
    for _ in range(25):
        candidate = generate_public_id(prefix)
        exists = connection.execute(
            select(table.c.id).where(table.c.public_id == candidate)
        ).first()
        if not exists:
            target.public_id = candidate
            return
    target.public_id = generate_public_id(prefix)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, index=True)  # opaque public code, e.g. usr_a9Kp2mQ4Lr8t
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), default='buyer')
    # Marketplace roles: buyer, seller, both
    # Garden-only roles (when marketplace hidden): manager (Garden Manager),
    #                                               gardener (New Gardener)
    display_name = db.Column(db.String(100))
    bio = db.Column(db.Text)
    address = db.Column(db.String(255))
    city = db.Column(db.String(100))
    state = db.Column(db.String(50))
    zip_code = db.Column(db.String(20))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    profile_image = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_active_user = db.Column(db.Boolean, default=True)
    is_admin = db.Column(db.Boolean, default=False)
    gardening_story = db.Column(db.Text)
    years_gardening = db.Column(db.Integer)
    gallery_image_1 = db.Column(db.String(255))
    gallery_image_2 = db.Column(db.String(255))
    gallery_image_3 = db.Column(db.String(255))
    phone_number = db.Column(db.String(20))
    sms_opt_in = db.Column(db.Boolean, default=False)
    device_token = db.Column(db.String(255))       # APNs/FCM push token (mobile)
    device_platform = db.Column(db.String(10))      # 'ios' or 'android'
    token_version = db.Column(db.Integer, default=0)  # Increment to revoke all JWTs
    # Per-user notification preferences
    email_order_updates = db.Column(db.Boolean, default=True)
    email_messages = db.Column(db.Boolean, default=True)
    email_harvest_alerts = db.Column(db.Boolean, default=True)
    email_garden_announcements = db.Column(db.Boolean, default=True)
    # Stripe integration
    stripe_customer_id = db.Column(db.String(255))            # cus_xxx
    stripe_connect_account_id = db.Column(db.String(255))     # acct_xxx
    stripe_onboarding_complete = db.Column(db.Boolean, default=False)

    listings = db.relationship('Listing', backref='seller', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='buyer', lazy='dynamic')
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.seller_id', backref='seller', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password, method=PASSWORD_HASH_METHOD)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def needs_password_rehash(self):
        """True when the stored hash isn't on the current pinned method (e.g. a
        legacy pbkdf2 hash). The login flow re-hashes such passwords on the next
        successful sign-in so old hashes are transparently upgraded."""
        return not (self.password_hash or '').startswith(PASSWORD_HASH_METHOD + ':')

    def can_sell(self):
        return self.role in ('seller', 'both')

    def can_buy(self):
        return self.role in ('buyer', 'both')

    def is_garden_manager(self):
        return self.role == 'manager'

    def is_gardener(self):
        return self.role == 'gardener'

    @property
    def avg_rating(self):
        reviews = self.reviews_received.all()
        if not reviews:
            return None
        return round(sum(r.rating for r in reviews) / len(reviews), 1)

    @property
    def review_count(self):
        return self.reviews_received.count()


class Listing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    vegetable_type = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    base_price = db.Column(db.Float)
    initial_quantity = db.Column(db.Integer)
    price_floor = db.Column(db.Float)
    price_ceiling = db.Column(db.Float)
    smart_pricing_enabled = db.Column(db.Boolean, default=True)
    unit = db.Column(db.String(30), default='each')
    quantity_available = db.Column(db.Integer, default=1)
    image_filename = db.Column(db.String(255))
    image_filename_2 = db.Column(db.String(255))
    image_filename_3 = db.Column(db.String(255))
    image_url = db.Column(db.String(500))  # External image URL (for seed/demo data)
    pickup_address = db.Column(db.String(255))
    pickup_city = db.Column(db.String(100))
    pickup_state = db.Column(db.String(50))
    pickup_zip = db.Column(db.String(20))
    pickup_latitude = db.Column(db.Float)
    pickup_longitude = db.Column(db.Float)
    delivery_available = db.Column(db.Boolean, default=False)
    delivery_radius_miles = db.Column(db.Float, default=0)
    pickup_instructions = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    cart_items = db.relationship('CartItem', backref='listing', lazy='dynamic')
    order_items = db.relationship('OrderItem', backref='listing', lazy='dynamic')

    @property
    def effective_price(self):
        """Return dynamically calculated price for buyers."""
        from app.pricing import calculate_smart_price
        return calculate_smart_price(self)


class CartItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('buyer_id', 'listing_id'),)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    total_price = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, completed, cancelled
    fulfillment_method = db.Column(db.String(20), default='pickup')  # pickup or delivery
    notes = db.Column(db.Text)
    payment_reference = db.Column(db.String(255))  # Stripe PaymentIntent ID
    payment_status = db.Column(db.String(50))  # e.g. succeeded, pending, failed
    stripe_payment_intent_id = db.Column(db.String(255))  # pi_xxx
    # Refund tracking
    refund_status = db.Column(db.String(20))  # NULL, 'partial', 'full'
    refund_amount = db.Column(db.Float, default=0)
    # Discount tracking
    discount_amount = db.Column(db.Float, default=0)
    promo_code_id = db.Column(db.Integer, db.ForeignKey('promo_code.id'), nullable=True)
    # Financial breakdown
    subtotal = db.Column(db.Float, default=0)              # item prices before fees
    delivery_fee = db.Column(db.Float, default=0)           # delivery charge
    platform_commission = db.Column(db.Float, default=0)    # platform's cut
    commission_rate = db.Column(db.Float, default=0)         # snapshot of rate at order time
    seller_earnings = db.Column(db.Float, default=0)         # subtotal - commission
    # DoorDash integration
    doordash_delivery_id = db.Column(db.String(255))
    doordash_tracking_url = db.Column(db.String(500))
    delivery_provider = db.Column(db.String(20), default='self')  # self or doordash
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    buyer = db.relationship('User', foreign_keys=[buyer_id], backref='orders_as_buyer')
    seller_user = db.relationship('User', foreign_keys=[seller_id], backref='orders_as_seller')
    items = db.relationship('OrderItem', backref='order', lazy='dynamic')
    review = db.relationship('Review', backref='order', uselist=False)


class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float)


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    thread_id = db.Column(db.String(64), index=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'), nullable=True)
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship('User', foreign_keys=[sender_id], backref='messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='messages_received')
    listing = db.relationship('Listing', backref='messages')

    @staticmethod
    def make_thread_id(user1_id, user2_id, listing_id=None):
        a, b = sorted([user1_id, user2_id])
        return f"{a}-{b}-{listing_id or 0}"


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reviewer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), unique=True, nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class PricingConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enabled = db.Column(db.Boolean, default=True)
    global_multiplier = db.Column(db.Float, default=1.0)
    supply_weight = db.Column(db.Float, default=0.5)
    velocity_weight = db.Column(db.Float, default=0.3)
    time_decay_weight = db.Column(db.Float, default=0.2)
    floor_pct = db.Column(db.Float, default=0.70)
    ceiling_pct = db.Column(db.Float, default=2.0)
    # Platform economics — on/off switches
    commission_enabled = db.Column(db.Boolean, default=True)          # master switch: charge commission?
    delivery_fees_enabled = db.Column(db.Boolean, default=True)       # master switch: charge delivery fees?
    per_mile_enabled = db.Column(db.Boolean, default=False)           # switch: add per-mile surcharge?
    free_delivery_enabled = db.Column(db.Boolean, default=False)      # switch: enable free delivery threshold?
    # Platform economics — rate / amount values
    platform_commission_pct = db.Column(db.Float, default=0.08)       # 8% default
    delivery_fee_flat = db.Column(db.Float, default=3.99)              # flat delivery fee per seller order
    delivery_fee_per_mile = db.Column(db.Float, default=0.0)           # per-mile surcharge amount
    delivery_fee_free_threshold = db.Column(db.Float, default=0.0)     # order subtotal for free delivery
    # DoorDash Drive integration
    doordash_enabled = db.Column(db.Boolean, default=False)
    doordash_subsidy_pct = db.Column(db.Float, default=0)            # platform subsidy % on DoorDash fee
    doordash_max_subsidy = db.Column(db.Float, default=5.0)           # max $ subsidy per order
    # Garden Pro subscription pricing
    garden_pro_enabled = db.Column(db.Boolean, default=True)
    garden_pro_trial_days = db.Column(db.Integer, default=14)
    garden_pro_monthly_cents = db.Column(db.Integer, default=1500)    # $15.00
    garden_pro_yearly_cents = db.Column(db.Integer, default=12500)    # $125.00
    # Platform fee (%) skimmed from each garden DUES payment as a Stripe
    # application_fee on the destination charge to the manager. 0 = manager
    # keeps 100% of dues. Admin-editable; replaces the GARDEN_DUES_FEE_PERCENT env.
    garden_dues_fee_percent = db.Column(db.Float, default=0.0)
    # When True (default), online dues collection is REFUSED unless the garden
    # manager has completed payout onboarding, guaranteeing every charge routes
    # to their Connect account. When False, dues fall back to a platform charge
    # if the manager isn't payout-ready (collection always works, but those dues
    # land with the platform until reconciled manually).
    dues_require_payout_ready = db.Column(db.Boolean, default=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


class SubscriptionPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Float, nullable=False)
    frequency = db.Column(db.String(20), default='weekly')  # weekly, biweekly, monthly
    fulfillment_day = db.Column(db.String(10), default='saturday')
    season_start = db.Column(db.Date)
    season_end = db.Column(db.Date)
    max_subscribers = db.Column(db.Integer, default=20)
    is_active = db.Column(db.Boolean, default=True)
    photo_url = db.Column(db.String(300))
    box_size = db.Column(db.String(20), default='medium')  # small, medium, large, family
    includes_delivery = db.Column(db.Boolean, default=False)
    delivery_radius_miles = db.Column(db.Float, default=10.0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    seller = db.relationship('User', backref='subscription_plans')
    subscriptions = db.relationship('Subscription', backref='plan', lazy='dynamic')
    previews = db.relationship('BoxPreview', backref='plan', lazy='dynamic',
                               order_by='BoxPreview.week_of.desc()')


class Subscription(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='active')  # active, paused, cancelled
    dietary_notes = db.Column(db.Text)
    substitution_pref = db.Column(db.String(30), default='seller_choice')  # seller_choice, no_subs, similar_only
    delivery_preference = db.Column(db.String(20), default='pickup')  # pickup, delivery
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    paused_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    buyer = db.relationship('User', backref='subscriptions')


class BoxPreview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey('subscription_plan.id'), nullable=False)
    week_of = db.Column(db.Date, nullable=False)
    items_description = db.Column(db.Text)
    photo_url = db.Column(db.String(300))
    is_published = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class PlantingGuide(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), nullable=False)
    zone = db.Column(db.String(10), default='5b')
    seed_indoor_start_doy = db.Column(db.Integer)
    direct_sow_start_doy = db.Column(db.Integer)
    direct_sow_end_doy = db.Column(db.Integer)
    transplant_start_doy = db.Column(db.Integer)
    transplant_end_doy = db.Column(db.Integer)
    days_to_harvest_min = db.Column(db.Integer)
    days_to_harvest_max = db.Column(db.Integer)
    succession_interval_days = db.Column(db.Integer)
    frost_sensitive = db.Column(db.Boolean, default=True)
    notes = db.Column(db.Text)
    companion_plants = db.Column(db.String(300))
    avoid_near = db.Column(db.String(300))


class SellerPlanting(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    variety = db.Column(db.String(100))
    planted_date = db.Column(db.Date, nullable=False)
    estimated_harvest_start = db.Column(db.Date)
    estimated_harvest_end = db.Column(db.Date)
    quantity_estimate = db.Column(db.String(100))
    status = db.Column(db.String(20), default='planted')
    allow_preorder = db.Column(db.Boolean, default=False)
    notes = db.Column(db.Text)
    linked_listing_id = db.Column(db.Integer, db.ForeignKey('listing.id'))
    auto_list_on_harvest = db.Column(db.Boolean, default=False)
    weight_lbs = db.Column(db.Float)              # Structured weight in pounds
    sale_price = db.Column(db.Float)              # Pre-set sale price per unit
    price_unit = db.Column(db.String(20), default='lb')  # lb, each, bunch, etc.
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    seller = db.relationship('User', backref='plantings')
    linked_listing = db.relationship('Listing', backref='source_planting', foreign_keys=[linked_listing_id])


class HarvestInterest(db.Model):
    """Tracks which users want notifications when a crop category is harvested."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    notify_email = db.Column(db.Boolean, default=True)
    notify_sms = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('user_id', 'category', name='uq_harvest_interest'),)
    user = db.relationship('User', backref=db.backref('harvest_interests', lazy='dynamic'))


class NeighborhoodGroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    slug = db.Column(db.String(120), unique=True, nullable=False)
    description = db.Column(db.Text)
    neighborhood = db.Column(db.String(100))
    city = db.Column(db.String(100), default='Omaha')
    state = db.Column(db.String(2), default='NE')
    zip_code = db.Column(db.String(10))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    cover_photo_url = db.Column(db.String(300))
    is_public = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship('User', backref='created_groups')
    members = db.relationship('GroupMembership', backref='group', lazy='dynamic')
    posts = db.relationship('GroupPost', backref='group', lazy='dynamic',
                            order_by='GroupPost.created_at.desc()')


class GroupMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('neighborhood_group.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(20), default='member')  # member, moderator, admin
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='group_memberships')
    __table_args__ = (db.UniqueConstraint('group_id', 'user_id'),)


class GroupPost(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.Integer, db.ForeignKey('neighborhood_group.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_type = db.Column(db.String(20), default='update')  # update, question, photo, event, trade
    title = db.Column(db.String(200))
    content = db.Column(db.Text, nullable=False)
    photo_url = db.Column(db.String(300))
    event_date = db.Column(db.DateTime)  # for event type posts
    event_location = db.Column(db.String(200))
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='group_posts')
    comments = db.relationship('GroupPostComment', backref='post', lazy='dynamic',
                               order_by='GroupPostComment.created_at')


class GroupPostComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('group_post.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='group_comments')


# ---- Community Garden Models ----

class CommunityGarden(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, index=True)  # opaque public code, e.g. grd_7tWx4LrB2nKp
    name = db.Column(db.String(150), nullable=False)
    slug = db.Column(db.String(150), unique=True, nullable=False)
    description = db.Column(db.Text)
    address = db.Column(db.String(300))
    city = db.Column(db.String(100), default='Omaha')
    state = db.Column(db.String(2), default='NE')
    zip_code = db.Column(db.String(10))
    photo_url = db.Column(db.String(300))
    total_plots = db.Column(db.Integer, default=0)
    plot_fee_annual = db.Column(db.Float, default=0.0)
    operating_model = db.Column(db.String(20), default='allotment')  # allotment, communal, hybrid
    season_start = db.Column(db.Date)
    season_end = db.Column(db.Date)
    rules = db.Column(db.Text)
    contact_email = db.Column(db.String(150))
    is_active = db.Column(db.Boolean, default=True)
    max_checkouts_per_member = db.Column(db.Integer, default=3)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    weather_alerts_enabled = db.Column(db.Boolean, default=False)
    grid_rows = db.Column(db.Integer, default=4)
    grid_cols = db.Column(db.Integer, default=5)
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subscription_status = db.Column(db.String(20), default='none')  # none, trialing, active, expired
    # Send-once marker for the day-2 "start your free trial" nudge (gardens
    # that never started a GardenSubscription). NULL = not yet sent.
    trial_nudge_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    organizer = db.relationship('User', backref='organized_gardens')
    plots = db.relationship('GardenPlot', backref='garden', lazy='dynamic')
    resources = db.relationship('SharedResource', backref='garden', lazy='dynamic')
    events = db.relationship('GardenEvent', backref='garden', lazy='dynamic')
    harvests = db.relationship('HarvestLog', backref='garden', lazy='dynamic')


class GardenPlot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    plot_number = db.Column(db.String(20), nullable=False)
    size = db.Column(db.String(30))  # e.g. "4x8 ft", "10x10 ft"
    location_notes = db.Column(db.String(200))  # e.g. "Row B, near water spigot"
    grid_row = db.Column(db.Integer)
    grid_col = db.Column(db.Integer)
    soil_type = db.Column(db.String(30))  # clay, loam, sandy, silt, mixed
    sun_exposure = db.Column(db.String(20))  # full_sun, partial_shade, full_shade
    status = db.Column(db.String(20), default='available')  # available, assigned, reserved, maintenance
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_date = db.Column(db.Date)
    renewal_date = db.Column(db.Date)
    reserved_by_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    reserved_at = db.Column(db.DateTime)
    custom_name = db.Column(db.String(100))  # Owner-chosen name, e.g. "Sunny Corner"
    # Layout: a plot occupies a rectangle [grid_row, grid_row+grid_height) x
    # [grid_col, grid_col+grid_width) on the garden's design grid.
    grid_width = db.Column(db.Integer, default=1)
    grid_height = db.Column(db.Integer, default=1)
    rounded = db.Column(db.Boolean, default=False)  # rounded-corner rendering

    assigned_to = db.relationship('User', foreign_keys=[assigned_to_id], backref='garden_plots')
    reserved_by = db.relationship('User', foreign_keys=[reserved_by_id], backref='garden_plot_reservations')


class GardenLayoutFeature(db.Model):
    """A non-plot element on a garden's layout map — sheds, tables, paths,
    landscaping, public/common areas, water sources, compost. These are the
    "dead zones" plots can't sit on, letting organizers match real-world space."""
    __tablename__ = 'garden_layout_feature'
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'),
                          nullable=False, index=True)
    feature_type = db.Column(db.String(30), nullable=False, default='other')
    label = db.Column(db.String(60))
    grid_row = db.Column(db.Integer, nullable=False)
    grid_col = db.Column(db.Integer, nullable=False)
    grid_width = db.Column(db.Integer, default=1)
    grid_height = db.Column(db.Integer, default=1)
    color = db.Column(db.String(20))      # optional hex override; else type default
    rounded = db.Column(db.Boolean, default=False)


class GardenWaitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    plot_size_pref = db.Column(db.String(30))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='waiting')  # waiting, offered, accepted, declined
    position = db.Column(db.Integer, default=0)

    user = db.relationship('User', backref='garden_waitlist_entries')
    garden = db.relationship('CommunityGarden', backref='waitlist')


class SharedResource(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(30))  # tool, supply, infrastructure
    description = db.Column(db.Text)
    quantity = db.Column(db.Integer, default=1)
    condition = db.Column(db.String(20), default='good')  # new, good, fair, needs_repair
    checked_out_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    checked_out_at = db.Column(db.DateTime)
    checkout_duration_days = db.Column(db.Integer, default=3)
    due_date = db.Column(db.DateTime)
    qr_code_token = db.Column(db.String(64))
    # Out-of-service tools (repair/maintenance) stay in inventory but can't be
    # checked out until an admin returns them to service.
    out_of_service = db.Column(db.Boolean, default=False, nullable=False)
    service_note = db.Column(db.String(300))

    checked_out_to = db.relationship('User', backref='checked_out_resources')
    checkout_logs = db.relationship('ResourceCheckoutLog', backref='resource', lazy='dynamic')


class ResourceCheckoutLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey('shared_resource.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    checked_out_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    due_date = db.Column(db.DateTime)
    returned_at = db.Column(db.DateTime)
    duration_days = db.Column(db.Integer, default=3)
    condition_at_checkout = db.Column(db.String(20))
    condition_at_return = db.Column(db.String(20))

    user = db.relationship('User', backref='resource_checkouts')


class GardenEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(30))  # workday, workshop, social, meeting, harvest_day
    event_date = db.Column(db.DateTime, nullable=False)
    duration_hours = db.Column(db.Float, default=2.0)
    max_volunteers = db.Column(db.Integer)
    # Recurrence for repeating volunteer opportunities. 'none' is a one-off;
    # weekly/biweekly/monthly events are expanded into a series of GardenEvent
    # rows at creation time (each row stores the same recurring value).
    recurring = db.Column(db.String(20), default='none')  # none, weekly, biweekly, monthly
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship('User', backref='created_garden_events')
    rsvps = db.relationship('EventRSVP', backref='event', lazy='dynamic')


class EventRSVP(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey('garden_event.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='going')  # going, maybe, not_going
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='event_rsvps')
    __table_args__ = (db.UniqueConstraint('event_id', 'user_id'),)


class HarvestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    category = db.Column(db.String(50))
    variety = db.Column(db.String(100))
    quantity_lbs = db.Column(db.Float)
    harvest_date = db.Column(db.Date, nullable=False)
    destination = db.Column(db.String(30), default='personal')  # personal, shared, food_bank, marketplace
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='harvest_logs')


# ---- Garden Admin Models ----

class GardenAnnouncement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default='normal')  # normal, important, urgent
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='garden_announcements')
    garden = db.relationship('CommunityGarden', backref='announcements')


class GardenComment(db.Model):
    """Public comment wall on a garden's page. New comments pass through the AI
    moderator (see app/moderation_service.py): 'allow' and 'flag' both post,
    'block' is rejected. Flagged comments set status='flagged' so a garden
    admin is alerted to review them; everything visible has status in
    ('approved','flagged')."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='approved')  # approved, flagged
    moderation_reason = db.Column(db.String(300))  # AI note when flagged
    parent_id = db.Column(db.Integer, db.ForeignKey('garden_comment.id'),
                          nullable=True)  # set on replies (one-level threading)
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    author = db.relationship('User', backref='garden_comments')
    garden = db.relationship('CommunityGarden',
                             backref=db.backref('comments', lazy='dynamic'))


class GardenCommentLike(db.Model):
    """A like on a community-wall comment — one per user per comment."""
    __tablename__ = 'garden_comment_like'
    id = db.Column(db.Integer, primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('garden_comment.id'),
                           nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        db.UniqueConstraint('comment_id', 'user_id', name='uq_garden_comment_like'),
    )


class EmailUnsubscribe(db.Model):
    """Global email suppression list. An address here is excluded from all bulk
    sends (garden announcements, CRM campaigns). Populated by the List-Unsubscribe
    self-service page. Transactional mail (resets, receipts) is never suppressed."""
    __tablename__ = 'email_unsubscribe'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    source = db.Column(db.String(40))  # e.g. 'self_service', 'admin'
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class GardenMessage(db.Model):
    """Direct messages between garden admin and plot owners."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    sender = db.relationship('User', foreign_keys=[sender_id], backref='garden_messages_sent')
    recipient = db.relationship('User', foreign_keys=[recipient_id], backref='garden_messages_received')
    garden = db.relationship('CommunityGarden', backref='admin_messages')


class GardenPhoto(db.Model):
    """Social media lite - photo sharing wall for garden members."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    photo_url = db.Column(db.String(300), nullable=False)
    caption = db.Column(db.String(500))
    category = db.Column(db.String(30), default='general')  # general, harvest, plot, event, wildlife, bloom
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='garden_photos')
    garden = db.relationship('CommunityGarden', backref='photos')
    comments = db.relationship('GardenPhotoComment', backref='photo', lazy='dynamic',
                               order_by='GardenPhotoComment.created_at')


class GardenPhotoComment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('garden_photo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='garden_photo_comments')


class GardenPhotoLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('garden_photo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    __table_args__ = (db.UniqueConstraint('photo_id', 'user_id'),)


# ---- Volunteer Shift Scheduling ----

class VolunteerShift(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    shift_date = db.Column(db.Date, nullable=False)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    max_volunteers = db.Column(db.Integer)
    recurring = db.Column(db.String(20), default='none')  # none, weekly, biweekly, monthly
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    garden = db.relationship('CommunityGarden', backref='shifts')
    created_by = db.relationship('User', backref='created_shifts')
    signups = db.relationship('ShiftSignup', backref='shift', lazy='dynamic',
                              cascade='all, delete-orphan')


class ShiftSignup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    shift_id = db.Column(db.Integer, db.ForeignKey('volunteer_shift.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='signed_up')  # signed_up, attended, no_show
    hours_logged = db.Column(db.Float)
    checked_in_at = db.Column(db.DateTime)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='shift_signups')

    __table_args__ = (db.UniqueConstraint('shift_id', 'user_id'),)


# ---- Garden Dues & Finance ----

class GardenDuesRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    season_year = db.Column(db.Integer, nullable=False)
    amount_due = db.Column(db.Float, nullable=False)
    amount_paid = db.Column(db.Float, default=0)
    status = db.Column(db.String(20), default='unpaid')  # unpaid, partial, paid, waived, comp
    payment_method = db.Column(db.String(30))  # cash, check, venmo, online, waived
    payment_date = db.Column(db.Date)
    payment_note = db.Column(db.Text)
    # Stripe PaymentIntent that paid these dues (online payments). Dedicated
    # column (not just payment_note) so webhook fulfillment can reconcile.
    stripe_payment_intent_id = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='garden_dues')
    garden = db.relationship('CommunityGarden', backref='dues_records')

    __table_args__ = (db.UniqueConstraint('garden_id', 'user_id', 'season_year'),)


class GardenExpense(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(50))  # supplies, infrastructure, water, seeds, tools, other
    expense_date = db.Column(db.Date, nullable=False)
    paid_by = db.Column(db.String(100))
    receipt_url = db.Column(db.String(300))
    notes = db.Column(db.Text)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship('User', backref='garden_expenses_created')
    garden = db.relationship('CommunityGarden', backref='expenses')


# ---- Weather Alerts ----

class GardenWeatherAlert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    alert_type = db.Column(db.String(30))  # frost, heat, storm, rain, drought
    message = db.Column(db.Text, nullable=False)
    severity = db.Column(db.String(20), default='info')  # info, warning, critical
    active_from = db.Column(db.DateTime)
    active_until = db.Column(db.DateTime)
    auto_generated = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    garden = db.relationship('CommunityGarden', backref='weather_alerts')


# ---- Plot Assignment History ----

class PlotAssignmentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plot_id = db.Column(db.Integer, db.ForeignKey('garden_plot.id'), nullable=False)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    season_year = db.Column(db.Integer, nullable=False)
    assigned_date = db.Column(db.Date)
    released_date = db.Column(db.Date)
    notes = db.Column(db.Text)

    user = db.relationship('User', backref='plot_history')
    plot = db.relationship('GardenPlot', backref='assignment_history')


# ---- Garden Membership Roles ----

class GardenMembership(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    role = db.Column(db.String(30), default='member')  # organizer, co_organizer, treasurer, volunteer_lead, member
    joined_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='garden_memberships')
    garden = db.relationship('CommunityGarden', backref='memberships')

    __table_args__ = (db.UniqueConstraint('garden_id', 'user_id'),)


# ---- Knowledge Base ----

class GardenKnowledgeArticle(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'))  # NULL = platform-wide
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50))  # planting, composting, pests, watering, soil, tools, seasonal, general
    pinned = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime)

    author = db.relationship('User', backref='knowledge_articles')
    garden = db.relationship('CommunityGarden', backref='knowledge_articles')


# ---- Seller Payout Tracking ----

class SellerPayout(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, processing, completed, failed
    period_start = db.Column(db.Date)
    period_end = db.Column(db.Date)
    order_ids = db.Column(db.Text)  # JSON list of order IDs included
    payout_reference = db.Column(db.String(255))  # external payment reference
    stripe_transfer_id = db.Column(db.String(255))  # tr_xxx
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

    seller = db.relationship('User', backref='payouts')


# ---- Email Configuration ----

class SiteEmailConfig(db.Model):
    """Singleton config for site-wide email branding and notification toggles."""
    id = db.Column(db.Integer, primary_key=True)
    # Branding
    logo_url = db.Column(db.String(500), default='')
    header_color = db.Column(db.String(7), default='#22242a')  # ink (redesign)
    tagline = db.Column(db.String(200), default='Less admin, more garden')
    footer_text = db.Column(db.Text, default='')
    from_name = db.Column(db.String(100), default='YardHarvest')
    subject_prefix = db.Column(db.String(50), default='YardHarvest')
    # Notification toggles
    enable_order_confirmation = db.Column(db.Boolean, default=True)
    enable_status_updates = db.Column(db.Boolean, default=True)
    enable_messages = db.Column(db.Boolean, default=True)
    enable_announcements = db.Column(db.Boolean, default=True)
    enable_subscription_boxes = db.Column(db.Boolean, default=True)
    # SMS notification toggles
    enable_sms_order_confirmation = db.Column(db.Boolean, default=False)
    enable_sms_status_updates = db.Column(db.Boolean, default=False)
    enable_sms_messages = db.Column(db.Boolean, default=False)
    # Harvest notification toggles
    enable_harvest_notifications = db.Column(db.Boolean, default=True)
    enable_sms_harvest_notifications = db.Column(db.Boolean, default=False)
    # Feature toggles
    marketplace_enabled = db.Column(db.Boolean, default=False)
    # Analytics & tracking
    analytics_enabled = db.Column(db.Boolean, default=True)
    cookie_consent_required = db.Column(db.Boolean, default=True)
    analytics_retention_days = db.Column(db.Integer, default=90)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))


class GardenEmailConfig(db.Model):
    """Per-garden email customization for announcements."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), unique=True, nullable=False)
    sender_name = db.Column(db.String(100), default='')
    subject_prefix = db.Column(db.String(50), default='')
    closing_text = db.Column(db.String(300), default='')
    accent_color = db.Column(db.String(7), default='#2d6a2e')
    sms_enabled = db.Column(db.Boolean, default=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    garden = db.relationship('CommunityGarden', backref=db.backref('email_config', uselist=False))


# ---- In-App Notification System ----

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # plot_reserved, plot_confirmed, plot_declined, shift_reminder, dues_reminder, announcement, message, waitlist_update
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text)
    link = db.Column(db.String(300))  # frontend route to navigate to
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref=db.backref('notifications', lazy='dynamic', order_by='Notification.created_at.desc()'))
    garden = db.relationship('CommunityGarden', backref='notifications')


# ---- Photo Database ----

class Photo(db.Model):
    __tablename__ = 'photo'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=True)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    file_size = db.Column(db.Integer)  # bytes
    width = db.Column(db.Integer)
    height = db.Column(db.Integer)
    category = db.Column(db.String(50), default='general')  # general, garden, harvest, event, plot
    caption = db.Column(db.Text)
    likes_count = db.Column(db.Integer, default=0)
    uploaded_at = db.Column(db.DateTime, default=db.func.now())

    user = db.relationship('User', backref='photos')
    comments = db.relationship('PhotoComment', backref='photo', lazy='dynamic',
                               order_by='PhotoComment.created_at',
                               cascade='all, delete-orphan')
    likes = db.relationship('PhotoLike', backref='photo', lazy='dynamic',
                            cascade='all, delete-orphan')


class PhotoLike(db.Model):
    """An upvote on a garden photo — one per user per photo."""
    __tablename__ = 'photo_like'
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    __table_args__ = (
        db.UniqueConstraint('photo_id', 'user_id', name='uq_photo_like'),
    )


class PhotoComment(db.Model):
    """A comment on a garden photo."""
    __tablename__ = 'photo_comment'
    id = db.Column(db.Integer, primary_key=True)
    photo_id = db.Column(db.Integer, db.ForeignKey('photo.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='photo_comments')


class GardenSubscription(db.Model):
    """Tracks Garden Pro subscription status for community gardens."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), unique=True, nullable=False)
    billing_cycle = db.Column(db.String(10), default='monthly')  # monthly, yearly
    status = db.Column(db.String(20), default='trialing')  # trialing, active, past_due, cancelled, expired
    trial_start = db.Column(db.DateTime)
    trial_end = db.Column(db.DateTime)
    # Highest trial-drip day (3/7/12/14/21) already emailed. Lets the daily
    # lifecycle job catch up after a missed heartbeat instead of matching exact
    # day numbers (which skipped an email forever). NULL = nothing sent yet.
    last_drip_day = db.Column(db.Integer)
    current_period_start = db.Column(db.DateTime)
    current_period_end = db.Column(db.DateTime)
    cancel_at_period_end = db.Column(db.Boolean, default=False)
    # True when Pro was granted by a YardHarvest platform admin (not a paid
    # Stripe subscription). Such grants have no real billing period, so the
    # billing page suppresses the "cancellation scheduled" banner for them.
    admin_granted = db.Column(db.Boolean, default=False)
    payment_reference = db.Column(db.String(255))
    stripe_subscription_id = db.Column(db.String(255))  # sub_xxx
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    garden = db.relationship('CommunityGarden', backref=db.backref('subscription', uselist=False))


class GardenLayoutDraft(db.Model):
    """Saved draft layouts for garden redesign planning."""
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    grid_rows = db.Column(db.Integer, default=4)
    grid_cols = db.Column(db.Integer, default=5)
    layout_data = db.Column(db.Text, default='{}')  # JSON: {placements, annotations}
    notes = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, onupdate=lambda: datetime.now(timezone.utc))

    garden = db.relationship('CommunityGarden', backref='layout_drafts')


# ---- Refunds ----

class Refund(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    garden_subscription_id = db.Column(db.Integer, db.ForeignKey('garden_subscription.id'), nullable=True)
    refund_type = db.Column(db.String(20), nullable=False)  # marketplace, garden_pro
    amount = db.Column(db.Float, nullable=False)
    reason = db.Column(db.Text)
    status = db.Column(db.String(20), default='pending')  # pending, completed, failed
    stripe_refund_id = db.Column(db.String(255))  # re_xxx
    stripe_reversal_id = db.Column(db.String(255))  # trr_xxx
    initiated_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    completed_at = db.Column(db.DateTime)

    order = db.relationship('Order', backref='refunds')
    garden_subscription = db.relationship('GardenSubscription', backref='refunds')
    initiated_by = db.relationship('User', backref='refunds_initiated')


# ---- Promo Codes ----

class PromoCode(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    discount_type = db.Column(db.String(20), nullable=False)  # percentage, fixed
    discount_value = db.Column(db.Float, nullable=False)  # percentage 0-100 or dollar amount
    scope = db.Column(db.String(20), default='both')  # marketplace, garden_pro, both
    max_uses = db.Column(db.Integer)  # NULL = unlimited
    current_uses = db.Column(db.Integer, default=0)
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    created_by = db.relationship('User', backref='promo_codes_created')
    usages = db.relationship('PromoCodeUsage', backref='promo_code', lazy='dynamic')


class PromoCodeUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    promo_code_id = db.Column(db.Integer, db.ForeignKey('promo_code.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=True)
    garden_subscription_id = db.Column(db.Integer, db.ForeignKey('garden_subscription.id'), nullable=True)
    discount_applied = db.Column(db.Float, nullable=False)
    used_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    user = db.relationship('User', backref='promo_code_usages')
    order = db.relationship('Order', backref='promo_usage')
    garden_sub = db.relationship('GardenSubscription', backref='promo_usage')


# ---- Analytics & Tracking ----

class AnalyticsEvent(db.Model):
    """First-party analytics event. Privacy-first — only recorded with consent."""
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False, index=True)
    page_url = db.Column(db.String(500))
    referrer = db.Column(db.String(500))
    metadata_json = db.Column(db.Text)  # JSON blob for event-specific data
    device_type = db.Column(db.String(20))  # mobile, tablet, desktop
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    __table_args__ = (
        db.Index('ix_analytics_type_created', 'event_type', 'created_at'),
    )


class PendingCheckout(db.Model):
    """Snapshot of a marketplace checkout, captured when its PaymentIntent is
    created.

    Fulfillment (creating Orders, decrementing stock, paying sellers) runs from
    this exact snapshot — driven by either the Stripe webhook
    (payment_intent.succeeded, the guarantee) or the client /confirm call (the
    instant path) — so a successful charge can never fail to produce orders.
    Idempotent via the per-PaymentIntent Order guard plus ``fulfilled``.
    """
    id = db.Column(db.Integer, primary_key=True)
    payment_intent_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    payload_json = db.Column(db.Text, nullable=False)  # basket + fulfillment + promo
    fulfilled = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


class ProcessedStripeEvent(db.Model):
    """Idempotency ledger for Stripe webhook events.

    Stripe delivers each event at least once and retries for up to 72h, so the
    same event.id can arrive multiple times. We record every processed id with
    a UNIQUE constraint and short-circuit on repeats to prevent double
    fulfillment (duplicate orders, transfers, emails).
    """
    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False, index=True)
    event_type = db.Column(db.String(80))
    processed_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Booking — a Calendly-style scheduling page for the site owner ("/book").
# Visitors pick a meeting type + an open slot; we save the booking, sync it to
# the owner's Zoho calendar, and (optionally) create a CRM lead. Single-host:
# one owner (you), with configurable meeting types + a weekly availability grid.
# All datetimes are stored naive-UTC (see booking_service for tz handling).
# ---------------------------------------------------------------------------
class BookingSettings(db.Model):
    """Global config for the booking page — a singleton row (id=1)."""
    __tablename__ = 'booking_settings'

    id = db.Column(db.Integer, primary_key=True)
    # The owner's home timezone — availability windows are defined in this tz.
    timezone = db.Column(db.String(64), default='America/Chicago', nullable=False)
    owner_name = db.Column(db.String(120), default='James Goodman')
    # Public page copy
    heading = db.Column(db.String(160), default='Book time with me')
    intro = db.Column(db.Text, default='Pick a meeting type and a time that works for you.')
    # Scheduling guardrails
    min_notice_hours = db.Column(db.Integer, default=12, nullable=False)
    max_advance_days = db.Column(db.Integer, default=30, nullable=False)
    slot_granularity_min = db.Column(db.Integer, default=30, nullable=False)
    max_per_day = db.Column(db.Integer, default=0, nullable=False)   # 0 = unlimited
    # Read the owner's real Zoho calendar to hide already-busy times.
    block_zoho_busy = db.Column(db.Boolean, default=True, nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def get(cls):
        """Return the singleton, creating it with column defaults on first use."""
        s = db.session.get(cls, 1)
        if s is None:
            s = cls(id=1)
            db.session.add(s)
            db.session.commit()
        return s

    def to_dict(self):
        return {
            'timezone': self.timezone, 'owner_name': self.owner_name or '',
            'heading': self.heading or '', 'intro': self.intro or '',
            'min_notice_hours': self.min_notice_hours,
            'max_advance_days': self.max_advance_days,
            'slot_granularity_min': self.slot_granularity_min,
            'max_per_day': self.max_per_day,
            'block_zoho_busy': bool(self.block_zoho_busy),
        }


class BookingType(db.Model):
    """A configurable meeting type (e.g. "Intro Call — 30 min")."""
    __tablename__ = 'booking_type'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, index=True)   # bkt_...
    slug = db.Column(db.String(80), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text)
    duration_min = db.Column(db.Integer, default=30, nullable=False)
    location = db.Column(db.String(255))   # "Phone call", a video link, an address…
    buffer_before_min = db.Column(db.Integer, default=0, nullable=False)
    buffer_after_min = db.Column(db.Integer, default=0, nullable=False)
    color = db.Column(db.String(7), default='#5b8c3e')   # hex UI accent
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    sort_order = db.Column(db.Integer, default=0, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    bookings = db.relationship('Booking', backref='booking_type', lazy='dynamic')

    def to_public_dict(self):
        return {
            'slug': self.slug, 'name': self.name,
            'description': self.description or '',
            'duration_min': self.duration_min,
            'location': self.location or '',
            'color': self.color or '#5b8c3e',
        }

    def to_admin_dict(self):
        d = self.to_public_dict()
        d.update({
            'id': self.id, 'public_id': self.public_id,
            'buffer_before_min': self.buffer_before_min,
            'buffer_after_min': self.buffer_after_min,
            'is_active': bool(self.is_active), 'sort_order': self.sort_order,
        })
        return d


class AvailabilityRule(db.Model):
    """A weekly recurring availability window, in the owner's timezone.

    ``day_of_week`` uses Python's ``date.weekday()`` convention: Monday=0 …
    Sunday=6. ``start_min``/``end_min`` are minutes from midnight (e.g. 540 =
    09:00, 1020 = 17:00). Rules apply to all active meeting types.
    """
    __tablename__ = 'booking_availability'

    id = db.Column(db.Integer, primary_key=True)
    day_of_week = db.Column(db.Integer, nullable=False)   # 0=Mon … 6=Sun
    start_min = db.Column(db.Integer, nullable=False)
    end_min = db.Column(db.Integer, nullable=False)

    def to_dict(self):
        return {'id': self.id, 'day_of_week': self.day_of_week,
                'start_min': self.start_min, 'end_min': self.end_min}


class Booking(db.Model):
    """A single confirmed appointment. ``public_id`` doubles as the unguessable
    token for the visitor's manage/cancel link."""
    __tablename__ = 'booking'

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(32), unique=True, index=True)   # bkg_…
    booking_type_id = db.Column(db.Integer, db.ForeignKey('booking_type.id'), nullable=False)
    start_at = db.Column(db.DateTime, nullable=False, index=True)    # naive UTC
    end_at = db.Column(db.DateTime, nullable=False)                  # naive UTC
    invitee_timezone = db.Column(db.String(64))                      # booker's tz (display)
    invitee_name = db.Column(db.String(120), nullable=False)
    invitee_email = db.Column(db.String(120), nullable=False, index=True)
    invitee_phone = db.Column(db.String(30))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='confirmed', nullable=False, index=True)  # confirmed | cancelled
    # ---- Zoho calendar sync ----
    zoho_event_uid = db.Column(db.String(255))
    zoho_sync_status = db.Column(db.String(20), default='pending')   # pending|synced|failed|skipped
    zoho_sync_error = db.Column(db.String(255))
    # ---- CRM tie-in (soft link to crm_contact.id; no cross-module FK) ----
    crm_contact_id = db.Column(db.Integer)
    # Stamped when the daily cron sends the 24h meeting reminder (send-once).
    reminder_sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    cancelled_at = db.Column(db.DateTime)

    def to_dict(self):
        bt = self.booking_type
        return {
            'public_id': self.public_id,
            'status': self.status,
            'start_at': (self.start_at.replace(tzinfo=timezone.utc).isoformat()
                         if self.start_at else None),
            'end_at': (self.end_at.replace(tzinfo=timezone.utc).isoformat()
                       if self.end_at else None),
            'invitee_timezone': self.invitee_timezone,
            'invitee_name': self.invitee_name,
            'invitee_email': self.invitee_email,
            'invitee_phone': self.invitee_phone or '',
            'notes': self.notes or '',
            'type_name': bt.name if bt else None,
            'type_slug': bt.slug if bt else None,
            'duration_min': bt.duration_min if bt else None,
            'location': (bt.location or '') if bt else '',
            'zoho_sync_status': self.zoho_sync_status,
        }


# ---------------------------------------------------------------------------
# Auto-assign an opaque, prefixed public_id to new users and gardens on insert.
# ---------------------------------------------------------------------------
@event.listens_for(User, 'before_insert')
def _user_before_insert(mapper, connection, target):
    _assign_public_id(connection, User.__table__, target, 'usr')


@event.listens_for(CommunityGarden, 'before_insert')
def _garden_before_insert(mapper, connection, target):
    _assign_public_id(connection, CommunityGarden.__table__, target, 'grd')


@event.listens_for(BookingType, 'before_insert')
def _booking_type_before_insert(mapper, connection, target):
    _assign_public_id(connection, BookingType.__table__, target, 'bkt')


@event.listens_for(Booking, 'before_insert')
def _booking_before_insert(mapper, connection, target):
    _assign_public_id(connection, Booking.__table__, target, 'bkg')
