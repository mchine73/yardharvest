"""Tests for a representative slice of the marketplace REST API:
listings browse/detail/create and cart add.
"""
from app.models import Listing, CartItem


def _make_listing(db_session, seller, **kwargs):
    listing = Listing(
        seller_id=seller.id,
        title=kwargs.pop('title', 'Fresh Tomatoes'),
        description=kwargs.pop('description', 'Ripe and red'),
        price=kwargs.pop('price', 3.50),
        base_price=kwargs.pop('base_price', 3.50),
        quantity_available=kwargs.pop('quantity_available', 10),
        is_active=kwargs.pop('is_active', True),
        smart_pricing_enabled=False,  # avoid dynamic pricing variance in assertions
        **kwargs,
    )
    db_session.add(listing)
    db_session.commit()
    return listing


def test_categories_endpoint(client):
    resp = client.get('/api/listings/categories')
    assert resp.status_code == 200
    data = resp.get_json()
    assert 'categories' in data and 'units' in data
    assert any(c['value'] == 'tomatoes' for c in data['categories'])


def test_browse_empty(client):
    resp = client.get('/api/listings/browse')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['listings'] == []
    assert data['total'] == 0


def test_browse_returns_active_listings(client, db_session, make_user):
    seller = make_user(username='browseseller', role='seller')
    _make_listing(db_session, seller, title='Carrots')
    resp = client.get('/api/listings/browse')
    assert resp.status_code == 200
    titles = [l['title'] for l in resp.get_json()['listings']]
    assert 'Carrots' in titles


def test_browse_hides_out_of_stock(client, db_session, make_user):
    seller = make_user(username='oosseller', role='seller')
    _make_listing(db_session, seller, title='Sold Out', quantity_available=0)
    resp = client.get('/api/listings/browse')
    titles = [l['title'] for l in resp.get_json()['listings']]
    assert 'Sold Out' not in titles


def test_listing_detail(client, db_session, make_user):
    seller = make_user(username='detailseller', role='seller')
    listing = _make_listing(db_session, seller, title='Detail Squash')
    resp = client.get(f'/api/listings/{listing.id}')
    assert resp.status_code == 200
    assert resp.get_json()['title'] == 'Detail Squash'


def test_listing_detail_404(client):
    resp = client.get('/api/listings/999999')
    assert resp.status_code == 404


def test_inactive_listing_hidden_from_anonymous(client, db_session, make_user):
    seller = make_user(username='inactiveseller', role='seller')
    listing = _make_listing(db_session, seller, is_active=False)
    resp = client.get(f'/api/listings/{listing.id}')
    assert resp.status_code == 404


def test_create_listing_requires_seller_role(client, make_user):
    make_user(username='buyeronly', email='buyeronly@example.com',
              password='GoodPass1', role='buyer')
    client.post('/api/auth/login', json={
        'email': 'buyeronly@example.com', 'password': 'GoodPass1',
    })
    resp = client.post('/api/listings', data={
        'title': 'Nope', 'price': '2.00', 'quantity_available': '5',
    }, content_type='multipart/form-data')
    assert resp.status_code == 403


def test_create_listing_success(client, make_user):
    make_user(username='realseller', email='realseller@example.com',
              password='GoodPass1', role='seller')
    client.post('/api/auth/login', json={
        'email': 'realseller@example.com', 'password': 'GoodPass1',
    })
    resp = client.post('/api/listings', data={
        'title': 'Heirloom Tomatoes',
        'description': 'Garden grown',
        'vegetable_type': 'tomatoes',
        'price': '4.25',
        'unit': 'each',
        'quantity_available': '12',
        'use_profile_address': 'true',
    }, content_type='multipart/form-data')
    assert resp.status_code == 201
    data = resp.get_json()
    assert data['title'] == 'Heirloom Tomatoes'
    assert data['quantity_available'] == 12


def test_create_listing_rejects_bad_price(client, make_user):
    make_user(username='badprice', email='badprice@example.com',
              password='GoodPass1', role='seller')
    client.post('/api/auth/login', json={
        'email': 'badprice@example.com', 'password': 'GoodPass1',
    })
    resp = client.post('/api/listings', data={
        'title': 'Bad', 'price': '0', 'quantity_available': '1',
    }, content_type='multipart/form-data')
    assert resp.status_code == 400


def test_cart_add_requires_auth(client, db_session, make_user):
    seller = make_user(username='cartseller', role='seller')
    listing = _make_listing(db_session, seller)
    resp = client.post(f'/api/cart/add/{listing.id}', json={'quantity': 1})
    assert resp.status_code == 401


def test_cart_add_success(client, db_session, make_user):
    seller = make_user(username='cseller', role='seller')
    listing = _make_listing(db_session, seller, title='Cartable Beans')
    make_user(username='cbuyer', email='cbuyer@example.com',
              password='GoodPass1', role='buyer')
    client.post('/api/auth/login', json={
        'email': 'cbuyer@example.com', 'password': 'GoodPass1',
    })
    resp = client.post(f'/api/cart/add/{listing.id}', json={'quantity': 2})
    assert resp.status_code == 200
    assert resp.get_json()['cart_count'] == 1

    # verify the cart count endpoint agrees
    count_resp = client.get('/api/cart/count')
    assert count_resp.get_json()['count'] == 1


def test_cart_add_own_listing_rejected(client, db_session, make_user):
    seller = make_user(username='selfseller', email='selfseller@example.com',
                       password='GoodPass1', role='both')
    listing = _make_listing(db_session, seller)
    client.post('/api/auth/login', json={
        'email': 'selfseller@example.com', 'password': 'GoodPass1',
    })
    resp = client.post(f'/api/cart/add/{listing.id}', json={'quantity': 1})
    assert resp.status_code == 400


def test_cart_add_caps_at_available_quantity(client, db_session, make_user):
    seller = make_user(username='capseller', role='seller')
    listing = _make_listing(db_session, seller, quantity_available=3)
    make_user(username='capbuyer', email='capbuyer@example.com',
              password='GoodPass1', role='buyer')
    client.post('/api/auth/login', json={
        'email': 'capbuyer@example.com', 'password': 'GoodPass1',
    })
    client.post(f'/api/cart/add/{listing.id}', json={'quantity': 99})
    with client.application.app_context():
        item = CartItem.query.filter_by(listing_id=listing.id).first()
        assert item.quantity == 3
