"""Tests for opaque prefixed public_ids and password-hash hardening.

Covers:
- New users/gardens get opaque ``usr_``/``grd_`` ids (CSPRNG, non-numeric, unique).
- set_password pins scrypt; needs_password_rehash detects legacy hashes.
- Login transparently re-hashes a legacy (pbkdf2) password to scrypt.
- The garden resolver accepts both the integer PK and the opaque public_id.
"""
import re

import pytest
from werkzeug.exceptions import NotFound
from werkzeug.security import generate_password_hash

from app import db
from app.models import (
    User, CommunityGarden, generate_public_id, PASSWORD_HASH_METHOD,
    _PUBLIC_ID_ALPHABET,
)
from tests.conftest import login_via_api

USR_RE = re.compile(r'^usr_[%s]{14}$' % re.escape(_PUBLIC_ID_ALPHABET))
GRD_RE = re.compile(r'^grd_[%s]{14}$' % re.escape(_PUBLIC_ID_ALPHABET))


def test_generate_public_id_shape():
    pid = generate_public_id('usr')
    assert USR_RE.match(pid)
    # No ambiguous characters in the alphabet.
    assert not (set('0O1Il') & set(_PUBLIC_ID_ALPHABET))


def test_new_user_gets_opaque_prefixed_id(make_user):
    u = make_user(username='zoe')
    assert USR_RE.match(u.public_id), u.public_id
    assert not u.public_id.split('_', 1)[1].isdigit()  # not a simple numeric


def test_new_garden_gets_opaque_prefixed_id(make_user, db_session):
    owner = make_user(username='gowner')
    g = CommunityGarden(name='Opaque Garden', slug='opaque-garden', organizer_id=owner.id)
    db_session.add(g)
    db_session.commit()
    assert GRD_RE.match(g.public_id), g.public_id


def test_public_ids_are_unique(make_user):
    ids = {make_user(username=f'u{i}').public_id for i in range(25)}
    assert len(ids) == 25


def test_set_password_uses_scrypt(make_user):
    u = make_user(username='hashy', password='Password1')
    assert u.password_hash.startswith('scrypt:')
    assert PASSWORD_HASH_METHOD == 'scrypt'
    assert u.check_password('Password1')
    assert not u.needs_password_rehash()


def test_needs_rehash_for_legacy_hash(make_user):
    u = make_user(username='legacy')
    u.password_hash = generate_password_hash('Password1', method='pbkdf2:sha256')
    db.session.commit()
    assert u.password_hash.startswith('pbkdf2:')
    assert u.needs_password_rehash() is True


def test_login_upgrades_legacy_hash(client, make_user):
    u = make_user(username='upgrader', email='upgrader@example.com', password='Password1')
    # Force a legacy hash on disk.
    u.password_hash = generate_password_hash('Password1', method='pbkdf2:sha256')
    db.session.commit()
    assert u.needs_password_rehash()

    resp = login_via_api(client, 'upgrader@example.com', 'Password1')
    assert resp.status_code == 200

    refreshed = db.session.get(User, u.id)
    assert refreshed.password_hash.startswith('scrypt:')
    assert refreshed.needs_password_rehash() is False
    assert refreshed.check_password('Password1')


def test_resolve_garden_pk_helper(app, make_user, db_session):
    owner = make_user(username='resolver')
    g = CommunityGarden(name='Resolver Garden', slug='resolver-garden', organizer_id=owner.id)
    db_session.add(g)
    db_session.commit()

    from app.helpers import resolve_garden_pk
    with app.test_request_context():
        assert resolve_garden_pk(g.id) == g.id              # integer PK
        assert resolve_garden_pk(str(g.id)) == g.id          # numeric string PK
        assert resolve_garden_pk(g.public_id) == g.id        # opaque public_id
        with pytest.raises(NotFound):
            resolve_garden_pk('grd_doesNotExist99')


def test_garden_detail_endpoint_accepts_public_id_or_pk(client, make_user, db_session):
    owner = make_user(username='ghttp')
    g = CommunityGarden(name='Http Garden', slug='http-garden', organizer_id=owner.id)
    db_session.add(g)
    db_session.commit()

    by_pubid = client.get(f'/api/gardens/{g.public_id}')
    assert by_pubid.status_code == 200
    assert by_pubid.get_json()['public_id'] == g.public_id

    by_pk = client.get(f'/api/gardens/{g.id}')          # backward-compatible
    assert by_pk.status_code == 200
    assert by_pk.get_json()['public_id'] == g.public_id

    assert client.get('/api/gardens/grd_nope000000000').status_code == 404


def test_profile_endpoint_accepts_public_id_or_pk(client, make_user):
    u = make_user(username='phttp', email='phttp@example.com')
    assert client.get(f'/api/profile/{u.public_id}').status_code == 200
    assert client.get(f'/api/profile/{u.id}').status_code == 200
    assert client.get('/api/profile/usr_nope000000000').status_code == 404


def test_server_generated_links_use_public_id(client, make_user, db_session):
    """A server-generated notification link points at the opaque garden id."""
    from app.models import CommunityGarden, GardenPlot, Notification
    organizer = make_user(username='org2', email='org2@example.com')
    make_user(username='mem2', email='mem2@example.com', password='Password1')
    g = CommunityGarden(name='Notif Garden', slug='notif-garden', organizer_id=organizer.id)
    db_session.add(g)
    db_session.commit()
    plot = GardenPlot(garden_id=g.id, plot_number='P1', status='available')
    db_session.add(plot)
    db_session.commit()

    assert login_via_api(client, 'mem2@example.com', 'Password1').status_code == 200
    # Reserve via the OPAQUE garden url; the organizer gets a notification.
    r = client.post(f'/api/gardens/{g.public_id}/plots/{plot.id}/reserve')
    assert r.status_code == 200

    note = Notification.query.filter_by(user_id=organizer.id, type='plot_reserved').first()
    assert note is not None
    # The admin tab is a PATH segment in App.jsx (/gardens/:id/admin/:tab).
    # These links used `?tab=plots`, which the router ignores — every one of
    # them dropped the organizer on the Dashboard instead.
    assert note.link == f'/gardens/{g.public_id}/admin/plots'
    assert note.link.startswith('/gardens/grd_')
