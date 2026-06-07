"""Unit tests for model logic (no HTTP)."""
from app.models import User, Listing, Order, Review, Message


def test_set_and_check_password_roundtrip(make_user):
    user = make_user(username='pwuser', password='Hunter2Pass')
    assert user.check_password('Hunter2Pass') is True
    assert user.check_password('wrong') is False


def test_password_is_hashed_not_plaintext(make_user):
    user = make_user(username='hashuser', password='Secret123')
    assert user.password_hash != 'Secret123'
    assert 'Secret123' not in user.password_hash
    # werkzeug default produces a scheme-prefixed hash
    assert ':' in user.password_hash or '$' in user.password_hash


def test_role_logic_can_sell_can_buy(make_user):
    buyer = make_user(username='buyer', role='buyer')
    seller = make_user(username='seller', role='seller')
    both = make_user(username='both', role='both')

    assert buyer.can_buy() is True
    assert buyer.can_sell() is False

    assert seller.can_sell() is True
    assert seller.can_buy() is False

    assert both.can_sell() is True
    assert both.can_buy() is True


def test_garden_role_helpers(make_user):
    manager = make_user(username='mgr', role='manager')
    gardener = make_user(username='gard', role='gardener')
    assert manager.is_garden_manager() is True
    assert manager.is_gardener() is False
    assert gardener.is_gardener() is True
    assert gardener.is_garden_manager() is False


def test_is_admin_defaults_false(make_user):
    user = make_user(username='regular')
    assert user.is_admin in (False, None)
    admin = make_user(username='boss', is_admin=True)
    assert admin.is_admin is True


def test_avg_rating_none_without_reviews(make_user):
    seller = make_user(username='noreviews', role='seller')
    assert seller.avg_rating is None
    assert seller.review_count == 0


def test_avg_rating_and_count_with_reviews(db_session, make_user):
    seller = make_user(username='rated', role='seller')
    buyer = make_user(username='reviewer', role='buyer')

    # Reviews need an order (order_id is unique + non-null).
    ratings = [5, 4, 4]
    for i, rating in enumerate(ratings):
        order = Order(buyer_id=buyer.id, seller_id=seller.id, total_price=10.0)
        db_session.add(order)
        db_session.flush()
        review = Review(
            reviewer_id=buyer.id,
            seller_id=seller.id,
            order_id=order.id,
            rating=rating,
        )
        db_session.add(review)
    db_session.commit()

    assert seller.review_count == 3
    # (5 + 4 + 4) / 3 = 4.333 -> rounded to 1 decimal
    assert seller.avg_rating == 4.3


def test_make_thread_id_is_order_independent():
    a = Message.make_thread_id(2, 7, listing_id=3)
    b = Message.make_thread_id(7, 2, listing_id=3)
    assert a == b == '2-7-3'


def test_make_thread_id_defaults_listing_zero():
    assert Message.make_thread_id(4, 1) == '1-4-0'


def test_listing_belongs_to_seller(db_session, make_user):
    seller = make_user(username='grower', role='seller')
    listing = Listing(seller_id=seller.id, title='Tomatoes', price=2.5,
                       quantity_available=10)
    db_session.add(listing)
    db_session.commit()
    assert listing.seller.id == seller.id
    assert seller.listings.count() == 1
