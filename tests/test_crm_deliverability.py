"""Deliverability honesty: suppression enforced by address at the CRM send
choke points, phantom 'sent' recording fixed, honest delivered_count, and the
CAN-SPAM postal address in the shared outreach footer."""
from app import db as _db


def _register_first_admin(client, username='delivadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password,
                             'confirm': password},
                       follow_redirects=True)


def _suppress(app, email):
    from app.models import EmailUnsubscribe
    with app.app_context():
        _db.session.add(EmailUnsubscribe(email=email.lower(), source='self'))
        _db.session.commit()


def test_campaign_records_suppressed_not_phantom_sent(client, app):
    """A globally-unsubscribed address must be recorded 'suppressed' with NO
    Activity/Note — previously it was stamped like a send that never happened,
    corrupting the timeline and the open-rate denominator."""
    _register_first_admin(client)
    _suppress(app, 'gone@example.com')
    from app.crm.models import (Campaign, CampaignRecipient, Contact, Company,
                                Activity)
    with app.app_context():
        co = Company(name='Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        ok_c = Contact(name='Keep', email='keep@example.com', company_id=co.id)
        gone_c = Contact(name='Gone', email='gone@example.com', company_id=co.id)
        _db.session.add_all([ok_c, gone_c])
        camp = Campaign(name='C', subject='Hi', body='Hello',
                        status='draft', audience_state='NE')
        _db.session.add(camp)
        _db.session.commit()
        cid, gone_id, keep_id = camp.id, gone_c.id, ok_c.id

    client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True)
    with app.app_context():
        by_contact = {r.contact_id: r for r in
                      CampaignRecipient.query.filter_by(campaign_id=cid)}
        assert by_contact[gone_id].status == 'suppressed'
        assert by_contact[keep_id].status in ('sent', 'logged')
        # no phantom timeline entries for mail that never went out
        assert Activity.query.filter_by(contact_id=gone_id).count() == 0
        camp = _db.session.get(Campaign, cid)
        assert all(r.status != 'suppressed' or r.contact_id == gone_id
                   for r in camp.recipients)


def test_smtp_send_refuses_suppressed_address(client, app, monkeypatch):
    """One-to-one/approval-queue sends honor the suppression list at the
    choke point — send_email must never even be called."""
    import app.email_service as es
    from app.crm.helpers import smtp_send
    _suppress(app, 'nope@example.com')
    called = {}
    monkeypatch.setattr(es, 'send_email',
                        lambda *a, **k: called.setdefault('hit', True))
    with app.app_context():
        assert smtp_send('nope@example.com', 'Subj', 'Body') is False
    assert 'hit' not in called


def test_delivered_count_is_accepted_sends_only(app):
    from app.crm.models import Campaign, CampaignRecipient
    with app.app_context():
        camp = Campaign(name='D', subject='s', body='b', status='sent')
        _db.session.add(camp)
        _db.session.flush()
        for status in ('sent', 'logged', 'suppressed', 'opted_out'):
            _db.session.add(CampaignRecipient(campaign_id=camp.id, status=status))
        _db.session.commit()
        assert camp.delivered_count == 1          # only the accepted send


def test_import_marks_already_suppressed_address_opted_out(client, app):
    """A re-imported row carrying an unsubscribed address must arrive
    opted-out instead of resurrecting the person into the mailable pool."""
    _register_first_admin(client)
    _suppress(app, 'unsub@example.com')
    csv_body = ('Name,City,State,Type,Email\n'
                'Fresh Org,Omaha,NE,Independent,unsub@example.com\n')
    from io import BytesIO
    client.post('/crm/import',
                data={'file': (BytesIO(csv_body.encode()), 'leads.csv')},
                content_type='multipart/form-data', follow_redirects=True)
    from app.crm.models import Contact
    with app.app_context():
        c = Contact.query.filter_by(email='unsub@example.com').first()
        assert c is not None and c.email_opt_out is True


def test_outreach_footer_includes_mailing_address(app):
    from app.email_service import render_sales_email
    with app.app_context():
        app.config['CRM_MAILING_ADDRESS'] = '123 Garden Way, Omaha, NE 68127'
        try:
            html = render_sales_email('<p>Hello</p>')
        finally:
            app.config.pop('CRM_MAILING_ADDRESS', None)
        assert '123 Garden Way, Omaha, NE 68127' in html
