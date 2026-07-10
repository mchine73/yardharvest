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

    # Two-step checkpoint: snapshot review first, then confirm.
    client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True)
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


def test_approve_atomic_claim_blocks_double_send(client, app, monkeypatch):
    """The approve transition is an atomic pending->executing claim: a second
    submit of the same proposal must not send a second email."""
    _register_first_admin(client)
    from app.crm.models import Company, Contact, CrmAgentAction
    import app.crm.views as views
    with app.app_context():
        co = Company(name='Claim Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name='Pat Claim', email='pat.claim@example.com',
                    company_id=co.id, lead_status='New')
        _db.session.add(c)
        _db.session.flush()
        a = CrmAgentAction(action_type='follow_up_email', status='pending',
                           contact_id=c.id, title='Follow up',
                           payload_json='{"subject":"Hi","body":"Hello"}')
        _db.session.add(a)
        _db.session.commit()
        aid = a.id
    sends = []
    monkeypatch.setattr(views, 'smtp_send',
                        lambda *args, **kw: sends.append(1) or True)
    data = {'subject': 'Hi', 'body': 'Hello'}
    client.post(f'/crm/agent/actions/{aid}/approve', data=data,
                follow_redirects=True)
    second = client.post(f'/crm/agent/actions/{aid}/approve', data=data,
                         follow_redirects=True)
    assert len(sends) == 1                    # exactly one send, ever
    assert b'already handled' in second.data


def test_console_shows_rendered_followup_preview(client, app):
    """The approval card shows the merge-resolved email and flags tokens that
    resolve empty for this contact (the 'Hi ,' problem)."""
    _register_first_admin(client)
    from app.crm.models import Company, Contact, CrmAgentAction
    with app.app_context():
        co = Company(name='Preview Org', state='NE', city='')   # city empty
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name='Prue View', email='prue@example.com',
                    company_id=co.id)
        _db.session.add(c)
        _db.session.flush()
        _db.session.add(CrmAgentAction(
            action_type='follow_up_email', status='pending', contact_id=c.id,
            title='Follow up',
            payload_json='{"subject":"Hi {{first_name}}",'
                         '"body":"<p>Greetings from {{city}}</p>"}'))
        _db.session.commit()
    html = client.get('/crm/agent').get_data(as_text=True)
    assert 'Hi Prue' in html                     # merge token resolved
    assert 'What Prue View will receive' in html
    assert 'city' in html and 'empty' in html    # empty-token warning


def test_campaign_send_is_review_then_confirm(client, app):
    """Bulk sends pass through a reviewable snapshot: the first send POST
    freezes the list (nothing mailed); a contact created AFTER the snapshot
    does NOT join the confirmed blast."""
    _register_first_admin(client)
    from app.crm.models import Campaign, CampaignRecipient, Contact, Company
    with app.app_context():
        co = Company(name='Snap Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        _db.session.add(Contact(name='Early', email='early@example.com',
                                company_id=co.id))
        camp = Campaign(name='Snap', subject='s', body='b',
                        status='draft', audience_state='NE')
        _db.session.add(camp)
        _db.session.commit()
        cid, co_id = camp.id, co.id

    r1 = client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True)
    assert b'Review the' in r1.data
    with app.app_context():
        camp = _db.session.get(Campaign, cid)
        assert camp.status == 'draft'            # nothing sent yet
        # A lead lands AFTER review — previously it silently joined the blast.
        _db.session.add(Contact(name='Late', email='late@example.com',
                                company_id=co_id))
        _db.session.commit()

    client.post(f'/crm/campaigns/{cid}/send', follow_redirects=True)
    with app.app_context():
        camp = _db.session.get(Campaign, cid)
        assert camp.status == 'sent'
        emails = {r.contact.email for r in
                  CampaignRecipient.query.filter_by(campaign_id=cid) if r.contact}
        assert emails == {'early@example.com'}   # snapshot, not live filters


def test_click_tracker_never_redirects_unresolved_token(client, app):
    """Open-redirect fix: an unknown token must never forward to the
    attacker-supplied URL (the tracker lives on the auth-exempt sending
    domain, so forwarding trades on our reputation)."""
    r = client.get('/crm/t/click/not-a-real-token?u=https://evil.example.com/x',
                   follow_redirects=False)
    assert r.status_code in (301, 302)
    assert 'evil.example.com' not in r.headers.get('Location', '')


def test_import_normalizes_org_type(client, app):
    """Free-text CSV Type values map onto the canonical set so type-filtered
    campaigns/segments can actually select the imported orgs."""
    _register_first_admin(client)
    from io import BytesIO
    csv_body = ('Name,City,State,Type\n'
                'Comm Org,Omaha,NE,community garden\n'
                'Parks Org,Lincoln,NE,Parks Department\n'
                'Odd Org,Wahoo,NE,Zebra Collective\n')
    client.post('/crm/import',
                data={'file': (BytesIO(csv_body.encode()), 'leads.csv')},
                content_type='multipart/form-data', follow_redirects=True)
    from app.crm.models import Company
    with app.app_context():
        assert Company.query.filter_by(name='Comm Org').first().org_type == 'Independent'
        assert Company.query.filter_by(name='Parks Org').first().org_type == 'City-Sponsored'
        assert Company.query.filter_by(name='Odd Org').first().org_type == ''


def test_delete_contact_detaches_referencing_rows(client, app):
    """Deleting a contact referenced by an agent proposal / campaign history
    must unlink those rows instead of raising IntegrityError on Postgres."""
    _register_first_admin(client)
    from app.crm.models import (Company, Contact, CrmAgentAction,
                                Campaign, CampaignRecipient)
    with app.app_context():
        co = Company(name='Del Org', state='NE')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name='Del Me', email='del@example.com', company_id=co.id)
        _db.session.add(c)
        _db.session.flush()
        camp = Campaign(name='Hist', subject='s', body='b', status='sent')
        _db.session.add(camp)
        _db.session.flush()
        _db.session.add(CrmAgentAction(action_type='follow_up_email',
                                       status='pending', contact_id=c.id,
                                       title='X', payload_json='{}'))
        _db.session.add(CampaignRecipient(campaign_id=camp.id,
                                          contact_id=c.id, status='sent'))
        _db.session.commit()
        cid, aid_count = c.id, CrmAgentAction.query.count()

    r = client.post(f'/crm/contacts/{cid}/delete', follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert _db.session.get(Contact, cid) is None
        # History survives, detached.
        assert CrmAgentAction.query.count() == aid_count
        assert CrmAgentAction.query.filter_by(contact_id=cid).count() == 0
        assert CampaignRecipient.query.filter_by(contact_id=cid).count() == 0
