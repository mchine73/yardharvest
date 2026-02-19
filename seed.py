"""Populate the database with sample data for demonstration."""
from app import create_app, db
from app.models import (
    User, Listing, Order, OrderItem, Message, Review, PricingConfig,
    NeighborhoodGroup, GroupMembership, GroupPost, GroupPostComment,
    CommunityGarden, GardenPlot, GardenWaitlist, SharedResource,
    GardenEvent, EventRSVP, HarvestLog,
)
from datetime import datetime, timezone, timedelta
import random
import os

# Sample data - uses real coordinates around Omaha, NE area
SELLERS = [
    {
        'username': 'green_thumb_maria',
        'email': 'maria@example.com',
        'display_name': 'Maria Garcia',
        'bio': 'Been gardening for 15 years! Specializing in heirloom tomatoes and peppers. Everything is grown organically in my backyard.',
        'gardening_story': 'I started gardening 15 years ago when my grandmother gave me some heirloom tomato seeds from Mexico. What began as a small pot on my porch has grown into a 2000 sq ft garden that feeds my family and neighbors. Gardening connects me to my roots and I love sharing that with my community.',
        'years_gardening': 15,
        'city': 'Omaha', 'state': 'NE', 'zip_code': '68106',
        'latitude': 41.2461, 'longitude': -95.9669,
    },
    {
        'username': 'backyard_bob',
        'email': 'bob@example.com',
        'display_name': 'Bob Thompson',
        'bio': 'Retired teacher turned full-time gardener. I grow way more than my family can eat!',
        'gardening_story': 'After retiring from teaching, I needed something to keep me busy. My backyard garden exploded! I grow way more than my wife and I can eat, so selling the surplus is a great way to reduce waste and meet my neighbors.',
        'years_gardening': 8,
        'city': 'Bellevue', 'state': 'NE', 'zip_code': '68005',
        'latitude': 41.1544, 'longitude': -95.9146,
    },
    {
        'username': 'sunny_sarah',
        'email': 'sarah@example.com',
        'display_name': 'Sarah Chen',
        'bio': 'Urban farmer on a quarter acre. Asian vegetables, herbs, and lots of greens.',
        'gardening_story': 'I grew up on a small farm in Taiwan and missed having access to fresh Asian vegetables. Now I grow bok choy, Thai basil, long beans, and lemongrass right here in Nebraska. My garden is my happy place.',
        'years_gardening': 12,
        'city': 'Papillion', 'state': 'NE', 'zip_code': '68046',
        'latitude': 41.1544, 'longitude': -96.0422,
    },
    {
        'username': 'organic_oscar',
        'email': 'oscar@example.com',
        'display_name': 'Oscar Williams',
        'bio': 'Permaculture enthusiast. Everything in my garden works together naturally. Also keep bees!',
        'gardening_story': 'Permaculture changed my life. My garden is a complete ecosystem - fruit trees, vegetables, herbs, and honeybees all working together. I am passionate about sustainable food production.',
        'years_gardening': 20,
        'city': 'La Vista', 'state': 'NE', 'zip_code': '68128',
        'latitude': 41.1839, 'longitude': -96.0311,
    },
    {
        'username': 'garden_grace',
        'email': 'grace@example.com',
        'display_name': 'Grace Johnson',
        'bio': 'Growing food for my community. Specializing in root vegetables and squash.',
        'gardening_story': 'I started a community garden plot and it grew from there! Now my entire backyard is a productive food forest. I specialize in root vegetables because there is something magical about pulling food out of the ground.',
        'years_gardening': 6,
        'city': 'Ralston', 'state': 'NE', 'zip_code': '68127',
        'latitude': 41.2011, 'longitude': -96.0403,
    },
]

BUYERS = [
    {
        'username': 'foodie_frank',
        'email': 'frank@example.com',
        'display_name': 'Frank Miller',
        'city': 'Omaha', 'state': 'NE', 'zip_code': '68102',
        'latitude': 41.2565, 'longitude': -95.9345,
    },
    {
        'username': 'chef_diana',
        'email': 'diana@example.com',
        'display_name': 'Diana Park',
        'city': 'Omaha', 'state': 'NE', 'zip_code': '68132',
        'latitude': 41.2627, 'longitude': -95.9783,
    },
]

LISTINGS_DATA = [
    # Maria's listings
    ('green_thumb_maria', [
        {'title': 'Heirloom Cherokee Purple Tomatoes', 'description': 'Beautiful, deep purple heirloom tomatoes. Incredible flavor, perfect for sandwiches and salads. Picked fresh this morning.', 'vegetable_type': 'tomatoes', 'price': 4.50, 'unit': 'per lb', 'quantity': 12, 'delivery': True, 'radius': 5, 'image': 'seed_tomatoes.jpg'},
        {'title': 'Sweet Bell Peppers - Mixed Colors', 'description': 'Red, yellow, and orange bell peppers. Crispy and sweet. Great for stir fry or eating raw.', 'vegetable_type': 'peppers', 'price': 3.00, 'unit': 'each', 'quantity': 20, 'delivery': True, 'radius': 5, 'image': 'seed_peppers.jpg'},
        {'title': 'Fresh Basil Bunches', 'description': 'Fragrant Genovese basil. Perfect for pesto, caprese, or any Italian dish.', 'vegetable_type': 'herbs', 'price': 2.50, 'unit': 'per bunch', 'quantity': 8, 'delivery': False, 'radius': 0, 'image': 'seed_basil.jpg'},
        {'title': 'Jalapeno Peppers', 'description': 'Medium heat jalapenos. Great for salsa, poppers, or pickling.', 'vegetable_type': 'peppers', 'price': 2.00, 'unit': 'per lb', 'quantity': 15, 'delivery': True, 'radius': 5, 'image': 'seed_jalapeno.jpg'},
    ]),
    # Bob's listings
    ('backyard_bob', [
        {'title': 'Giant Zucchini', 'description': 'They just keep coming! Beautiful green zucchini, perfect for grilling, baking, or spiralizing.', 'vegetable_type': 'squash', 'price': 1.50, 'unit': 'each', 'quantity': 25, 'delivery': False, 'radius': 0, 'image': 'seed_zucchini.jpg'},
        {'title': 'Sweet Corn - Just Picked!', 'description': 'Nothing beats fresh sweet corn. Picked this morning, still has the silk on. Boil, grill, or roast.', 'vegetable_type': 'corn', 'price': 6.00, 'unit': 'per dozen', 'quantity': 8, 'delivery': True, 'radius': 10, 'image': 'seed_corn.jpg'},
        {'title': 'Roma Tomatoes for Sauce', 'description': 'Meaty Roma tomatoes, low moisture - perfect for making your own pasta sauce or salsa.', 'vegetable_type': 'tomatoes', 'price': 3.50, 'unit': 'per lb', 'quantity': 20, 'delivery': True, 'radius': 10, 'image': 'seed_roma.jpg'},
    ]),
    # Sarah's listings
    ('sunny_sarah', [
        {'title': 'Baby Bok Choy', 'description': 'Tender baby bok choy, perfect for stir fry or soup. Grown without pesticides.', 'vegetable_type': 'greens', 'price': 3.00, 'unit': 'per bunch', 'quantity': 10, 'delivery': True, 'radius': 8, 'image': 'seed_bokchoy.jpg'},
        {'title': 'Thai Basil', 'description': 'Authentic Thai basil with that distinctive anise flavor. Essential for Thai and Vietnamese cooking.', 'vegetable_type': 'herbs', 'price': 2.00, 'unit': 'per bunch', 'quantity': 12, 'delivery': True, 'radius': 8, 'image': 'seed_thaibasil.jpg'},
        {'title': 'Chinese Long Beans', 'description': 'Also called yard-long beans. Tender and delicious stir-fried with garlic.', 'vegetable_type': 'beans', 'price': 4.00, 'unit': 'per lb', 'quantity': 8, 'delivery': False, 'radius': 0, 'image': 'seed_longbeans.jpg'},
        {'title': 'Fresh Lemongrass Stalks', 'description': 'Fragrant lemongrass, freshly cut. Makes amazing tea, soup, or curry paste.', 'vegetable_type': 'herbs', 'price': 1.50, 'unit': 'per bunch', 'quantity': 15, 'delivery': True, 'radius': 8, 'image': 'seed_lemongrass.jpg'},
    ]),
    # Oscar's listings
    ('organic_oscar', [
        {'title': 'Raw Wildflower Honey', 'description': 'From my own backyard beehives. Unfiltered, unpasteurized, pure Nebraska wildflower honey.', 'vegetable_type': 'honey', 'price': 12.00, 'unit': 'each', 'quantity': 6, 'delivery': True, 'radius': 15, 'image': 'seed_honey.jpg'},
        {'title': 'Mixed Salad Greens', 'description': 'A beautiful mix of lettuce, arugula, mizuna, and spinach. Washed and ready to eat.', 'vegetable_type': 'greens', 'price': 5.00, 'unit': 'per bag', 'quantity': 10, 'delivery': True, 'radius': 15, 'image': 'seed_greens.jpg'},
        {'title': 'Fresh Eggs - Free Range', 'description': 'From my happy backyard chickens. Brown and blue eggs, rich orange yolks.', 'vegetable_type': 'eggs', 'price': 6.00, 'unit': 'per dozen', 'quantity': 4, 'delivery': False, 'radius': 0, 'image': 'seed_eggs.jpg'},
    ]),
    # Grace's listings
    ('garden_grace', [
        {'title': 'Butternut Squash', 'description': 'Sweet, nutty butternut squash. Perfect for roasting, soup, or ravioli filling.', 'vegetable_type': 'squash', 'price': 3.00, 'unit': 'each', 'quantity': 15, 'delivery': True, 'radius': 7, 'image': 'seed_butternut.jpg'},
        {'title': 'Rainbow Carrots', 'description': 'Purple, orange, yellow, and white carrots. Beautiful and delicious. Kids love them!', 'vegetable_type': 'root_vegetables', 'price': 4.00, 'unit': 'per bunch', 'quantity': 10, 'delivery': True, 'radius': 7, 'image': 'seed_carrots.jpg'},
        {'title': 'Golden Beets', 'description': 'Sweet golden beets that won\'t stain your hands! Great roasted or in salads.', 'vegetable_type': 'root_vegetables', 'price': 3.50, 'unit': 'per bunch', 'quantity': 8, 'delivery': False, 'radius': 0, 'image': 'seed_beets.jpg'},
        {'title': 'Sugar Pie Pumpkins', 'description': 'Small sweet pumpkins perfect for homemade pumpkin pie. Way better than canned!', 'vegetable_type': 'squash', 'price': 4.00, 'unit': 'each', 'quantity': 12, 'delivery': True, 'radius': 7, 'image': 'seed_pumpkins.jpg'},
    ]),
]


def seed():
    print("Seeding database...")

    # Clear existing data
    HarvestLog.query.delete()
    EventRSVP.query.delete()
    GardenEvent.query.delete()
    SharedResource.query.delete()
    GardenWaitlist.query.delete()
    GardenPlot.query.delete()
    CommunityGarden.query.delete()
    GroupPostComment.query.delete()
    GroupPost.query.delete()
    GroupMembership.query.delete()
    NeighborhoodGroup.query.delete()
    PricingConfig.query.delete()
    Review.query.delete()
    Message.query.delete()
    OrderItem.query.delete()
    Order.query.delete()
    Listing.query.delete()
    User.query.delete()
    db.session.commit()

    users = {}

    # Create admin user
    admin = User(
        username='admin',
        email='admin@yardharvest.com',
        role='both',
        display_name='YardHarvest Admin',
        bio='Site administrator',
        is_admin=True,
        city='Omaha',
        state='NE',
        zip_code='68102',
    )
    admin.set_password('admin123')
    db.session.add(admin)
    users['admin'] = admin

    # Create sellers
    for data in SELLERS:
        user = User(
            username=data['username'],
            email=data['email'],
            role='seller',
            display_name=data['display_name'],
            bio=data['bio'],
            gardening_story=data['gardening_story'],
            years_gardening=data['years_gardening'],
            city=data['city'],
            state=data['state'],
            zip_code=data['zip_code'],
            latitude=data['latitude'],
            longitude=data['longitude'],
        )
        user.set_password('password123')
        db.session.add(user)
        users[data['username']] = user

    # Create buyers
    for data in BUYERS:
        user = User(
            username=data['username'],
            email=data['email'],
            role='buyer',
            display_name=data['display_name'],
            city=data['city'],
            state=data['state'],
            zip_code=data['zip_code'],
            latitude=data['latitude'],
            longitude=data['longitude'],
        )
        user.set_password('password123')
        db.session.add(user)
        users[data['username']] = user

    db.session.flush()

    # Create listings
    all_listings = []
    for seller_username, items in LISTINGS_DATA:
        seller = users[seller_username]
        for item in items:
            # Only set image if the file exists
            img_file = item.get('image', '')
            img_path = os.path.join('app', 'static', 'uploads', img_file) if img_file else ''
            has_image = img_file and os.path.exists(img_path)

            listing = Listing(
                seller_id=seller.id,
                title=item['title'],
                description=item['description'],
                vegetable_type=item['vegetable_type'],
                price=item['price'],
                base_price=item['price'],
                initial_quantity=item['quantity'],
                price_floor=round(item['price'] * 0.70, 2),
                price_ceiling=round(item['price'] * 2.0, 2),
                smart_pricing_enabled=True,
                unit=item['unit'],
                quantity_available=item['quantity'],
                image_filename=img_file if has_image else None,
                pickup_city=seller.city,
                pickup_state=seller.state,
                pickup_zip=seller.zip_code,
                pickup_latitude=seller.latitude + random.uniform(-0.01, 0.01),
                pickup_longitude=seller.longitude + random.uniform(-0.01, 0.01),
                delivery_available=item['delivery'],
                delivery_radius_miles=item['radius'],
                pickup_instructions='Text me when you arrive!' if random.random() > 0.5 else '',
                is_active=True,
                created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 30)),
            )
            db.session.add(listing)
            all_listings.append((listing, seller))

    db.session.flush()

    # Create some completed orders with reviews
    frank = users['foodie_frank']
    diana = users['chef_diana']

    for buyer, listing, seller in [
        (frank, all_listings[0][0], all_listings[0][1]),  # Frank buys Maria's tomatoes
        (frank, all_listings[4][0], all_listings[4][1]),  # Frank buys Bob's zucchini
        (diana, all_listings[7][0], all_listings[7][1]),  # Diana buys Sarah's bok choy
        (diana, all_listings[10][0], all_listings[10][1]),  # Diana buys Oscar's honey
    ]:
        order = Order(
            buyer_id=buyer.id,
            seller_id=seller.id,
            total_price=listing.price * 2,
            status='completed',
            fulfillment_method='pickup',
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(5, 20)),
        )
        db.session.add(order)
        db.session.flush()

        oi = OrderItem(
            order_id=order.id,
            listing_id=listing.id,
            quantity=2,
            unit_price=listing.price,
        )
        db.session.add(oi)

        review = Review(
            reviewer_id=buyer.id,
            seller_id=seller.id,
            order_id=order.id,
            rating=random.choice([4, 4, 5, 5, 5]),
            comment=random.choice([
                'Amazing quality! So much better than the grocery store.',
                'Super fresh and the seller was really friendly. Will buy again!',
                'Exactly as described. Love supporting local gardeners.',
                'Wonderful produce. You can taste the difference when it\'s homegrown.',
                'Great experience! Easy pickup and everything was perfect.',
            ]),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10)),
        )
        db.session.add(review)

    # Create a pending order
    pending_order = Order(
        buyer_id=frank.id,
        seller_id=users['garden_grace'].id,
        total_price=7.00,
        status='pending',
        fulfillment_method='delivery',
        notes='Can you deliver Saturday morning?',
    )
    db.session.add(pending_order)
    db.session.flush()

    db.session.add(OrderItem(
        order_id=pending_order.id,
        listing_id=all_listings[14][0].id,  # Grace's rainbow carrots
        quantity=1,
        unit_price=4.00,
    ))
    db.session.add(OrderItem(
        order_id=pending_order.id,
        listing_id=all_listings[15][0].id,  # Grace's golden beets
        quantity=1,
        unit_price=3.50,
    ))

    # Reduce quantities on some listings to demonstrate dynamic pricing
    all_listings[0][0].quantity_available = 3   # Maria's tomatoes: 3/12 remaining -> high demand
    all_listings[4][0].quantity_available = 22  # Bob's zucchini: 22/25 -> low demand
    all_listings[11][0].quantity_available = 1  # Oscar's honey: 1/6 remaining -> very high demand
    all_listings[7][0].quantity_available = 2   # Sarah's bok choy: 2/10 remaining -> high demand

    # Create PricingConfig singleton
    config = PricingConfig(enabled=True, global_multiplier=1.0)
    db.session.add(config)

    # Create some messages
    thread1 = Message.make_thread_id(frank.id, users['green_thumb_maria'].id, all_listings[0][0].id)
    msgs = [
        (frank.id, users['green_thumb_maria'].id, 'Hi Maria! Are your tomatoes still available? I\'d love to pick some up this weekend.'),
        (users['green_thumb_maria'].id, frank.id, 'Hi Frank! Yes, I have plenty. I\'m usually home Saturday mornings if you want to stop by.'),
        (frank.id, users['green_thumb_maria'].id, 'Perfect! I\'ll come by around 10am. Thanks!'),
    ]
    for i, (sender, recipient, body) in enumerate(msgs):
        msg = Message(
            thread_id=thread1,
            sender_id=sender,
            recipient_id=recipient,
            listing_id=all_listings[0][0].id,
            body=body,
            is_read=True,
            created_at=datetime.now(timezone.utc) - timedelta(hours=48 - i * 2),
        )
        db.session.add(msg)

    # ---- Neighborhood Garden Groups ----
    print("Creating neighborhood groups...")

    maria = users['green_thumb_maria']
    bob = users['backyard_bob']
    sarah = users['sunny_sarah']
    oscar = users['organic_oscar']
    grace = users['garden_grace']

    # Group 1: Dundee Gardeners
    dundee = NeighborhoodGroup(
        name='Dundee Gardeners',
        slug='dundee-gardeners',
        description='The established gardening community of the Dundee neighborhood. We share tips, trade produce, and host monthly meetups at Memorial Park. All skill levels welcome!',
        neighborhood='Dundee',
        city='Omaha',
        state='NE',
        zip_code='68132',
        is_public=True,
        created_by_id=maria.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=120),
    )
    db.session.add(dundee)
    db.session.flush()

    for u, role in [(maria, 'admin'), (frank, 'member'), (diana, 'member'), (oscar, 'moderator')]:
        db.session.add(GroupMembership(group_id=dundee.id, user_id=u.id, role=role,
                                       joined_at=datetime.now(timezone.utc) - timedelta(days=random.randint(10, 100))))

    dundee_posts = [
        GroupPost(group_id=dundee.id, author_id=maria.id, post_type='update',
                  title='Welcome to Dundee Gardeners!',
                  content='So glad to have this group going. Let us use this space to share gardening tips, trade surplus produce, and plan community events. Looking forward to a great growing season!',
                  pinned=True,
                  created_at=datetime.now(timezone.utc) - timedelta(days=90)),
        GroupPost(group_id=dundee.id, author_id=oscar.id, post_type='question',
                  title='Best time to plant garlic in Zone 5b?',
                  content='I want to try planting garlic this fall. When is the ideal time to get bulbs in the ground here in Omaha? Any variety recommendations?',
                  created_at=datetime.now(timezone.utc) - timedelta(days=14)),
        GroupPost(group_id=dundee.id, author_id=maria.id, post_type='event',
                  title='Monthly Garden Walk - Dundee',
                  content='Join us for our monthly garden walk! We will visit 3 neighborhood gardens and share tips. Bring your questions and a friend!',
                  event_date=datetime.now(timezone.utc) + timedelta(days=10),
                  event_location='Memorial Park, 6005 Underwood Ave',
                  created_at=datetime.now(timezone.utc) - timedelta(days=5)),
        GroupPost(group_id=dundee.id, author_id=frank.id, post_type='trade',
                  title='Trade: Tomatoes for Peppers',
                  content='I have way too many cherry tomatoes. Would love to trade for some bell peppers or jalapenos. Anyone interested?',
                  created_at=datetime.now(timezone.utc) - timedelta(days=3)),
    ]
    for p in dundee_posts:
        db.session.add(p)
    db.session.flush()

    # Add some comments
    db.session.add(GroupPostComment(post_id=dundee_posts[1].id, author_id=maria.id,
                                    content='Mid-October is perfect! I usually plant around Oct 15. Try Music or German Extra Hardy varieties.',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=13)))
    db.session.add(GroupPostComment(post_id=dundee_posts[1].id, author_id=frank.id,
                                    content='I planted some last year and had great results with Chesnok Red. Plant them about 2 inches deep.',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=12)))

    # Group 2: Benson Green Thumbs
    benson = NeighborhoodGroup(
        name='Benson Green Thumbs',
        slug='benson-green-thumbs',
        description='Benson neighborhood gardening crew! We love community events, seed swaps, and helping new gardeners get started. Join us for weekly Saturday morning garden hangs.',
        neighborhood='Benson',
        city='Omaha',
        state='NE',
        zip_code='68104',
        is_public=True,
        created_by_id=bob.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=90),
    )
    db.session.add(benson)
    db.session.flush()

    for u, role in [(bob, 'admin'), (sarah, 'moderator'), (frank, 'member'), (grace, 'member')]:
        db.session.add(GroupMembership(group_id=benson.id, user_id=u.id, role=role,
                                       joined_at=datetime.now(timezone.utc) - timedelta(days=random.randint(10, 80))))

    benson_posts = [
        GroupPost(group_id=benson.id, author_id=bob.id, post_type='update',
                  title='Seed Swap This Saturday!',
                  content='Bring your extra seeds to the Benson community center this Saturday at 10am. I have tons of heirloom tomato and squash seeds to share.',
                  created_at=datetime.now(timezone.utc) - timedelta(days=7)),
        GroupPost(group_id=benson.id, author_id=sarah.id, post_type='photo',
                  title='My bok choy harvest this morning',
                  content='Look at this beautiful batch of baby bok choy! The cool nights have been perfect for growing Asian greens. Happy to share tips if anyone wants to try.',
                  created_at=datetime.now(timezone.utc) - timedelta(days=4)),
        GroupPost(group_id=benson.id, author_id=grace.id, post_type='event',
                  title='Beginner Garden Workshop',
                  content='Hosting a free workshop for new gardeners. We will cover soil prep, seed starting, and basic garden planning. All are welcome!',
                  event_date=datetime.now(timezone.utc) + timedelta(days=14),
                  event_location='Benson Community Center, 6008 Maple St',
                  created_at=datetime.now(timezone.utc) - timedelta(days=2)),
    ]
    for p in benson_posts:
        db.session.add(p)
    db.session.flush()

    db.session.add(GroupPostComment(post_id=benson_posts[0].id, author_id=grace.id,
                                    content='I will be there! I have some great purple carrot seeds to swap.',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=6)))

    # Group 3: Aksarben Urban Farmers
    aksarben = NeighborhoodGroup(
        name='Aksarben Urban Farmers',
        slug='aksarben-urban-farmers',
        description='A newer group focused on urban farming techniques in the Aksarben area. Container gardening, vertical farming, composting, and making the most of small spaces.',
        neighborhood='Aksarben',
        city='Omaha',
        state='NE',
        zip_code='68106',
        is_public=True,
        created_by_id=sarah.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=45),
    )
    db.session.add(aksarben)
    db.session.flush()

    for u, role in [(sarah, 'admin'), (maria, 'member'), (diana, 'member')]:
        db.session.add(GroupMembership(group_id=aksarben.id, user_id=u.id, role=role,
                                       joined_at=datetime.now(timezone.utc) - timedelta(days=random.randint(5, 40))))

    aksarben_posts = [
        GroupPost(group_id=aksarben.id, author_id=sarah.id, post_type='update',
                  title='Welcome Urban Farmers!',
                  content='Excited to start this group for anyone growing food in small urban spaces. Whether you have a balcony, patio, or small yard, let us figure it out together.',
                  pinned=True,
                  created_at=datetime.now(timezone.utc) - timedelta(days=40)),
        GroupPost(group_id=aksarben.id, author_id=sarah.id, post_type='question',
                  title='Best containers for tomatoes?',
                  content='What size containers do you all use for tomatoes? I have been using 5-gallon buckets but wondering if I should go bigger.',
                  created_at=datetime.now(timezone.utc) - timedelta(days=10)),
    ]
    for p in aksarben_posts:
        db.session.add(p)
    db.session.flush()

    db.session.add(GroupPostComment(post_id=aksarben_posts[1].id, author_id=maria.id,
                                    content='I switched to 10-gallon fabric pots and the difference was huge. Way better root growth and drainage.',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=9)))

    # Group 4: Midtown Growers Collective
    midtown = NeighborhoodGroup(
        name='Midtown Growers Collective',
        slug='midtown-growers-collective',
        description='Focused on shared resources and cooperative gardening in the Midtown area. We share tools, bulk order seeds together, and coordinate plantings to avoid everyone growing the same thing.',
        neighborhood='Midtown',
        city='Omaha',
        state='NE',
        zip_code='68131',
        is_public=True,
        created_by_id=oscar.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=60),
    )
    db.session.add(midtown)
    db.session.flush()

    for u, role in [(oscar, 'admin'), (bob, 'moderator'), (maria, 'member'), (grace, 'member'), (frank, 'member')]:
        db.session.add(GroupMembership(group_id=midtown.id, user_id=u.id, role=role,
                                       joined_at=datetime.now(timezone.utc) - timedelta(days=random.randint(5, 55))))

    midtown_posts = [
        GroupPost(group_id=midtown.id, author_id=oscar.id, post_type='update',
                  title='Tool Library Now Open!',
                  content='Great news! Our shared tool library is now stocked with tillers, wheelbarrows, and hand tools. DM me to arrange a pickup. Let us keep costs down by sharing resources.',
                  pinned=True,
                  created_at=datetime.now(timezone.utc) - timedelta(days=30)),
        GroupPost(group_id=midtown.id, author_id=bob.id, post_type='trade',
                  title='Bulk Seed Order - Spring Planning',
                  content='Planning a bulk seed order from Johnny Seeds. If we order together we can save 20% on shipping. Drop a comment with what you need and I will compile the list.',
                  created_at=datetime.now(timezone.utc) - timedelta(days=8)),
        GroupPost(group_id=midtown.id, author_id=grace.id, post_type='update',
                  title='Composting Workshop Recap',
                  content='Thanks to everyone who came to the composting workshop! Here are the key takeaways: greens to browns ratio of 1:3, keep it moist like a wrung-out sponge, and turn it every 2 weeks.',
                  created_at=datetime.now(timezone.utc) - timedelta(days=1)),
    ]
    for p in midtown_posts:
        db.session.add(p)
    db.session.flush()

    db.session.add(GroupPostComment(post_id=midtown_posts[1].id, author_id=maria.id,
                                    content='I need heirloom tomato seeds (Cherokee Purple, Brandywine) and Genovese basil. Count me in!',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=7)))
    db.session.add(GroupPostComment(post_id=midtown_posts[1].id, author_id=grace.id,
                                    content='I would love some rainbow carrot seeds and sugar pie pumpkin seeds. Great idea Bob!',
                                    created_at=datetime.now(timezone.utc) - timedelta(days=6)))

    # ---- Community Gardens ----
    print("Creating community gardens...")

    # Garden 1: Hanscom Park Community Garden
    hanscom = CommunityGarden(
        name='Hanscom Park Community Garden',
        slug='hanscom-park-community-garden',
        description='A beloved community garden nestled near Hanscom Park. We have been growing together since 2018, offering 20 individual plots for families and individuals. Our garden emphasizes organic growing methods and community building. Water access, composting bins, and a tool shed are available to all members.',
        address='1802 S 32nd Ave',
        city='Omaha',
        state='NE',
        zip_code='68105',
        total_plots=20,
        plot_fee_annual=50.0,
        operating_model='allotment',
        season_start=datetime(2025, 4, 15).date(),
        season_end=datetime(2025, 10, 31).date(),
        rules='1. Water your plot at least twice a week\n2. Keep pathways clear and weed-free\n3. Use organic methods only - no synthetic pesticides\n4. Attend at least 2 workdays per season\n5. Harvest regularly to keep plants productive\n6. Share surplus with neighbors or donate to food bank\n7. Clean up your plot by November 15',
        contact_email='hanscomgarden@yardharvest.com',
        organizer_id=maria.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=365),
    )
    db.session.add(hanscom)
    db.session.flush()

    # Hanscom plots - 20 plots
    for i in range(1, 21):
        status = 'assigned' if i <= 14 else ('available' if i <= 18 else 'maintenance')
        assigned_user = None
        if status == 'assigned':
            assigned_user = [maria, bob, sarah, oscar, grace, frank, diana,
                            maria, bob, sarah, oscar, grace, frank, diana][i - 1]
        plot = GardenPlot(
            garden_id=hanscom.id,
            plot_number=str(i),
            size='4x8 ft' if i <= 10 else '10x10 ft',
            location_notes=f'Row {"ABCDE"[(i-1)//4]}, Position {(i-1)%4 + 1}' + (', near water spigot' if i in [1, 5, 9, 13] else ''),
            status=status,
            assigned_to_id=assigned_user.id if assigned_user else None,
            assigned_date=(datetime.now(timezone.utc) - timedelta(days=random.randint(30, 300))).date() if status == 'assigned' else None,
        )
        db.session.add(plot)

    # Hanscom resources
    hanscom_resources = [
        SharedResource(garden_id=hanscom.id, name='Wheelbarrow', resource_type='tool', description='Large steel wheelbarrow', quantity=2, condition='good'),
        SharedResource(garden_id=hanscom.id, name='Garden Hose (100ft)', resource_type='tool', description='Heavy duty garden hose with spray nozzle', quantity=3, condition='good'),
        SharedResource(garden_id=hanscom.id, name='Spade', resource_type='tool', description='Full-size digging spade', quantity=4, condition='good'),
        SharedResource(garden_id=hanscom.id, name='Rake', resource_type='tool', description='Leaf rake and garden rake', quantity=3, condition='fair'),
        SharedResource(garden_id=hanscom.id, name='Compost Bin', resource_type='infrastructure', description='3-bin composting system', quantity=1, condition='good'),
        SharedResource(garden_id=hanscom.id, name='Seed Starting Mix', resource_type='supply', description='Organic seed starting mix - 50lb bag', quantity=2, condition='new'),
        SharedResource(garden_id=hanscom.id, name='Tomato Cages', resource_type='supply', description='Heavy duty tomato cages, 5ft tall', quantity=20, condition='good'),
        SharedResource(garden_id=hanscom.id, name='Row Cover', resource_type='supply', description='Frost protection row cover, 50ft roll', quantity=3, condition='good'),
    ]
    for r in hanscom_resources:
        db.session.add(r)

    # Check out a few resources
    hanscom_resources[0].checked_out_to_id = bob.id
    hanscom_resources[0].checked_out_at = datetime.now(timezone.utc) - timedelta(hours=4)

    # Hanscom events
    hanscom_events = [
        GardenEvent(garden_id=hanscom.id, title='Spring Cleanup Workday', description='Help us prepare the garden for the new season! We will clear debris, repair raised beds, and spread compost. Bring gloves and water.',
                    event_type='workday', event_date=datetime.now(timezone.utc) + timedelta(days=7), duration_hours=3, max_volunteers=15, created_by_id=maria.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=10)),
        GardenEvent(garden_id=hanscom.id, title='Composting 101 Workshop', description='Learn the basics of composting. We will cover greens vs browns, proper moisture levels, and how to use finished compost in your garden.',
                    event_type='workshop', event_date=datetime.now(timezone.utc) + timedelta(days=21), duration_hours=1.5, max_volunteers=20, created_by_id=oscar.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=5)),
        GardenEvent(garden_id=hanscom.id, title='Summer Potluck & Garden Tour', description='Bring a dish to share (bonus points if it uses garden produce!) and enjoy a tour of all the plots.',
                    event_type='social', event_date=datetime.now(timezone.utc) + timedelta(days=45), duration_hours=3, max_volunteers=30, created_by_id=maria.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=2)),
        GardenEvent(garden_id=hanscom.id, title='Monthly Garden Meeting', description='Discuss garden business, upcoming events, and any issues. All plot holders encouraged to attend.',
                    event_type='meeting', event_date=datetime.now(timezone.utc) - timedelta(days=5), duration_hours=1, max_volunteers=None, created_by_id=maria.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=20)),
        GardenEvent(garden_id=hanscom.id, title='Fall Harvest Festival', description='Celebrate the harvest season! Bring your best produce for the friendly harvest competition.',
                    event_type='harvest_day', event_date=datetime.now(timezone.utc) - timedelta(days=60), duration_hours=4, max_volunteers=25, created_by_id=maria.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=90)),
    ]
    for e in hanscom_events:
        db.session.add(e)
    db.session.flush()

    # RSVPs for events
    for event in hanscom_events:
        rsvp_users = random.sample([bob, sarah, oscar, grace, frank, diana], random.randint(3, 6))
        for u in rsvp_users:
            db.session.add(EventRSVP(event_id=event.id, user_id=u.id, status=random.choice(['going', 'going', 'going', 'maybe']),
                                      created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 10))))

    # Hanscom harvest logs
    harvest_categories = ['tomatoes', 'peppers', 'greens', 'herbs', 'squash', 'beans', 'root_vegetables', 'corn']
    harvest_varieties = {
        'tomatoes': ['Cherokee Purple', 'Roma', 'Cherry', 'Brandywine', 'San Marzano'],
        'peppers': ['Bell Pepper', 'Jalapeno', 'Poblano', 'Banana Pepper'],
        'greens': ['Lettuce', 'Kale', 'Spinach', 'Bok Choy', 'Swiss Chard'],
        'herbs': ['Basil', 'Cilantro', 'Dill', 'Parsley', 'Mint'],
        'squash': ['Zucchini', 'Yellow Squash', 'Butternut', 'Acorn'],
        'beans': ['Green Beans', 'Snap Peas', 'Lima Beans'],
        'root_vegetables': ['Carrots', 'Beets', 'Radishes', 'Potatoes'],
        'corn': ['Sweet Corn', 'Popcorn'],
    }
    destinations = ['personal', 'personal', 'personal', 'shared', 'food_bank', 'marketplace']

    for _ in range(60):
        cat = random.choice(harvest_categories)
        var = random.choice(harvest_varieties[cat])
        harvester = random.choice([maria, bob, sarah, oscar, grace, frank, diana])
        h = HarvestLog(
            garden_id=hanscom.id,
            user_id=harvester.id,
            category=cat,
            variety=var,
            quantity_lbs=round(random.uniform(0.5, 15.0), 1),
            harvest_date=(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180))).date(),
            destination=random.choice(destinations),
            notes='',
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 180)),
        )
        db.session.add(h)

    # Hanscom waitlist
    db.session.add(GardenWaitlist(garden_id=hanscom.id, user_id=diana.id, plot_size_pref='4x8 ft',
                                   notes='I am a beginner gardener looking to learn.', status='waiting',
                                   requested_at=datetime.now(timezone.utc) - timedelta(days=15)))

    # Garden 2: Benson Community Growing Space
    benson_garden = CommunityGarden(
        name='Benson Community Growing Space',
        slug='benson-community-growing-space',
        description='A hybrid community garden in the heart of Benson. We have 8 individual plots and a large shared growing area where we collectively grow food for the neighborhood and local food banks. Perfect for people who want to garden but prefer a collaborative approach.',
        address='6015 Maple St',
        city='Omaha',
        state='NE',
        zip_code='68104',
        total_plots=12,
        plot_fee_annual=35.0,
        operating_model='hybrid',
        season_start=datetime(2025, 4, 1).date(),
        season_end=datetime(2025, 11, 15).date(),
        rules='1. Shared areas are maintained collectively\n2. Sign up for weekly watering shifts\n3. Organic methods preferred\n4. Donate at least 10% of harvest to food bank\n5. Label all personal plantings clearly',
        contact_email='bensongarden@yardharvest.com',
        organizer_id=bob.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=200),
    )
    db.session.add(benson_garden)
    db.session.flush()

    # Benson plots
    for i in range(1, 13):
        status = 'assigned' if i <= 8 else 'available'
        assigned_user = None
        if status == 'assigned':
            assigned_user = [bob, sarah, grace, frank, oscar, maria, diana, bob][i - 1]
        plot = GardenPlot(
            garden_id=benson_garden.id,
            plot_number=f'B{i}',
            size='4x8 ft',
            location_notes=f'Section {"AB"[(i-1)//6]}, Spot {(i-1)%6 + 1}',
            status=status,
            assigned_to_id=assigned_user.id if assigned_user else None,
            assigned_date=(datetime.now(timezone.utc) - timedelta(days=random.randint(30, 180))).date() if status == 'assigned' else None,
        )
        db.session.add(plot)

    # Benson resources
    benson_res = [
        SharedResource(garden_id=benson_garden.id, name='Rototiller', resource_type='tool', description='Gas-powered rototiller for bed prep', quantity=1, condition='good'),
        SharedResource(garden_id=benson_garden.id, name='Watering Cans', resource_type='tool', description='2-gallon watering cans', quantity=6, condition='good'),
        SharedResource(garden_id=benson_garden.id, name='Raised Bed Soil', resource_type='supply', description='Bulk garden soil mix', quantity=10, condition='new'),
        SharedResource(garden_id=benson_garden.id, name='Hand Tools Set', resource_type='tool', description='Trowel, cultivator, weeder set', quantity=5, condition='fair'),
    ]
    for r in benson_res:
        db.session.add(r)

    # Benson events
    benson_ev = [
        GardenEvent(garden_id=benson_garden.id, title='Saturday Morning Work Party', description='Join us every Saturday for community gardening! We work on shared beds, maintain pathways, and enjoy coffee together.',
                    event_type='workday', event_date=datetime.now(timezone.utc) + timedelta(days=3), duration_hours=3, max_volunteers=12, created_by_id=bob.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=7)),
        GardenEvent(garden_id=benson_garden.id, title='Seed Starting Workshop', description='Learn how to start seeds indoors for transplanting. We will cover timing, soil mix, and light requirements.',
                    event_type='workshop', event_date=datetime.now(timezone.utc) + timedelta(days=14), duration_hours=2, max_volunteers=15, created_by_id=sarah.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=3)),
    ]
    for e in benson_ev:
        db.session.add(e)
    db.session.flush()

    for event in benson_ev:
        rsvp_users = random.sample([maria, sarah, grace, frank, oscar], random.randint(2, 5))
        for u in rsvp_users:
            db.session.add(EventRSVP(event_id=event.id, user_id=u.id, status='going'))

    # Benson harvest logs
    for _ in range(35):
        cat = random.choice(harvest_categories)
        var = random.choice(harvest_varieties[cat])
        harvester = random.choice([bob, sarah, grace, frank, oscar])
        h = HarvestLog(
            garden_id=benson_garden.id,
            user_id=harvester.id,
            category=cat,
            variety=var,
            quantity_lbs=round(random.uniform(0.5, 12.0), 1),
            harvest_date=(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 150))).date(),
            destination=random.choice(['personal', 'shared', 'food_bank', 'food_bank']),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 150)),
        )
        db.session.add(h)

    # Garden 3: Florence Urban Farm
    florence = CommunityGarden(
        name='Florence Urban Farm',
        slug='florence-urban-farm',
        description='A communal urban farm in the Florence neighborhood focused on food justice and community self-sufficiency. All produce is grown collectively and shared among members and donated to local families in need. No individual plots - we grow and harvest together!',
        address='8502 N 30th St',
        city='Omaha',
        state='NE',
        zip_code='68112',
        total_plots=8,
        plot_fee_annual=0.0,
        operating_model='communal',
        season_start=datetime(2025, 3, 15).date(),
        season_end=datetime(2025, 11, 30).date(),
        rules='1. All produce is shared communally\n2. Everyone contributes at least 4 hours per month\n3. No chemicals of any kind\n4. Respect the growing schedule posted on the shed\n5. Children welcome with adult supervision',
        contact_email='florencefarm@yardharvest.com',
        organizer_id=grace.id,
        created_at=datetime.now(timezone.utc) - timedelta(days=150),
    )
    db.session.add(florence)
    db.session.flush()

    # Florence plots (communal growing areas)
    florence_areas = [
        ('Tomato Row', '20x4 ft', 'Main tomato growing area, south-facing'),
        ('Greens Bed', '10x10 ft', 'Lettuce, kale, spinach rotation'),
        ('Root Veggie Patch', '10x10 ft', 'Carrots, beets, potatoes'),
        ('Herb Spiral', '6x6 ft', 'Permaculture herb spiral'),
        ('Three Sisters', '15x15 ft', 'Corn, beans, and squash companion planting'),
        ('Berry Patch', '10x4 ft', 'Strawberries and raspberries'),
        ('Cut Flower Garden', '8x4 ft', 'Sunflowers, zinnias, and pollinator plants'),
        ('Seedling Nursery', '4x8 ft', 'Covered seed starting area'),
    ]
    for i, (name, size, notes) in enumerate(florence_areas):
        plot = GardenPlot(
            garden_id=florence.id,
            plot_number=name,
            size=size,
            location_notes=notes,
            status='assigned',
            assigned_to_id=grace.id,
            assigned_date=(datetime.now(timezone.utc) - timedelta(days=150)).date(),
        )
        db.session.add(plot)

    # Florence resources
    florence_res = [
        SharedResource(garden_id=florence.id, name='Community Tool Shed', resource_type='infrastructure', description='Fully stocked tool shed with all basic gardening tools', quantity=1, condition='good'),
        SharedResource(garden_id=florence.id, name='Rain Barrel', resource_type='infrastructure', description='55-gallon rain collection barrels', quantity=4, condition='good'),
        SharedResource(garden_id=florence.id, name='Worm Composting Bin', resource_type='infrastructure', description='Large vermicomposting system', quantity=1, condition='good'),
        SharedResource(garden_id=florence.id, name='Harvest Baskets', resource_type='supply', description='Reusable produce collection baskets', quantity=10, condition='good'),
    ]
    for r in florence_res:
        db.session.add(r)

    # Florence events
    florence_ev = [
        GardenEvent(garden_id=florence.id, title='Community Harvest Day', description='Come help harvest and divide the week produce. Everyone takes home a share, and we deliver to families who cannot make it.',
                    event_type='harvest_day', event_date=datetime.now(timezone.utc) + timedelta(days=5), duration_hours=2, max_volunteers=20, created_by_id=grace.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=3)),
        GardenEvent(garden_id=florence.id, title='Kids Garden Club', description='Monthly session for children ages 5-12. They will learn about where food comes from, plant seeds, and take home produce.',
                    event_type='workshop', event_date=datetime.now(timezone.utc) + timedelta(days=10), duration_hours=1.5, max_volunteers=15, created_by_id=grace.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=8)),
        GardenEvent(garden_id=florence.id, title='Garden Planning Meeting', description='Plan next season plantings, discuss crop rotation, and coordinate volunteer schedules.',
                    event_type='meeting', event_date=datetime.now(timezone.utc) + timedelta(days=30), duration_hours=1.5, max_volunteers=None, created_by_id=grace.id,
                    created_at=datetime.now(timezone.utc) - timedelta(days=1)),
    ]
    for e in florence_ev:
        db.session.add(e)
    db.session.flush()

    for event in florence_ev:
        rsvp_users = random.sample([maria, bob, sarah, oscar, frank], random.randint(2, 5))
        for u in rsvp_users:
            db.session.add(EventRSVP(event_id=event.id, user_id=u.id, status='going'))

    # Florence harvest logs (heavily food bank focused)
    for _ in range(45):
        cat = random.choice(harvest_categories)
        var = random.choice(harvest_varieties[cat])
        harvester = random.choice([grace, maria, oscar, sarah])
        h = HarvestLog(
            garden_id=florence.id,
            user_id=harvester.id,
            category=cat,
            variety=var,
            quantity_lbs=round(random.uniform(1.0, 20.0), 1),
            harvest_date=(datetime.now(timezone.utc) - timedelta(days=random.randint(1, 120))).date(),
            destination=random.choice(['shared', 'shared', 'food_bank', 'food_bank', 'food_bank']),
            created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1, 120)),
        )
        db.session.add(h)

    # Florence waitlist
    db.session.add(GardenWaitlist(garden_id=florence.id, user_id=frank.id, plot_size_pref='',
                                   notes='I want to help with the community growing effort.', status='waiting',
                                   requested_at=datetime.now(timezone.utc) - timedelta(days=10)))
    db.session.add(GardenWaitlist(garden_id=florence.id, user_id=diana.id, plot_size_pref='',
                                   notes='Interested in volunteering and learning to garden.', status='waiting',
                                   requested_at=datetime.now(timezone.utc) - timedelta(days=5)))

    db.session.commit()
    print(f"Done! Created:")
    print(f"  - 1 admin user")
    print(f"  - {len(SELLERS)} sellers")
    print(f"  - {len(BUYERS)} buyers")
    print(f"  - {sum(len(items) for _, items in LISTINGS_DATA)} listings")
    print(f"  - 5 orders (4 completed, 1 pending)")
    print(f"  - 4 reviews")
    print(f"  - 3 messages")
    print(f"  - 1 pricing config")
    print(f"  - 4 neighborhood groups with posts and comments")
    print(f"  - 3 community gardens with plots, resources, events, and harvests")
    print(f"\nSample logins:")
    print(f"  Admin:  admin@yardharvest.com / admin123")
    print(f"  Seller: maria@example.com / password123")
    print(f"  Buyer:  frank@example.com / password123")


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
