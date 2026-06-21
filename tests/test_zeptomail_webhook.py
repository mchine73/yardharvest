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
