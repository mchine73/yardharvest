"""A treasurer can take Tap to Pay — and the reader lands on the right account.

The failure this guards against was found with a real card: the connection
token followed the signed-in user while the PaymentIntent followed the
garden's payout account, and Stripe answered "No such payment_intent". The
fix scopes the Terminal session to the GARDEN'S payout account for anyone
holding the MONEY capability. These tests pin both halves:

* the capability gate — money roles pass, non-money roles get a 403 that
  says so, not a Stripe error three steps later;
* the account scoping — whoever the collector is, the token and the charge
  are created on the organizer's connected account, because that is the
  account the money must land in.
"""
import uuid

import pytest

from app import db as _db
from tests.conftest import login_via_api


ORG_ACCT = 'acct_ORGANIZER'


@pytest.fixture()
def garden(app, make_user):
    """A Pro garden whose organizer has a Stripe account, plus one holder of
    each assignable role. Only the organizer has any Stripe identity — the
    point is that nobody else needs one."""
    from app.models import (CommunityGarden, GardenMembership,
                            GardenSubscription)
    people = {}
    owner = make_user(username='towner', email='towner@example.com',
                      role='manager', password='GoodPass1')
    owner.stripe_connect_account_id = ORG_ACCT
    people['organizer'] = owner
    g = CommunityGarden(name='Treasury Garden',
                        slug='treasury-%s' % uuid.uuid4().hex[:8],
                        organizer_id=owner.id, subscription_status='active')
    _db.session.add(g)
    _db.session.flush()
    _db.session.add(GardenSubscription(garden_id=g.id, status='active'))

    for role in ('co_organizer', 'treasurer', 'volunteer_lead', 'member'):
        u = make_user(username='t_%s' % role, email='t_%s@example.com' % role,
                      role='gardener', password='GoodPass1')
        people[role] = u
        _db.session.add(GardenMembership(garden_id=g.id, user_id=u.id, role=role))
    _db.session.commit()
    return {'garden': g, 'id': g.id, 'people': people}


def as_(client, who):
    email = ('towner@example.com' if who == 'organizer'
             else 't_%s@example.com' % who)
    assert login_via_api(client, email, 'GoodPass1').status_code == 200


@pytest.fixture()
def stripe_ok(monkeypatch):
    """Stripe says yes to everything, and records what it was asked."""
    from app import stripe_service
    calls = {'token_account': None, 'pi_kwargs': None}

    monkeypatch.setattr(stripe_service, 'is_configured', lambda: True)
    monkeypatch.setattr(stripe_service, 'get_connect_account',
                        lambda user: (object(), None))
    monkeypatch.setattr(stripe_service, 'connect_account_ready',
                        lambda user, acct=None: True)
    monkeypatch.setattr(stripe_service, 'card_present_capability_status',
                        lambda user, acct=None: ('active', None))
    monkeypatch.setattr(stripe_service, 'connect_card_present_ready',
                        lambda user, acct=None: True)
    monkeypatch.setattr(stripe_service, 'ensure_terminal_location',
                        lambda user, acct=None: 'tml_TEST')

    import stripe

    class FakeToken:
        secret = 'pst_test_secret'

    def fake_token_create(**kwargs):
        calls['token_account'] = kwargs.get('stripe_account')
        return FakeToken()

    class FakePI:
        id = 'pi_TEST'
        client_secret = 'pi_TEST_secret'

    def fake_pi_create(**kwargs):
        calls['pi_kwargs'] = kwargs
        return FakePI()

    monkeypatch.setattr(stripe.terminal.ConnectionToken, 'create',
                        staticmethod(fake_token_create))
    monkeypatch.setattr(stripe.PaymentIntent, 'create',
                        staticmethod(fake_pi_create))
    return calls


TOKEN_URL = '/api/garden-admin/terminal/connection_token'


# ---------------------------------------------------------------------------
# The capability gate
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('who', ['organizer', 'co_organizer', 'treasurer'])
def test_money_roles_get_a_terminal_session(client, garden, stripe_ok, who):
    as_(client, who)
    r = client.post(TOKEN_URL, json={'garden_id': garden['id']})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    body = r.get_json()
    assert body['secret'] == 'pst_test_secret'
    assert body['location_id'] == 'tml_TEST'


@pytest.mark.parametrize('who', ['volunteer_lead', 'member'])
def test_non_money_roles_are_told_why(client, garden, stripe_ok, who):
    as_(client, who)
    r = client.post(TOKEN_URL, json={'garden_id': garden['id']})
    assert r.status_code == 403
    assert r.get_json()['reason'] == 'money_capability_required'
    # And Stripe was never asked for anything.
    assert stripe_ok['token_account'] is None


# ---------------------------------------------------------------------------
# The account scoping — the actual bug this feature exists to prevent
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('who', ['treasurer', 'co_organizer', 'organizer'])
def test_the_token_lands_on_the_gardens_payout_account(client, garden,
                                                       stripe_ok, who):
    as_(client, who)
    r = client.post(TOKEN_URL, json={'garden_id': garden['id']})
    assert r.status_code == 200
    assert stripe_ok['token_account'] == ORG_ACCT, (
        'the reader session must live on the garden payout account, whoever '
        'is holding the phone — otherwise the PaymentIntent is invisible to it')


def test_without_garden_id_the_old_organizer_path_survives(client, garden,
                                                           stripe_ok):
    """Old app builds send no garden_id; they get the collector's own account,
    which only ever worked for the organizer — unchanged behavior."""
    as_(client, 'organizer')
    r = client.post(TOKEN_URL, json={})
    assert r.status_code == 200
    assert stripe_ok['token_account'] == ORG_ACCT


def test_a_treasurer_charge_is_created_on_the_organizer_account(client, garden,
                                                                stripe_ok):
    from app.models import GardenDuesRecord
    rec = GardenDuesRecord(garden_id=garden['id'],
                           user_id=garden['people']['member'].id,
                           season_year=2026, amount_due=40.0, amount_paid=0.0,
                           status='unpaid')
    _db.session.add(rec)
    _db.session.commit()

    as_(client, 'treasurer')
    r = client.post('/api/garden-admin/%s/dues/%s/collect-in-person'
                    % (garden['id'], rec.id))
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert stripe_ok['pi_kwargs'] is not None
    assert stripe_ok['pi_kwargs'].get('stripe_account') == ORG_ACCT, (
        'the charge must be a direct charge on the garden payout account')
