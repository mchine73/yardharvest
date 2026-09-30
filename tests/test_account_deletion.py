"""Erasing an account.

The operation is irreversible and unattended, so these lean hard on the two
ways it could be wrong in opposite directions: erasing too little (personal
data survives, or the account can still sign in) and erasing too much (a
garden loses its organizer, a dues ledger loses a row a treasurer has to
reconcile, someone else's conversation loses half its messages).
"""
import pytest

from app import db as _db, account_deletion
from app.models import (CommunityGarden, GardenDuesRecord, GardenPlot,
                        GardenComment, Notification, User)

PASSWORD = 'Password1'   # the conftest factory's default


@pytest.fixture
def member(make_user):
    u = make_user(username='leaver', email='leaver@example.com')
    u.display_name = 'Dana Leaver'
    u.bio = 'I grow tomatoes'
    u.phone_number = '+14025551234'
    u.address = '12 Elm St'
    u.sms_opt_in = True
    _db.session.commit()
    return u



@pytest.fixture
def other_organizer(make_user):
    """Someone else's garden needs someone else to own it. Using member.id+9999
    passed on SQLite (foreign keys off by default) and failed on Postgres."""
    return make_user(username='owner', email='owner@example.com')

def login(client, email='leaver@example.com'):
    return client.post('/api/auth/login', json={'email': email, 'password': PASSWORD})


def delete(client, password=PASSWORD, confirm='DELETE'):
    return client.delete('/api/auth/account',
                         json={'password': password, 'confirm': confirm})


# ---------------------------------------------------------------------------
# The two gates
# ---------------------------------------------------------------------------
def test_the_wrong_password_deletes_nothing(client, member):
    login(client)
    r = delete(client, password='not-my-password')
    assert r.status_code == 403
    assert _db.session.get(User, member.id).deleted_at is None


def test_it_cannot_be_reached_by_clicking_through(client, member):
    """A typed confirmation, so a misclick on a destructive control does not
    erase an account."""
    login(client)
    r = delete(client, confirm='')
    assert r.status_code == 400
    assert _db.session.get(User, member.id).deleted_at is None


def test_a_signed_out_caller_cannot_delete_anyone(client, member):
    assert client.delete('/api/auth/account',
                         json={'password': PASSWORD, 'confirm': 'DELETE'}
                         ).status_code in (401, 403)


# ---------------------------------------------------------------------------
# Erasing enough
# ---------------------------------------------------------------------------
def test_personal_data_is_gone(client, member):
    login(client)
    assert delete(client).status_code == 200

    u = _db.session.get(User, member.id)
    assert u is not None, 'the row survives as a tombstone'
    assert u.deleted_at is not None
    assert u.display_name == account_deletion.TOMBSTONE_NAME
    assert u.bio is None and u.phone_number is None and u.address is None
    assert 'leaver@example.com' not in (u.email or '')
    assert u.email.endswith('@deleted.invalid')


def test_the_account_can_no_longer_sign_in(client, member):
    login(client)
    delete(client)
    client.post('/api/auth/logout')
    assert login(client).status_code != 200


def test_every_subscription_is_switched_off(client, member):
    """A deleted account still receiving the garden newsletter is the most
    visible way to get this wrong."""
    login(client)
    delete(client)
    u = _db.session.get(User, member.id)
    assert u.sms_opt_in is False
    assert u.email_messages is False and u.email_garden_announcements is False


def test_issued_tokens_stop_working(client, member):
    before = member.token_version or 0
    login(client)
    delete(client)
    assert _db.session.get(User, member.id).token_version > before


def test_private_artefacts_are_purged(client, member, app):
    login(client)
    _db.session.add(Notification(user_id=member.id, type='test', title='hello'))
    _db.session.commit()
    delete(client)
    assert Notification.query.filter_by(user_id=member.id).count() == 0


# ---------------------------------------------------------------------------
# Not erasing too much
# ---------------------------------------------------------------------------
def test_a_garden_organizer_is_refused_with_a_way_forward(client, make_user, member):
    """organizer_id is NOT NULL: erasing an owner would orphan the garden and
    everyone in it. The refusal has to say what to do, or it reads as the
    product refusing to let you leave."""
    g = CommunityGarden(name='Elm Street Garden', slug='elm-street-garden', organizer_id=member.id)
    _db.session.add(g)
    _db.session.commit()

    login(client)
    r = delete(client)
    assert r.status_code == 409
    body = r.get_json()
    assert 'Elm Street Garden' in body['error']
    assert 'transfer' in body['error'].lower()
    assert _db.session.get(User, member.id).deleted_at is None


def test_financial_records_survive(client, member, other_organizer, app):
    """Art. 17(3)(b): tax and accounting do not bend to an erasure request,
    and a treasurer still has to reconcile the season."""
    g = CommunityGarden(name='Other Garden', slug='other-garden', organizer_id=other_organizer.id)
    _db.session.add(g)
    _db.session.flush()
    _db.session.add(GardenDuesRecord(garden_id=g.id, user_id=member.id,
                                     amount_due=40.0, season_year=2026))
    _db.session.commit()

    login(client)
    assert delete(client).status_code == 200
    assert GardenDuesRecord.query.filter_by(user_id=member.id).count() == 1


def test_shared_conversation_keeps_its_content_and_loses_the_name(client, member, other_organizer):
    """A comment thread is a conversation. Deleting one side of it edits
    everyone else's history."""
    g = CommunityGarden(name='Thread Garden', slug='thread-garden', organizer_id=other_organizer.id)
    _db.session.add(g)
    _db.session.flush()
    _db.session.add(GardenComment(garden_id=g.id, author_id=member.id,
                                  body='The water is on Saturdays'))
    _db.session.commit()

    login(client)
    delete(client)

    c = GardenComment.query.filter_by(author_id=member.id).one()
    assert c.body == 'The water is on Saturdays'
    assert _db.session.get(User, c.author_id).display_name == account_deletion.TOMBSTONE_NAME


def test_a_held_plot_is_released(client, member, other_organizer):
    """A plot still assigned to a deleted account is a bed nobody can claim
    and a waitlist that never moves."""
    g = CommunityGarden(name='Plot Garden', slug='plot-garden', organizer_id=other_organizer.id)
    _db.session.add(g)
    _db.session.flush()
    p = GardenPlot(garden_id=g.id, plot_number='A1', assigned_to_id=member.id,
                   status='assigned')
    _db.session.add(p)
    _db.session.commit()

    login(client)
    delete(client)

    plot = _db.session.get(GardenPlot, p.id)
    assert plot.assigned_to_id is None
    assert plot.status == 'available'


# ---------------------------------------------------------------------------
# Telling people first
# ---------------------------------------------------------------------------
def test_the_check_says_what_will_happen_before_anything_is_destroyed(client, member):
    login(client)
    body = client.get('/api/auth/account/deletion-check').get_json()
    assert body['blockers'] == []
    assert any('dues' in s.lower() or 'payment' in s.lower() for s in body['retained'])
    assert any('profile' in s.lower() for s in body['removed'])


def test_the_check_surfaces_a_blocker_without_deleting(client, member):
    _db.session.add(CommunityGarden(name='Blocking Garden', slug='blocking-garden', organizer_id=member.id))
    _db.session.commit()
    login(client)
    body = client.get('/api/auth/account/deletion-check').get_json()
    assert len(body['blockers']) == 1
    assert _db.session.get(User, member.id).deleted_at is None

# ---------------------------------------------------------------------------
# Telling the person it happened
# ---------------------------------------------------------------------------
def test_the_person_is_told_at_the_address_being_erased(client, member, monkeypatch):
    """An erasure nobody is told about is indistinguishable from an account
    takeover, and this is the last moment the address exists."""
    sent = []
    import app.email_service as es
    monkeypatch.setattr(es, 'send_email',
                        lambda to, subject, html, **k: sent.append((to, subject, html)) or True)

    login(client)
    assert delete(client).status_code == 200

    assert len(sent) == 1
    to, subject, html = sent[0]
    assert to == 'leaver@example.com'          # the real address, pre-scrub
    assert 'deleted' in subject.lower()
    assert 'did not ask for this' in html      # the takeover case


def test_a_mail_failure_does_not_undo_the_erasure(client, member, monkeypatch):
    """Sent after the commit on purpose: the account is gone either way, and a
    half-deleted account is far worse than a missing email."""
    import app.email_service as es
    monkeypatch.setattr(es, 'send_email',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('mail down')))

    login(client)
    assert delete(client).status_code == 200
    assert _db.session.get(User, member.id).deleted_at is not None

