"""ZeptoMail bounce/complaint webhook -> auto-suppress dead/complaining addrs.

The webhook parses ZeptoMail's (loosely-specified) payload tolerantly: hard
bounces and spam complaints land on the global suppression list, while soft
bounces, opens, and unrecognized shapes are acknowledged but ignored.
"""
from app import db as _db


def _post(client, payload, **kwargs):
    return client.post('/api/webhooks/zeptomail', json=payload, **kwargs)


def test_hard_bounce_is_suppressed(client, app):
    from app.models import EmailUnsubscribe
    payload = {
        'event_name': 'bounce',
        'event_message': [{
            'details': [{
                'event': 'HardBounce',
                'bounced_recipient': 'dead@example.com',
                'reason': '550 5.1.1 user unknown',
            }],
            # 'from' must NOT be harvested as a recipient.
            'email_info': {
                'from': {'address': 'james@yardharvest.app'},
                'to': [{'email_address': {'address': 'dead@example.com'}}],
            },
        }],
    }
    r = _post(client, payload)
    assert r.status_code == 200
    assert r.get_json()['suppressed'] == 1
    with app.app_context():
        row = EmailUnsubscribe.query.filter_by(email='dead@example.com').first()
        assert row is not None and row.source == 'bounce'
        # The sender address is never suppressed.
        assert EmailUnsubscribe.query.filter_by(email='james@yardharvest.app').first() is None


def test_soft_bounce_is_not_suppressed(client, app):
    from app.models import EmailUnsubscribe
    payload = {
        'event_name': 'softbounce',
        'event_message': [{'details': [{
            'event': 'SoftBounce',
            'bounced_recipient': 'slow@example.com',
        }]}],
    }
    r = _post(client, payload)
    assert r.status_code == 200 and r.get_json()['suppressed'] == 0
    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email='slow@example.com').first() is None


def test_complaint_suppresses_and_opts_out_contact(client, app):
    from app.models import EmailUnsubscribe
    from app.crm.models import Contact
    with app.app_context():
        c = Contact(name='Angry', email='Angry@Example.com', email_opt_out=False)
        _db.session.add(c)
        _db.session.commit()
        cid = c.id

    payload = {
        'event_name': 'complaint',
        'event_message': [{'details': [{
            'event': 'Complaint',
            'recipient': 'angry@example.com',
        }]}],
    }
    r = _post(client, payload)
    assert r.status_code == 200 and r.get_json()['suppressed'] == 1
    with app.app_context():
        row = EmailUnsubscribe.query.filter_by(email='angry@example.com').first()
        assert row is not None and row.source == 'complaint'
        assert _db.session.get(Contact, cid).email_opt_out is True


def test_open_event_is_ignored(client, app):
    from app.models import EmailUnsubscribe
    payload = {
        'event_name': 'email_open',
        'event_message': [{'details': [{
            'event': 'Open',
            'recipient': 'reader@example.com',
        }]}],
    }
    r = _post(client, payload)
    assert r.status_code == 200 and r.get_json()['suppressed'] == 0
    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email='reader@example.com').first() is None


def test_empty_payload_is_acknowledged(client):
    r = _post(client, {})
    assert r.status_code == 200 and r.get_json()['suppressed'] == 0


def test_duplicate_bounce_is_idempotent(client, app):
    from app.models import EmailUnsubscribe
    payload = {
        'event_name': 'hardbounce',
        'event_message': [{'details': [{
            'event': 'HardBounce', 'bounced_recipient': 'twice@example.com',
        }]}],
    }
    assert _post(client, payload).get_json()['suppressed'] == 1
    # Second delivery of the same event must not add a duplicate row.
    assert _post(client, payload).get_json()['suppressed'] == 0
    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email='twice@example.com').count() == 1


def _soft_payload(addr, reason='mailbox full'):
    """ZeptoMail's real soft-bounce shape: nested email_info.to + event_data."""
    return {
        'event_name': 'soft bounce',
        'event_message': {
            'event_data': {'details': {'reason': reason}},
            'email_info': {'to': {'email_address': [{'address': addr}]}},
        },
    }


def test_soft_bounce_records_strike_without_suppressing(client, app):
    from app.models import EmailUnsubscribe
    from app.crm.models import Contact
    with app.app_context():
        c = Contact(name='Slowbox', email='slowbox@example.com', email_opt_out=False)
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    r = _post(client, _soft_payload('slowbox@example.com'))
    assert r.status_code == 200
    body = r.get_json()
    assert body['suppressed'] == 0 and body['soft_recorded'] == 1
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.soft_bounce_count == 1
        assert c.last_bounce_type == 'soft'
        assert c.last_bounce_reason == 'mailbox full'
        assert c.email_opt_out is False
        # A single soft bounce never lands on the global suppression list.
        assert EmailUnsubscribe.query.filter_by(email='slowbox@example.com').first() is None


def test_soft_bounces_suppress_after_threshold(client, app, monkeypatch):
    from app.models import EmailUnsubscribe
    from app.crm.models import Contact
    monkeypatch.setenv('SOFT_BOUNCE_SUPPRESS_THRESHOLD', '2')
    with app.app_context():
        c = Contact(name='Repeat', email='repeat@example.com', email_opt_out=False)
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    assert _post(client, _soft_payload('repeat@example.com')).get_json()['suppressed'] == 0
    assert _post(client, _soft_payload('repeat@example.com')).get_json()['suppressed'] == 1
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.soft_bounce_count == 2 and c.email_opt_out is True
        row = EmailUnsubscribe.query.filter_by(email='repeat@example.com').first()
        assert row is not None and row.source == 'soft_bounce'


def test_open_event_clears_soft_strikes(client, app):
    from app.crm.models import Contact
    with app.app_context():
        c = Contact(name='Backalive', email='backalive@example.com', soft_bounce_count=2)
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    payload = {'event_name': 'open',
               'event_message': {'email_info': {'to': {'email_address': [
                   {'address': 'backalive@example.com'}]}}}}
    r = _post(client, payload)
    assert r.status_code == 200 and r.get_json().get('recovered') == 1
    with app.app_context():
        assert _db.session.get(Contact, cid).soft_bounce_count == 0


def test_hard_bounce_stamps_contact(client, app):
    from app.crm.models import Contact
    with app.app_context():
        c = Contact(name='Dead', email='deadbox@example.com')
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    payload = {'event_name': 'hard bounce',
               'event_message': {'event_data': {'details': {'reason': '550 user unknown'}},
                                 'email_info': {'to': {'email_address': [
                                     {'address': 'deadbox@example.com'}]}}}}
    assert _post(client, payload).get_json()['suppressed'] == 1
    with app.app_context():
        c = _db.session.get(Contact, cid)
        assert c.email_opt_out is True and c.last_bounce_type == 'hard'
        assert c.last_bounce_reason == '550 user unknown'


def test_feedback_loop_classifies_as_complaint(client, app):
    from app.models import EmailUnsubscribe
    payload = {'event_name': 'feedback loop',
               'event_message': {'email_info': {'to': {'email_address': [
                   {'address': 'flagger@example.com'}]}}}}
    assert _post(client, payload).get_json()['suppressed'] == 1
    with app.app_context():
        row = EmailUnsubscribe.query.filter_by(email='flagger@example.com').first()
        assert row is not None and row.source == 'complaint'


def test_events_are_logged_for_dashboard(client, app):
    """Every webhook event lands in crm_email_event (history for the
    deliverability dashboard), with opens/clicks distinguished."""
    from app.crm.models import CrmEmailEvent
    _post(client, {'event_name': 'hard bounce',
                   'event_message': {'event_data': {'details': {'reason': '550 gone'}},
                                     'email_info': {'to': {'email_address': [
                                         {'address': 'log1@example.com'}]}}}})
    _post(client, _soft_payload('log2@example.com'))
    _post(client, {'event_name': 'email_link_clicked',
                   'event_message': {'email_info': {'to': {'email_address': [
                       {'address': 'log3@example.com'}]}}}})
    with app.app_context():
        rows = {e.email: e for e in CrmEmailEvent.query.all()}
        assert rows['log1@example.com'].event_type == 'hard'
        assert rows['log1@example.com'].reason == '550 gone'
        assert rows['log2@example.com'].event_type == 'soft'
        assert rows['log3@example.com'].event_type == 'click'


def test_bounce_lands_on_contact_timeline(client, app):
    """Bounces are recorded as Activity on the CRM contact, so the BDR agent's
    context (recent timeline entries) sees them."""
    from app.crm.models import Contact, Activity, CrmEmailEvent
    with app.app_context():
        c = Contact(name='Timeline', email='timeline@example.com')
        _db.session.add(c)
        _db.session.commit()
        cid = c.id
    _post(client, {'event_name': 'hard bounce',
                   'event_message': {'event_data': {'details': {'reason': '550 no such user'}},
                                     'email_info': {'to': {'email_address': [
                                         {'address': 'timeline@example.com'}]}}}})
    with app.app_context():
        acts = Activity.query.filter_by(contact_id=cid, kind='bounce').all()
        assert len(acts) == 1
        assert 'hard-bounced' in acts[0].description
        assert '550 no such user' in acts[0].description
        # The event row links back to the contact.
        ev = CrmEmailEvent.query.filter_by(email='timeline@example.com').first()
        assert ev is not None and ev.contact_id == cid


def test_auth_key_in_payload_authorizes(client, app):
    from app.models import EmailUnsubscribe
    payload = {'event_name': 'hard bounce', 'mailagent_key': 'p4yload-key',
               'event_message': {'email_info': {'to': {'email_address': [
                   {'address': 'pk@example.com'}]}}}}
    original = app.config.get('ZEPTOMAIL_WEBHOOK_SECRET', '')
    app.config['ZEPTOMAIL_WEBHOOK_SECRET'] = 'p4yload-key'
    try:
        # No header/query token, but the payload carries the agent key -> accepted.
        r = _post(client, payload)
        assert r.status_code == 200 and r.get_json()['suppressed'] == 1
        with app.app_context():
            assert EmailUnsubscribe.query.filter_by(email='pk@example.com').first() is not None
    finally:
        app.config['ZEPTOMAIL_WEBHOOK_SECRET'] = original


def test_secret_enforced_when_configured(client, app):
    """When ZEPTOMAIL_WEBHOOK_SECRET is set, an unauthenticated POST is rejected."""
    from app.models import EmailUnsubscribe
    payload = {
        'event_name': 'hardbounce',
        'event_message': [{'details': [{
            'event': 'HardBounce', 'bounced_recipient': 'gated@example.com',
        }]}],
    }
    original = app.config.get('ZEPTOMAIL_WEBHOOK_SECRET', '')
    app.config['ZEPTOMAIL_WEBHOOK_SECRET'] = 's3cr3t'
    try:
        # No token -> 403, nothing suppressed.
        assert _post(client, payload).status_code == 403
        with app.app_context():
            assert EmailUnsubscribe.query.filter_by(email='gated@example.com').first() is None
        # Wrong token -> 403.
        assert _post(client, payload, headers={'X-Webhook-Token': 'nope'}).status_code == 403
        # Correct token -> accepted and suppressed.
        r = _post(client, payload, headers={'X-Webhook-Token': 's3cr3t'})
        assert r.status_code == 200 and r.get_json()['suppressed'] == 1
        with app.app_context():
            assert EmailUnsubscribe.query.filter_by(email='gated@example.com').first() is not None
    finally:
        app.config['ZEPTOMAIL_WEBHOOK_SECRET'] = original
