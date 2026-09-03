"""Inbound STOP / START / HELP, recorded against the member who sent it.

Twilio handles these keywords itself — blocking or unblocking the number and
sending the standard reply — and also posts the message here tagged with
`OptOutType`, so the application can keep its own record straight. Two rules
follow from that, and both are asserted below:

* **Never reply.** Twilio already did. A second message arrives right behind
  its own, on a number whose 10DLC registration depends on clean opt-out
  behavior.
* **Never act on an unsigned request.** A forged opt-*in* would resume
  messaging someone who asked us to stop, which is the direction that
  actually matters.
"""
from unittest.mock import patch

import pytest

from app import db as _db


ENDPOINT = '/api/webhooks/twilio/sms'


@pytest.fixture()
def member(make_user):
    user = make_user(username='texter', email='texter@example.com')
    user.phone_number = '+14025551234'
    user.sms_opt_in = True
    _db.session.commit()
    return user


def post(client, **form):
    """Post as Twilio would, with signature verification satisfied."""
    with patch('app.api.webhook_api._twilio_signature_ok', return_value=True):
        return client.post(ENDPOINT, data=form)


def opted_in(email='texter@example.com'):
    from app.models import User
    return User.query.filter_by(email=email).one().sms_opt_in


# ---------------------------------------------------------------------------
# Signature
# ---------------------------------------------------------------------------
def test_an_unsigned_request_changes_nothing(client, app, member):
    """The whole endpoint hangs on this. Without it, anyone who found the URL
    could opt a member back in after they had asked us to stop."""
    resp = client.post(ENDPOINT, data={'From': '+14025551234', 'Body': 'STOP'})
    assert resp.status_code == 403
    assert opted_in() is True


def test_a_forged_opt_in_is_refused(client, app, member):
    """The direction that matters: silencing us is a nuisance, resuming
    messages to someone who said no is the actual harm."""
    member.sms_opt_in = False
    _db.session.commit()

    resp = client.post(ENDPOINT, data={'From': '+14025551234',
                                       'Body': 'START',
                                       'OptOutType': 'START'})
    assert resp.status_code == 403
    assert opted_in() is False


def test_verification_is_refused_when_no_token_is_configured(client, app, monkeypatch):
    """An unverifiable request is not a trusted one."""
    monkeypatch.delenv('TWILIO_AUTH_TOKEN', raising=False)
    resp = client.post(ENDPOINT, data={'From': '+1402', 'Body': 'STOP'},
                       headers={'X-Twilio-Signature': 'anything'})
    assert resp.status_code == 403


def test_a_genuinely_signed_request_is_accepted(client, app, member, monkeypatch):
    """The tests above patch verification out, so exercise the real validator
    once with a signature computed the way Twilio computes it. Otherwise the
    one security control here is the only untested line in the file."""
    from twilio.request_validator import RequestValidator

    token = 'test_auth_token'
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', token)
    params = {'From': '+14025551234', 'Body': 'STOP', 'OptOutType': 'STOP'}
    url = 'http://localhost' + ENDPOINT
    signature = RequestValidator(token).compute_signature(url, params)

    resp = client.post(ENDPOINT, data=params,
                       headers={'X-Twilio-Signature': signature})
    assert resp.status_code == 200
    assert opted_in() is False


def test_a_tampered_signed_request_is_refused(client, app, member, monkeypatch):
    """Signed for one payload, sent with another."""
    from twilio.request_validator import RequestValidator

    token = 'test_auth_token'
    monkeypatch.setenv('TWILIO_AUTH_TOKEN', token)
    url = 'http://localhost' + ENDPOINT
    signature = RequestValidator(token).compute_signature(
        url, {'From': '+14025551234', 'Body': 'HELP'})

    resp = client.post(ENDPOINT,
                       data={'From': '+14025551234', 'Body': 'STOP'},
                       headers={'X-Twilio-Signature': signature})
    assert resp.status_code == 403
    assert opted_in() is True


# ---------------------------------------------------------------------------
# Keywords
# ---------------------------------------------------------------------------
def test_stop_clears_the_opt_in(client, app, member):
    resp = post(client, From='+14025551234', Body='STOP', OptOutType='STOP')
    assert resp.status_code == 200
    assert opted_in() is False


def test_start_restores_it(client, app, member):
    """Texting START is affirmative consent — it restores a preference the
    sender themselves turned off."""
    member.sms_opt_in = False
    _db.session.commit()

    post(client, From='+14025551234', Body='START', OptOutType='START')
    assert opted_in() is True


def test_help_changes_no_preference(client, app, member):
    post(client, From='+14025551234', Body='HELP', OptOutType='HELP')
    assert opted_in() is True


@pytest.mark.parametrize('word', ['STOP', 'stop', 'Unsubscribe', 'CANCEL',
                                  'quit', 'END', 'STOPALL'])
def test_every_stop_word_counts_without_twilios_tag(client, app, member, word):
    """A bare long code does not send OptOutType, so the body is the fallback
    and the two must never disagree about what a message meant."""
    post(client, From='+14025551234', Body=word)
    assert opted_in() is False


def test_an_ordinary_message_is_left_alone(client, app, member):
    """We are not a two-way channel; a real message must not be read as a
    command."""
    post(client, From='+14025551234',
         Body='is the water on this weekend?')
    assert opted_in() is True


def test_a_number_we_do_not_know_is_harmless(client, app, member):
    resp = post(client, From='+15559998888', Body='STOP', OptOutType='STOP')
    assert resp.status_code == 200
    assert opted_in() is True


def test_a_member_stored_in_the_old_format_is_still_matched(client, app, make_user):
    """Before the backfill runs, stored numbers are whatever people typed —
    and that is exactly when the first STOP arrives."""
    from app.models import User
    user = make_user(username='oldfmt', email='oldfmt@example.com')
    user.phone_number = '(402) 555-7777'
    user.sms_opt_in = True
    _db.session.commit()

    post(client, From='+14025557777', Body='STOP', OptOutType='STOP')
    assert User.query.filter_by(email='oldfmt@example.com').one().sms_opt_in is False


# ---------------------------------------------------------------------------
# The reply
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('body', ['STOP', 'START', 'HELP', 'hello there'])
def test_we_never_send_a_message_back(client, app, member, body):
    """Twilio has already replied. Anything in this TwiML arrives as a second
    text right behind its own."""
    resp = post(client, From='+14025551234', Body=body)
    xml = resp.get_data(as_text=True)
    assert 'text/xml' in resp.content_type
    assert '<Message' not in xml
    assert xml.strip().endswith('<Response></Response>')


def test_a_failure_still_answers_twilio(client, app, member):
    """A 500 makes Twilio retry, and a retry cannot fix a bug in here — the
    keyword already took effect on their side regardless."""
    from app import sms_service
    with patch.object(sms_service, 'set_opt_in', side_effect=RuntimeError('boom')):
        resp = post(client, From='+14025551234', Body='STOP', OptOutType='STOP')
    assert resp.status_code == 200
