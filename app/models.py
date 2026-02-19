from app import db, login_manager
from flask_login import UserMixin
from datetime import datetime, timezone
from werkzeug.security import generate_password_hash, check_password_hash


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(10), default='buyer')  # buyer, seller, both
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

    listings = db.relationship('Listing', backref='seller', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='buyer', lazy='dynamic')
    reviews_given = db.relationship('Review', foreign_keys='Review.reviewer_id', backref='reviewer', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.seller_id', backref='seller', lazy='dynamic')

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def can_sell(self):
        return self.role in ('seller', 'both')

    def can_buy(self):
        return self.role in ('buyer', 'both')

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
    payment_reference = db.Column(db.String(255))  # Gr4vy transaction ID
    payment_status = db.Column(db.String(50))  # e.g. completed, pending, failed
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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    seller = db.relationship('User', backref='plantings')


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
    organizer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
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
    status = db.Column(db.String(20), default='available')  # available, assigned, reserved, maintenance
    assigned_to_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    assigned_date = db.Column(db.Date)
    renewal_date = db.Column(db.Date)

    assigned_to = db.relationship('User', backref='garden_plots')


class GardenWaitlist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    requested_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    plot_size_pref = db.Column(db.String(30))
    notes = db.Column(db.Text)
    status = db.Column(db.String(20), default='waiting')  # waiting, offered, accepted, declined

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

    checked_out_to = db.relationship('User', backref='checked_out_resources')


class GardenEvent(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    garden_id = db.Column(db.Integer, db.ForeignKey('community_garden.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    event_type = db.Column(db.String(30))  # workday, workshop, social, meeting, harvest_day
    event_date = db.Column(db.DateTime, nullable=False)
    duration_hours = db.Column(db.Float, default=2.0)
    max_volunteers = db.Column(db.Integer)
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
