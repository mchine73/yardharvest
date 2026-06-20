"""List-Unsubscribe self-service page + global bulk-email suppression."""
from app import db as _db


def test_unsubscribe_get_shows_form(client):
    r = client.get('/unsubscribe')
    assert r.status_code == 200
    assert b'Unsubscribe' in r.data and b'name="email"' in r.data


def test_unsubscribe_get_does_not_suppress(client, app):
    """Link scanners / prefetch hit GET — that must never opt anyone out."""
    from app.models import EmailUnsubscribe
    client.get('/unsubscribe?email=ghost@example.com')
    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email='ghost@example.com').first() is None


def test_unsubscribe_post_suppresses_and_opts_out_contact(client, app):
    from app.models import EmailUnsubscribe
    from app.crm.models import Contact
    with app.app_context():
        c = Contact(name='Jo', email='Jo@Example.com', email_opt_out=False)
        _db.session.add(c)
        _db.session.commit()
        cid = c.id

    r = client.post('/unsubscribe', data={'email': 'jo@example.com'})
    assert r.status_code == 200 and b'unsubscribed' in r.data.lower()

    with app.app_context():
        assert EmailUnsubscribe.query.filter_by(email='jo@example.com').first() is not None
        from app.email_service import is_email_suppressed
        assert is_email_suppressed('JO@example.com') is True          # case-insensitive
        assert _db.session.get(Contact, cid).email_opt_out is True    # CRM reflects it


def test_list_unsubscribe_header_present(app):
    from app.email_service import _list_unsubscribe_headers
    with app.app_context():
        h = _list_unsubscribe_headers()
        assert 'List-Unsubscribe' in h
        val = h['List-Unsubscribe']
        assert '/unsubscribe' in val and 'mailto:' in val
