"""Phone numbers Twilio will actually accept, and STOP that actually sticks.

Two gaps found the day SMS went live:

* Nothing put stored numbers into E.164. A member who typed "402-555-1234"
  during signup was stored exactly like that, and Twilio answers with error
  21211 — which reads like a configuration fault rather than a data one. They
  tick the SMS box, believe they are subscribed, and never hear anything.
* Nothing handled STOP. Twilio blocks an opted-out recipient at the carrier
  and returns 21610, but `sms_opt_in` stayed true, so every later send tried
  again. That is a lie in the member's own preferences and, on a 10DLC number,
  the behavior that gets a sender flagged.
"""
from unittest.mock import MagicMock, patch

import pytest

from app import db as _db
from tests.conftest import login_via_api


# ---------------------------------------------------------------------------
# Normalizing
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('raw,expected', [
    ('4025551234', '+14025551234'),          # the common case: bare US ten
    ('402-555-1234', '+14025551234'),
    ('(402) 555-1234', '+14025551234'),
    ('402.555.1234', '+14025551234'),
    ('  402 555 1234  ', '+14025551234'),
    ('14025551234', '+14025551234'),         # eleven with the country code
    ('+1 402 555 1234', '+14025551234'),
    ('+14025551234', '+14025551234'),        # already right, left alone
    ('+442071838750', '+442071838750'),      # international, carries its own +
])
def test_numbers_people_actually_type(raw, expected):
    from app.sms_service import normalize_phone
    assert normalize_phone(raw) == expected


@pytest.mark.parametrize('raw', [
    '', None, '   ', 'not a phone', '555-1234',   # too short to place
    '02071838750',                                # international without a +
    '+0123456789',                                # E.164 cannot start with 0
    '123456789012345678',                         # too long
])
def test_a_number_we_cannot_read_is_refused_not_guessed(raw):
    """Guessing at a number is how you text a stranger."""
    from app.sms_service import normalize_phone
    assert normalize_phone(raw) is None


# ---------------------------------------------------------------------------
# Where numbers are written
# ---------------------------------------------------------------------------
def test_registration_stores_a_typed_number_in_e164(client, app):
    from app.models import User
    resp = client.post('/api/auth/register', json={
        'username': 'dialme', 'email': 'dialme@example.com',
        'password': 'GoodPass1', 'role': 'gardener',
        'phone_number': '(402) 555-9876', 'sms_opt_in': True})
    assert resp.status_code in (200, 201), resp.get_json()
    user = User.query.filter_by(email='dialme@example.com').one()
    assert user.phone_number == '+14025559876'


def test_registration_refuses_a_number_it_cannot_dial(client, app):
    """Creating the account anyway produces someone who opted into SMS and
    will never hear anything."""
    from app.models import User
    resp = client.post('/api/auth/register', json={
        'username': 'bogus', 'email': 'bogus@example.com',
        'password': 'GoodPass1', 'role': 'gardener',
        'phone_number': 'call me maybe', 'sms_opt_in': True})
    assert resp.status_code == 400
    assert 'country code' in resp.get_json()['error']
    assert User.query.filter_by(email='bogus@example.com').first() is None


def test_registration_without_a_phone_is_still_fine(client, app):
    """It is an optional field and must stay one."""
    resp = client.post('/api/auth/register', json={
        'username': 'nophone', 'email': 'nophone@example.com',
        'password': 'GoodPass1', 'role': 'gardener'})
    assert resp.status_code in (200, 201), resp.get_json()


def test_notification_preferences_normalize_too(client, app, make_user):
    from app.models import User
    make_user(username='prefs', email='prefs@example.com', password='GoodPass1')
    login_via_api(client, 'prefs@example.com', 'GoodPass1')

    assert client.put('/api/notifications/preferences',
                      json={'phone_number': '402-555-0000'}).status_code == 200
    assert User.query.filter_by(email='prefs@example.com').one().phone_number \
        == '+14025550000'

    bad = client.put('/api/notifications/preferences',
                     json={'phone_number': 'nope'})
    assert bad.status_code == 400
    # The rejected value must not have overwritten the good one.
    assert User.query.filter_by(email='prefs@example.com').one().phone_number \
        == '+14025550000'


def test_clearing_the_number_is_allowed(client, app, make_user):
    from app.models import User
    u = make_user(username='clearme', email='clearme@example.com',
                  password='GoodPass1')
    u.phone_number = '+14025551234'
    _db.session.commit()
    login_via_api(client, 'clearme@example.com', 'GoodPass1')

    assert client.put('/api/notifications/preferences',
                      json={'phone_number': ''}).status_code == 200
    assert User.query.filter_by(email='clearme@example.com').one().phone_number == ''


# ---------------------------------------------------------------------------
# Sending
# ---------------------------------------------------------------------------
def configured(monkeypatch):
    monkeypatch.setenv('TWILIO_ACCOUNT_SID', 'ACtest')
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', 'tok')
    monkeypatch.setenv('TWILIO_PHONE_NUMBER', '+15005550006')


def opted_in_member(make_user, phone, *, username='sendee'):
    user = make_user(username=username, email='%s@example.com' % username)
    user.phone_number = phone
    user.sms_opt_in = True
    _db.session.commit()
    return user


def test_a_legacy_number_is_normalized_at_send(app, monkeypatch, make_user):
    """Rows written before any of this still hold whatever was typed."""
    from app import sms_service
    opted_in_member(make_user, '402-555-1234')
    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('402-555-1234', 'hello') is True
    assert client.messages.create.call_args.kwargs['to'] == '+14025551234'


def test_an_unusable_number_never_reaches_twilio(app, monkeypatch):
    from app import sms_service
    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('call me maybe', 'hello') is False
    client.messages.create.assert_not_called()


# ---------------------------------------------------------------------------
# The consent backstop
# ---------------------------------------------------------------------------
# Every call site already checks sms_opt_in. This is the last line: fourteen
# copies of one rule is the shape that has drifted here five times, and consent
# is a worse thing to drift on than a price.

def test_a_member_who_opted_out_is_not_texted(app, monkeypatch, make_user):
    from app import sms_service
    user = opted_in_member(make_user, '+14025551234')
    user.sms_opt_in = False
    _db.session.commit()

    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('+14025551234', 'hello') is False
    client.messages.create.assert_not_called()


def test_a_number_belonging_to_nobody_is_refused(app, db_session, monkeypatch):
    """Fails closed. Every real send goes to a member, so no match is either a
    bug or a deliberate send that should say so."""
    from app import sms_service
    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('+15559990000', 'hello') is False
    client.messages.create.assert_not_called()


def test_a_deliberate_send_can_say_so(app, db_session, monkeypatch):
    """The admin's test message names its own recipient; it is not acting on
    anyone's stored preference. Without this the tool used to prove the
    integration works would be blocked by the integration."""
    from app import sms_service
    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('+15559990000', 'test',
                                    require_opt_in=False) is True
    client.messages.create.assert_called_once()


def test_the_backstop_matches_however_the_number_was_stored(app, monkeypatch,
                                                            make_user):
    """A member stored as they typed it must not be refused as a stranger."""
    from app import sms_service
    opted_in_member(make_user, '(402) 555-4444')
    configured(monkeypatch)
    client = MagicMock()
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('+14025554444', 'hello') is True


# ---------------------------------------------------------------------------
# STOP
# ---------------------------------------------------------------------------
class TwilioError(Exception):
    def __init__(self, code):
        super().__init__('twilio said no (%s)' % code)
        self.code = code


def test_a_stop_reply_clears_the_opt_in(app, monkeypatch, make_user):
    """Otherwise the member's own preferences claim they are subscribed while
    the carrier blocks every message — and we keep trying forever."""
    from app import sms_service
    from app.models import User
    user = make_user(username='stopper', email='stopper@example.com')
    user.phone_number = '+14025551234'
    user.sms_opt_in = True
    _db.session.commit()

    configured(monkeypatch)
    client = MagicMock()
    client.messages.create.side_effect = TwilioError(sms_service.STOP_REPLY)
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        assert sms_service.send_sms('+14025551234', 'hello') is False

    assert User.query.filter_by(email='stopper@example.com').one().sms_opt_in is False


def test_a_stop_reply_finds_a_member_stored_in_the_old_format(app, monkeypatch,
                                                              make_user):
    """Suppression has to work before the backfill has run, or the first STOP
    after go-live is ignored."""
    from app import sms_service
    from app.models import User
    user = make_user(username='oldfmt', email='oldfmt@example.com')
    user.phone_number = '402-555-1234'      # never normalized
    user.sms_opt_in = True
    _db.session.commit()

    configured(monkeypatch)
    client = MagicMock()
    client.messages.create.side_effect = TwilioError(sms_service.STOP_REPLY)
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        sms_service.send_sms('402-555-1234', 'hello')

    assert User.query.filter_by(email='oldfmt@example.com').one().sms_opt_in is False


def test_an_invalid_number_does_not_opt_anyone_out(app, monkeypatch, make_user):
    """21211 is a data problem, not a consent one. Treating it as consent
    would silently unsubscribe people over a typo."""
    from app import sms_service
    from app.models import User
    user = make_user(username='typo', email='typo@example.com')
    user.phone_number = '+14025551234'
    user.sms_opt_in = True
    _db.session.commit()

    configured(monkeypatch)
    client = MagicMock()
    client.messages.create.side_effect = TwilioError(sms_service.INVALID_NUMBER)
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        sms_service.send_sms('+14025551234', 'hello')

    assert User.query.filter_by(email='typo@example.com').one().sms_opt_in is True


def test_an_ordinary_failure_changes_nothing(app, monkeypatch, make_user):
    from app import sms_service
    from app.models import User
    user = make_user(username='blip', email='blip@example.com')
    user.phone_number = '+14025551234'
    user.sms_opt_in = True
    _db.session.commit()

    configured(monkeypatch)
    client = MagicMock()
    client.messages.create.side_effect = TwilioError(30001)   # queue overflow
    with patch.object(sms_service, 'TwilioClient', return_value=client):
        sms_service.send_sms('+14025551234', 'hello')

    assert User.query.filter_by(email='blip@example.com').one().sms_opt_in is True


# ---------------------------------------------------------------------------
# The backfill
# ---------------------------------------------------------------------------
def test_the_backfill_repairs_existing_rows(app, make_user):
    from app.models import User
    a = make_user(username='a1', email='a1@example.com')
    a.phone_number = '(402) 555-1111'
    b = make_user(username='b1', email='b1@example.com')
    b.phone_number = '+14025552222'          # already fine
    c = make_user(username='c1', email='c1@example.com')
    c.phone_number = 'gibberish'
    _db.session.commit()

    result = app.test_cli_runner().invoke(args=['normalize-phone-numbers'])
    assert result.exit_code == 0, result.output
    assert 'Normalized 1' in result.output
    assert '1 already fine' in result.output
    assert '1 unreadable' in result.output

    assert User.query.filter_by(email='a1@example.com').one().phone_number \
        == '+14025551111'
    # Left exactly as found — a human has to look at it.
    assert User.query.filter_by(email='c1@example.com').one().phone_number == 'gibberish'


def test_the_backfill_dry_run_writes_nothing(app, make_user):
    from app.models import User
    u = make_user(username='d1', email='d1@example.com')
    u.phone_number = '402-555-3333'
    _db.session.commit()

    result = app.test_cli_runner().invoke(
        args=['normalize-phone-numbers', '--dry-run'])
    assert 'Dry run' in result.output
    assert User.query.filter_by(email='d1@example.com').one().phone_number \
        == '402-555-3333'


def test_the_backfill_flags_an_opted_in_member_it_cannot_repair(app, make_user):
    """The ones that matter: they believe they are subscribed."""
    u = make_user(username='e1', email='e1@example.com')
    u.phone_number = 'call me'
    u.sms_opt_in = True
    _db.session.commit()

    result = app.test_cli_runner().invoke(
        args=['normalize-phone-numbers', '--dry-run'])
    assert 'will never receive SMS' in result.output
