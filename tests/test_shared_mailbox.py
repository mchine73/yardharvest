"""james@yardharvest.app is the platform's address too, not a sales inbox.

So an inbound message from someone the CRM knows is not evidence they replied
to outreach — it may be a customer asking for help, or a stranger writing in
cold. Running the prospecting flow on either sends a sales email to somebody
who was asking a question, which is the kind of email that loses an account.
"""
import pytest

from app import db as _db
from app.crm import agent_service
from app.crm.autonomy_replies import handle_inbound
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmInboundReply, CrmUser, _utcnow)


def _company(name='Maple Roots'):
    co = Company(name=name, city='Lincoln', state='NE', org_type='Independent')
    _db.session.add(co)
    _db.session.commit()
    return co


def _contact(name, email, company=None, **kw):
    c = Contact(name=name, email=email,
                company_id=company.id if company else None, **kw)
    _db.session.add(c)
    _db.session.commit()
    return c


def _operator():
    u = CrmUser(username='op', role='admin')
    u.set_password('secret123')
    _db.session.add(u)
    _db.session.commit()
    return u


def test_a_customer_writing_in_is_never_run_through_the_sales_flow(app, db_session,
                                                                   monkeypatch):
    co = _company()
    customer = _contact('Dana Reed', 'dana@maple.org', co, lead_status='Working',
                        platform_status='trialing', last_contacted_at=_utcnow())

    monkeypatch.setattr(agent_service, 'classify_reply',
                        lambda *a, **k: pytest.fail('must not classify a customer'))
    monkeypatch.setattr(agent_service, 'draft_reply',
                        lambda *a, **k: pytest.fail('must not draft a sales reply'))

    summary = {}
    action = handle_inbound({'from_email': 'dana@maple.org', 'subject': 'Plot map help',
                             'text': 'How do I move a plot?',
                             'message_id': '<cust-1@maple.org>', 'date': _utcnow()},
                            30, 1, AgentSettings.get(), summary)

    assert action == 'Surfaced for review'
    row = CrmInboundReply.query.filter_by(classification='not_outreach').one()
    assert row.contact_id == customer.id
    assert 'already on the platform' in row.summary
    # Lead status untouched, nothing queued to send.
    assert _db.session.get(Contact, customer.id).lead_status == 'Working'
    assert CrmAgentAction.query.count() == 0
    assert summary['not_outreach'][0]['contact'] == 'Dana Reed'


def test_mail_from_someone_we_never_emailed_is_not_a_reply(app, db_session, monkeypatch):
    """Matching an address only says who they are. With platform mail in the
    same box that is not evidence they answered anything."""
    co = _company()
    never = _contact('Sam Rivers', 'sam@maple.org', co, lead_status='New')
    assert never.last_contacted_at is None

    monkeypatch.setattr(agent_service, 'classify_reply',
                        lambda *a, **k: pytest.fail('must not classify'))
    summary = {}
    handle_inbound({'from_email': 'sam@maple.org', 'subject': 'Question',
                    'text': 'Saw your site — what is this?',
                    'message_id': '<new-1@maple.org>', 'date': _utcnow()},
                   31, 1, AgentSettings.get(), summary)

    row = CrmInboundReply.query.filter_by(classification='not_outreach').one()
    assert 'never emailed them' in row.summary
    assert _db.session.get(Contact, never.id).lead_status == 'New'


def test_a_threaded_match_is_proof_we_wrote_first(app, db_session, monkeypatch):
    """The never-emailed guard must not swallow a genuine reply: a Message-ID
    we generated is evidence we started the conversation, even when the reply
    arrives from an address we have never mailed."""
    co = _company()
    shared = _contact('Info — Maple Roots', 'info@maple.org', co, lead_status='Working')
    op = _operator()
    _db.session.add(CrmAgentAction(
        action_type='follow_up_email', status='executed', contact_id=shared.id,
        title='Intro', created_by_id=op.id,
        payload_json='{"subject": "Waitlist", "message_id": "<ours-9@yardharvest.app>"}'))
    settings = AgentSettings.get()
    settings.operator_user_id = op.id
    _db.session.commit()

    monkeypatch.setattr(agent_service, 'classify_reply',
                        lambda *a, **k: ({'classification': 'interested',
                                          'summary': 'Wants a call.',
                                          'suggested_next_step': 'Book'}, {}))
    monkeypatch.setattr(agent_service, 'draft_reply',
                        lambda *a, **k: ({'subject': 'Re: Waitlist',
                                          'body': '<p>Sure.</p>'}, {}))

    summary = {}
    action = handle_inbound({'from_email': 'coordinator@gmail.com',
                             'in_reply_to': '<ours-9@yardharvest.app>',
                             'subject': 'Re: Waitlist', 'text': 'Yes please.',
                             'message_id': '<their-9@gmail.com>', 'date': _utcnow()},
                            32, 1, settings, summary)

    assert 'Engaged' in action
    assert _db.session.get(Contact, shared.id).lead_status == 'Engaged'


def test_a_real_reply_from_a_lead_we_did_email_still_works(app, db_session, monkeypatch):
    """The guards must not break the case the whole loop exists for."""
    co = _company()
    lead = _contact('Pat Grower', 'pat@maple.org', co, lead_status='Working',
                    last_contacted_at=_utcnow())
    op = _operator()
    settings = AgentSettings.get()
    settings.operator_user_id = op.id
    _db.session.commit()

    monkeypatch.setattr(agent_service, 'classify_reply',
                        lambda *a, **k: ({'classification': 'interested',
                                          'summary': 'Asked for pricing.',
                                          'suggested_next_step': 'Send it'}, {}))
    monkeypatch.setattr(agent_service, 'draft_reply',
                        lambda *a, **k: ({'subject': 'Re: Waitlist',
                                          'body': '<p>It is $12/month.</p>'}, {}))

    summary = {}
    action = handle_inbound({'from_email': 'pat@maple.org', 'subject': 'Re: Waitlist',
                             'text': 'How much is it?',
                             'message_id': '<real-1@maple.org>', 'date': _utcnow()},
                            33, 1, settings, summary)

    assert 'Engaged' in action
    assert _db.session.get(Contact, lead.id).lead_status == 'Engaged'
    assert CrmAgentAction.query.filter_by(action_type='reply_email').count() == 1


def test_both_kinds_of_held_inbound_reach_the_console(client, app, db_session):
    from app.crm.views import _today_brief

    client.post('/crm/register', data={'username': 'mbadmin', 'password': 'secret123',
                                       'confirm': 'secret123'}, follow_redirects=True)
    co = _company()
    known = _contact('Dana Reed', 'dana@maple.org', co, platform_status='active')
    _db.session.add_all([
        CrmInboundReply(contact_id=None, from_email='stranger@cedar.org',
                        subject='Re: Waitlist', message_id='<u-1@x>',
                        classification='unmatched', summary='Looks like a reply'),
        CrmInboundReply(contact_id=known.id, from_email='dana@maple.org',
                        subject='Plot help', message_id='<n-1@x>',
                        classification='not_outreach', summary='Already on the platform'),
    ])
    _db.session.commit()

    with app.test_request_context():
        held = _today_brief()['unmatched']
    assert {r.classification for r in held} == {'unmatched', 'not_outreach'}

    body = client.get('/crm/agent').data.decode()
    assert 'Inbound mail that needs you' in body
    assert 'stranger@cedar.org' in body and 'dana@maple.org' in body
