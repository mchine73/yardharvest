"""What the writer is allowed to say, and which replies we manage to hear.

Two gaps that cost conversions. The writer was forbidden to state a price or
link the free signup, so a volunteer garden with no budget got asked for a
30-minute call and "how much is it?" needed a manual round-trip. And reply
capture matched only the exact address we mailed — for a lead base of info@
inboxes, a coordinator answering from her own address vanished silently.
"""
from datetime import timedelta

import pytest

from app import db as _db
from app.crm import agent_service, autonomy
from app.crm.autonomy_replies import (FREEMAIL_DOMAINS, _looks_like_a_reply_to_us,
                                      _match_by_thread, handle_inbound)
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmInboundReply, CrmUser, Note, _utcnow)
from app.models import PricingConfig


@pytest.fixture()
def console_price(db_session):
    row = PricingConfig.query.first() or PricingConfig()
    row.garden_pro_monthly_cents = 1200
    row.garden_pro_yearly_cents = 6000
    row.garden_pro_trial_days = 14
    _db.session.add(row)
    _db.session.commit()
    return row


def _company(name='Maple Roots', **kw):
    co = Company(name=name, city='Lincoln', state='NE',
                 org_type=kw.pop('org_type', 'Independent'), **kw)
    _db.session.add(co)
    _db.session.commit()
    return co


def _contact(name, email, company=None, **kw):
    c = Contact(name=name, email=email, company_id=company.id if company else None, **kw)
    _db.session.add(c)
    _db.session.commit()
    return c


def _operator():
    u = CrmUser(username='op', role='admin')
    u.set_password('secret123')
    _db.session.add(u)
    _db.session.commit()
    return u


# ---------------------------------------------------------------------------
# R3 — the facts the writer was denied
# ---------------------------------------------------------------------------
def test_the_writer_is_told_the_real_price_from_the_console(app, console_price):
    with app.test_request_context():
        voice = agent_service.brand_voice()

    assert '$12/month' in voice and '$60/year' in voice
    assert '14-day free trial' in voice
    # $12 x 12 = $144, so the annual deal saves $84. Stated, not left to the
    # model to work out and get wrong.
    assert 'saves $84' in voice
    assert '/register' in voice and '/pricing' in voice and '/book' in voice


def test_the_price_follows_the_console_without_a_deploy(app, console_price):
    """Resolved per call, not frozen at import."""
    with app.test_request_context():
        assert '$60/year' in agent_service.brand_voice()
    console_price.garden_pro_yearly_cents = 9900
    _db.session.commit()
    with app.test_request_context():
        voice = agent_service.brand_voice()
    assert '$99/year' in voice and '$60/year' not in voice


def test_the_cta_is_matched_to_who_can_actually_buy(app, console_price):
    """A volunteer garden has no budget line and no procurement process; a
    nonprofit or a city program has both."""
    with app.test_request_context():
        voice = agent_service.brand_voice()
    assert 'Do NOT open by asking for a 30-minute call' in voice
    assert 'free plan' in voice
    for payer in ('nonprofit', 'operator', 'city'):
        assert payer in voice.lower()


def test_the_lead_block_carries_what_research_already_found():
    """The CRM was holding a website, tags and a scout's rationale and handing
    the writer none of it."""
    line = agent_service._lead_block({
        'lead_id': 3, 'name': 'Pat Grower', 'company': 'Maple Roots',
        'city': 'Lincoln', 'state': 'NE', 'org_type': 'Independent',
        'lead_status': 'New', 'days_since_contact': None, 'recent': [],
        'website': 'https://maple.org', 'tags': 'grant-funded, 40 plots',
        'facts_on_file': ['Fit: 40 plots, runs a waitlist on paper.\nSource: maple.org/about',
                          'Received a 2025 city greening grant.'],
    })
    assert 'https://maple.org' in line
    assert 'grant-funded, 40 plots' in line
    assert 'facts on file:' in line
    assert 'runs a waitlist on paper' in line
    # Newlines would break the one-line-per-lead prompt format.
    assert '\n' not in line


def test_lead_context_supplies_the_facts_and_skips_our_own_emails(app, db_session):
    from app.crm.views import _lead_context

    co = _company()
    c = _contact('Pat Grower', 'pat@maple.org', co)
    _db.session.add_all([
        Note(contact_id=c.id, content='Fit: 40 plots, waitlist on paper.'),
        Note(contact_id=c.id, content='[Email sent to pat@maple.org] Waitlist for Maple\n\nbody'),
    ])
    _db.session.commit()

    ctx = _lead_context(c)
    assert ctx['website'] is None and ctx['tags'] is None
    assert any('40 plots' in f for f in ctx['facts_on_file'])
    # Prior emails reach the prompt separately, with touch numbers.
    assert not any(f.startswith('[Email ') for f in ctx['facts_on_file'])


def test_the_signup_link_counts_as_a_call_to_action():
    """One ask per email. A free-signup link is an ask like any other."""
    body = ('<p>Hi Pat,</p><p>Set your page up free: '
            '<a href="https://www.yardharvest.app/register">ten minutes</a>. '
            'Or grab a time: <a href="https://www.yardharvest.app/book">book</a>.</p>')
    issues = agent_service.lint_email('A question about your waitlist', body,
                                      contact_name='Pat Grower')
    assert any('more than one call to action' in i for i in issues)


def test_no_budget_is_its_own_class_not_a_rejection():
    assert 'no_budget' in agent_service.REPLY_CLASSES
    system = agent_service.CLASSIFY_SYSTEM
    assert 'no_budget' in system
    # A referral is a person to talk to, not an away notice.
    assert "is 'other', not this" in system


# ---------------------------------------------------------------------------
# R4 — hearing the reply
# ---------------------------------------------------------------------------
def test_a_reply_from_a_different_address_still_finds_the_contact(app, db_session):
    """The case we were losing: we mail info@, the coordinator answers from
    her own inbox, and only our Message-ID connects the two."""
    co = _company()
    shared = _contact('Info — Maple Roots', 'info@maple.org', co)
    op = _operator()
    _db.session.add(CrmAgentAction(
        action_type='follow_up_email', status='executed', contact_id=shared.id,
        title='Intro', created_by_id=op.id,
        payload_json='{"subject": "Waitlist for Maple", "message_id": "<abc123@yardharvest.app>"}'))
    _db.session.commit()

    contact, why = _match_by_thread({'in_reply_to': '<abc123@yardharvest.app>'})
    assert contact.id == shared.id
    assert 'abc123' in why

    # References works too — some clients only populate that.
    contact, _ = _match_by_thread(
        {'references': '<other@x.com> <abc123@yardharvest.app>'})
    assert contact.id == shared.id


def test_an_unrelated_message_id_matches_nobody(app, db_session):
    _company()
    assert _match_by_thread({'in_reply_to': '<nope@elsewhere.com>'}) == (None, None)


def test_a_reply_to_a_subject_we_sent_is_corroboration(app, db_session):
    co = _company()
    c = _contact('Pat', 'pat@maple.org', co)
    _db.session.add(Note(contact_id=c.id,
                         content='[Email sent to pat@maple.org] Waitlist for Maple\n\nbody'))
    _db.session.commit()

    why = _looks_like_a_reply_to_us({'subject': 'Re: Waitlist for Maple',
                                     'from_email': 'someone@gmail.com'})
    assert why and 'Waitlist for Maple' in why


def test_an_old_subject_is_no_longer_evidence(app, db_session):
    co = _company()
    c = _contact('Pat', 'pat@maple.org', co)
    stale = Note(contact_id=c.id,
                 content='[Email sent to pat@maple.org] Waitlist for Maple\n\nbody')
    _db.session.add(stale)
    _db.session.commit()
    stale.created_at = _utcnow() - timedelta(days=90)
    _db.session.commit()

    assert _looks_like_a_reply_to_us({'subject': 'Re: Waitlist for Maple',
                                      'from_email': 'someone@gmail.com'}) is None


def test_a_company_domain_corroborates_but_a_freemail_one_never_does(app, db_session):
    _company('Maple Roots', website='https://maple.org')
    _db.session.commit()

    why = _looks_like_a_reply_to_us({'subject': 'quick question',
                                     'from_email': 'director@maple.org'})
    assert why and 'Maple Roots' in why

    # Otherwise every stranger with a Gmail address would be attached to
    # whichever company happens to have a Gmail contact.
    assert 'gmail.com' in FREEMAIL_DOMAINS
    _company('Gmail Garden', website='https://gmail.com')
    _db.session.commit()
    assert _looks_like_a_reply_to_us({'subject': 'buy cheap watches',
                                      'from_email': 'spam@gmail.com'}) is None


def test_vendor_mail_stays_out_of_the_queue(app, db_session):
    """The mailbox may also take Stripe, GitHub and invoices. A needs-you
    queue full of receipts is a queue nobody reads."""
    _company('Maple Roots', website='https://maple.org')
    _db.session.commit()
    assert _looks_like_a_reply_to_us({'subject': 'Your invoice is ready',
                                      'from_email': 'billing@stripe.com'}) is None


def test_an_unidentified_reply_is_surfaced_once_and_sends_nothing(app, db_session):
    co = _company('Maple Roots', website='https://maple.org')
    _db.session.commit()
    settings = AgentSettings.get()
    summary = {}

    parsed = {'from_email': 'director@maple.org', 'from_name': 'Dana Reed',
              'subject': 'Re: Waitlist for Maple', 'text': 'Who is this about?',
              'message_id': '<inbound-1@maple.org>', 'date': _utcnow()}
    assert handle_inbound(parsed, 11, 1, settings, summary) is None

    row = CrmInboundReply.query.filter_by(classification='unmatched').one()
    assert row.contact_id is None and row.from_email == 'director@maple.org'
    assert 'Needs a human' in row.action_taken
    assert summary['unmatched'][0]['from'] == 'director@maple.org'
    # No lead was invented and no mail went out.
    assert Contact.query.count() == 0
    assert CrmAgentAction.query.count() == 0

    # Re-polling the same message must not queue it twice.
    handle_inbound(parsed, 11, 1, settings, summary)
    assert CrmInboundReply.query.filter_by(classification='unmatched').count() == 1


def test_no_budget_keeps_the_lead_and_drafts_the_free_plan(app, db_session, monkeypatch):
    """It used to Disqualify — throwing away the one objection we can answer
    the same day."""
    co = _company()
    c = _contact('Pat Grower', 'pat@maple.org', co, lead_status='Working')
    op = _operator()
    settings = AgentSettings.get()
    settings.operator_user_id = op.id
    _db.session.commit()

    monkeypatch.setattr(agent_service, 'classify_reply',
                        lambda text, subject='', model=None: (
                            {'classification': 'no_budget',
                             'summary': 'All volunteers, no budget this year.',
                             'suggested_next_step': 'Offer the free plan.'}, {}))
    monkeypatch.setattr(agent_service, 'draft_reply',
                        lambda ctx, sender_name='', model=None: (
                            {'subject': 'Re: Waitlist for Maple',
                             'body': '<p>The free plan covers all of that.</p>'}, {}))

    summary = {}
    action = handle_inbound({'from_email': 'pat@maple.org', 'subject': 'Re: Waitlist',
                             'text': "We're all volunteers — there's no budget.",
                             'message_id': '<in-2@maple.org>', 'date': _utcnow()},
                            12, 1, settings, summary)

    c = _db.session.get(Contact, c.id)
    assert c.lead_status == 'Engaged'
    assert c.lead_status != 'Disqualified'
    assert 'free plan' in (c.next_action_note or '')
    assert 'cost objection' in action
    # The answer is queued, never auto-sent.
    queued = CrmAgentAction.query.filter_by(action_type='reply_email', status='pending').one()
    assert 'free plan' in queued.payload['body']


def test_every_send_carries_a_message_id_we_own(app, db_session, monkeypatch):
    from app.crm import helpers

    captured = {}
    monkeypatch.setattr('app.email_service.send_email',
                        lambda *a, **kw: captured.update(kw) or True)
    monkeypatch.setattr('app.email_service.is_email_suppressed', lambda e: False)

    with app.test_request_context():
        assert helpers.smtp_send('pat@maple.org', 'Subject', '<p>Body</p>') is True
        mid = captured['mime_headers']['Message-ID']
        assert mid.startswith('<') and mid.endswith('>')
        # From our own domain, so a reply's In-Reply-To is traceable to us.
        assert 'yardharvest.app' in mid

        # A caller that needs to store the id supplies it.
        helpers.smtp_send('pat@maple.org', 'S', '<p>B</p>', message_id='<mine@x>')
        assert captured['mime_headers']['Message-ID'] == '<mine@x>'
