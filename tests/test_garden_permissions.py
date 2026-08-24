"""Garden roles grant real, bounded access.

Before this, every garden-admin check in the codebase was
`organizer_id == me or is_admin`, while the members tab told organizers that
appointing a co-organizer or treasurer handed over abilities. It handed over a
label. An organizer who stepped back had given away nothing.

Two failures matter in opposite directions, so both are asserted:

* under-granting — the organizer, or a delegate, cannot do their job;
* over-granting — a delegate reaches something that could cost the garden its
  money or its ownership.

The escalation tests are the ones to keep: a permission model whose weakest
member can promote themselves is not a permission model.
"""
import uuid

import pytest

from app import db as _db
from tests.conftest import login_via_api


ROLES = ('organizer', 'co_organizer', 'treasurer', 'volunteer_lead', 'member')


@pytest.fixture()
def garden(app, make_user):
    """One garden, one holder of each role, all on Garden Pro."""
    from app.models import (CommunityGarden, GardenMembership,
                            GardenSubscription)
    people = {}
    owner = make_user(username='owner', email='owner@example.com',
                      role='manager', password='GoodPass1')
    people['organizer'] = owner
    g = CommunityGarden(name='Roles Garden',
                        slug='roles-%s' % uuid.uuid4().hex[:8],
                        organizer_id=owner.id, subscription_status='active')
    _db.session.add(g)
    _db.session.flush()
    _db.session.add(GardenSubscription(garden_id=g.id, status='active'))

    for role in ROLES[1:]:
        u = make_user(username=role, email='%s@example.com' % role,
                      role='gardener', password='GoodPass1')
        people[role] = u
        _db.session.add(GardenMembership(garden_id=g.id, user_id=u.id, role=role))

    stranger = make_user(username='stranger', email='stranger@example.com',
                         role='gardener', password='GoodPass1')
    people['stranger'] = stranger
    _db.session.commit()
    return {'garden': g, 'id': g.id, 'public_id': g.public_id,
            'people': {k: v.id for k, v in people.items()}}


def as_(client, who):
    email = 'owner@example.com' if who == 'organizer' else '%s@example.com' % who
    assert login_via_api(client, email, 'GoodPass1').status_code == 200


def allowed(resp):
    """Did authorization pass?

    404 and 500 are treated as test bugs rather than answers: a typo'd URL
    returns 404, and "404 is not 403" would quietly report that a forbidden
    thing was permitted — which is the one direction these tests must never
    get wrong.
    """
    assert resp.status_code != 500, resp.get_data(as_text=True)[:300]
    assert resp.status_code != 404, 'wrong URL in the test, not a permission answer'
    return resp.status_code not in (401, 403)


# ---------------------------------------------------------------------------
# The map itself
# ---------------------------------------------------------------------------
def test_the_owner_holds_every_capability(app, garden):
    from app import garden_permissions as perms
    from app.models import User
    owner = _db.session.get(User, garden['people']['organizer'])
    assert perms.garden_role(owner, garden['garden']) == 'organizer'
    assert perms.capabilities_for(owner, garden['garden']) == frozenset(
        perms.ALL_CAPABILITIES)


@pytest.mark.parametrize('role,expected', [
    ('co_organizer', {'view', 'garden', 'people', 'content', 'events', 'shifts',
                      'resources', 'money', 'reports'}),
    ('treasurer', {'view', 'money', 'reports'}),
    ('volunteer_lead', {'view', 'events', 'shifts'}),
    ('member', set()),
])
def test_each_role_holds_exactly_its_set(app, garden, role, expected):
    from app import garden_permissions as perms
    from app.models import User
    user = _db.session.get(User, garden['people'][role])
    assert set(perms.capabilities_for(user, garden['garden'])) == expected


def test_someone_with_no_membership_holds_nothing(app, garden):
    from app import garden_permissions as perms
    from app.models import User
    stranger = _db.session.get(User, garden['people']['stranger'])
    assert perms.garden_role(stranger, garden['garden']) is None
    assert perms.capabilities_for(stranger, garden['garden']) == frozenset()


def test_an_unknown_capability_is_refused_rather_than_assumed(app, garden):
    """An endpoint asking for a capability that doesn't exist is a bug, and the
    safe reading of a bug in an authorization check is no."""
    from app import garden_permissions as perms
    from app.models import User
    owner = _db.session.get(User, garden['people']['organizer'])
    assert perms.can(owner, garden['garden'], 'not_a_capability') is False


def test_a_stale_organizer_membership_is_not_ownership(app, garden, make_user):
    """Ownership transfer leaves the old owner labelled 'organizer'. That row
    must not read as ownership, or a transfer would hand the garden to two
    people at once."""
    from app import garden_permissions as perms
    from app.models import GardenMembership, User
    usurper = make_user(username='usurper', email='usurper@example.com',
                        role='gardener', password='GoodPass1')
    _db.session.add(GardenMembership(garden_id=garden['id'], user_id=usurper.id,
                                     role='organizer'))
    _db.session.commit()

    u = _db.session.get(User, usurper.id)
    assert perms.garden_role(u, garden['garden']) == 'co_organizer'
    assert not perms.can(u, garden['garden'], perms.BILLING)
    assert not perms.can(u, garden['garden'], perms.ROLES)


# ---------------------------------------------------------------------------
# Nothing the organizer could do before has been taken away
# ---------------------------------------------------------------------------
ORGANIZER_SURFACES = [
    ('GET', '/api/garden-admin/{id}/dashboard'),
    ('GET', '/api/garden-admin/{id}/plots'),
    ('GET', '/api/garden-admin/{id}/members'),
    ('GET', '/api/garden-admin/{id}/dues'),
    ('GET', '/api/garden-admin/{id}/expenses'),
    ('GET', '/api/garden-admin/{id}/finance-summary'),
    ('GET', '/api/garden-admin/{id}/finance/activity'),
    ('GET', '/api/garden-admin/{id}/announcements'),
    ('GET', '/api/garden-admin/{id}/photos'),
    ('GET', '/api/garden-admin/{id}/messages'),
    ('GET', '/api/garden-admin/{id}/weather'),
    ('GET', '/api/gardens/{id}/waitlist'),
]


@pytest.mark.parametrize('method,path', ORGANIZER_SURFACES)
def test_the_organizer_keeps_everything(client, app, garden, method, path):
    as_(client, 'organizer')
    resp = client.open(path.format(id=garden['id']), method=method)
    assert allowed(resp), '%s %s became forbidden for the owner' % (method, path)


# ---------------------------------------------------------------------------
# Delegates reach their own work
# ---------------------------------------------------------------------------
def test_a_treasurer_can_do_the_books(client, app, garden):
    as_(client, 'treasurer')
    gid = garden['id']
    for path in ('/api/garden-admin/%d/dues' % gid,
                 '/api/garden-admin/%d/expenses' % gid,
                 '/api/garden-admin/%d/finance-summary' % gid,
                 '/api/garden-admin/%d/finance/activity' % gid,
                 '/api/garden-admin/%d/dashboard' % gid):
        assert allowed(client.get(path)), path


def test_a_volunteer_lead_can_run_shifts_and_events(client, app, garden):
    as_(client, 'volunteer_lead')
    gid = garden['id']
    assert allowed(client.post('/api/garden-admin/%d/shifts' % gid, json={
        'title': 'Watering', 'shift_date': '2026-09-01',
        'start_time': '09:00', 'end_time': '11:00'}))
    assert allowed(client.get('/api/garden-admin/%d/dashboard' % gid))


def test_a_co_organizer_can_run_the_garden(client, app, garden):
    as_(client, 'co_organizer')
    gid = garden['id']
    for path in ('/api/garden-admin/%d/plots' % gid,
                 '/api/garden-admin/%d/members' % gid,
                 '/api/garden-admin/%d/dues' % gid,
                 '/api/garden-admin/%d/announcements' % gid,
                 '/api/garden-admin/%d/photos' % gid):
        assert allowed(client.get(path)), path


# ---------------------------------------------------------------------------
# And no further
# ---------------------------------------------------------------------------
def test_a_treasurer_cannot_touch_plots_or_the_roster(client, app, garden):
    as_(client, 'treasurer')
    gid = garden['id']
    assert not allowed(client.get('/api/garden-admin/%d/plots' % gid))
    assert not allowed(client.get('/api/garden-admin/%d/members' % gid))
    assert not allowed(client.get('/api/garden-admin/%d/announcements' % gid))


def test_a_volunteer_lead_cannot_see_the_money(client, app, garden):
    as_(client, 'volunteer_lead')
    gid = garden['id']
    assert not allowed(client.get('/api/garden-admin/%d/dues' % gid))
    assert not allowed(client.get('/api/garden-admin/%d/finance/activity' % gid))
    assert not allowed(client.get('/api/garden-admin/%d/members' % gid))


def test_a_plain_member_reaches_nothing(client, app, garden):
    as_(client, 'member')
    gid = garden['id']
    for path in ('/api/garden-admin/%d/dashboard' % gid,
                 '/api/garden-admin/%d/plots' % gid,
                 '/api/garden-admin/%d/dues' % gid):
        assert not allowed(client.get(path)), path


def test_a_denial_says_which_permission_is_missing(client, app, garden):
    """"Not authorized" on a portal you can see half of is maddening."""
    as_(client, 'volunteer_lead')
    body = client.get('/api/garden-admin/%d/dues' % garden['id']).get_json()
    assert body['reason'] == 'missing_capability'
    assert body['capability'] == 'money'
    assert body['your_role'] == 'volunteer_lead'


# ---------------------------------------------------------------------------
# Escalation
# ---------------------------------------------------------------------------
def test_a_co_organizer_cannot_hand_out_roles(client, app, garden):
    """Whoever can edit roles can grant every other capability, so this is the
    hinge the whole model turns on."""
    as_(client, 'co_organizer')
    resp = client.post('/api/garden-admin/%d/members/%d/role'
                       % (garden['id'], garden['people']['member']),
                       json={'role': 'co_organizer'})
    assert not allowed(resp)


def test_nobody_can_be_made_organizer_through_the_roles_endpoint(client, app, garden):
    """Ownership follows CommunityGarden.organizer_id. If this endpoint could
    write 'organizer', role editing would become a way to seize a garden."""
    as_(client, 'organizer')
    resp = client.post('/api/garden-admin/%d/members/%d/role'
                       % (garden['id'], garden['people']['co_organizer']),
                       json={'role': 'organizer'})
    assert resp.status_code == 400
    assert 'organizer' not in resp.get_json().get('assignable', [])


def test_the_owners_own_role_cannot_be_edited_away(client, app, garden):
    as_(client, 'organizer')
    resp = client.post('/api/garden-admin/%d/members/%d/role'
                       % (garden['id'], garden['people']['organizer']),
                       json={'role': 'member'})
    assert resp.status_code == 400

    from app import garden_permissions as perms
    from app.models import User
    owner = _db.session.get(User, garden['people']['organizer'])
    assert perms.garden_role(owner, garden['garden']) == 'organizer'


def test_a_co_organizer_cannot_redirect_the_gardens_money(client, app, garden):
    """The one delegation that could actually cost a garden its funds: billing
    and payout setup decide whose bank account the money lands in."""
    as_(client, 'co_organizer')
    gid = garden['id']
    assert not allowed(client.get('/api/gardens/%d/payouts/status' % gid))
    assert not allowed(client.post('/api/gardens/%d/payouts/connect' % gid,
                                   json={}))


def test_a_co_organizer_can_still_take_and_see_money(client, app, garden):
    """The boundary is *where the money goes*, not whether they can work with
    it — otherwise delegation is useless."""
    as_(client, 'co_organizer')
    assert allowed(client.get('/api/garden-admin/%d/finance/activity' % garden['id']))
    assert allowed(client.get('/api/garden-admin/%d/dues' % garden['id']))


# ---------------------------------------------------------------------------
# What the client is told
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('role,expect_portal', [
    ('organizer', True), ('co_organizer', True), ('treasurer', True),
    ('volunteer_lead', True), ('member', False), ('stranger', False),
])
def test_the_garden_payload_reports_the_viewers_access(client, app, garden,
                                                       role, expect_portal):
    """The SPA routes on this, so it has to match what the API will actually
    allow — a portal link that 403s is worse than no link."""
    as_(client, role)
    body = client.get('/api/gardens/%d' % garden['id']).get_json()
    caps = body['user_capabilities']
    assert ('view' in caps) is expect_portal
    if role in ('organizer', 'co_organizer', 'treasurer', 'volunteer_lead'):
        assert body['user_garden_role'] == role
    assert body['user_is_organizer'] is (role == 'organizer')
    # Only the owner is ever told they can touch billing.
    assert ('billing' in caps) is (role == 'organizer')
