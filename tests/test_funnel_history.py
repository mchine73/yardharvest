"""How a lead moved, and what the outreach actually converted.

The CRM held every lead's status *now* and nothing about how it got there, so
the questions that decide what to change next — did touch 2 ever beat touch 1,
do city programs answer more often than volunteer gardens, did the signup link
outperform the call — had no answer anywhere. And a garden signing up was
invisible to the CRM until the nightly batch noticed.
"""
from datetime import date, timedelta

import pytest

from app import db as _db
from app.crm import autonomy
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmInboundReply, CrmLeadStatusHistory, CrmUser, Deal,
                            _utcnow, record_lead_status)
from app.models import CommunityGarden, GardenSubscription, User


def _org(name='Maple Roots', **kw):
    co = Company(name=name, city='Lincoln', state='NE', **kw)
    _db.session.add(co)
    _db.session.commit()
    return co


def _lead(name, email, company=None, **kw):
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


# ---------------------------------------------------------------------------
# Recording the move
# ---------------------------------------------------------------------------
def test_a_status_change_records_where_it_came_from_and_what_moved_it(app, db_session):
    c = _lead('Pat Grower', 'pat@maple.org')
    assert record_lead_status(c, 'Working', source='agent', note='First touch sent')
    _db.session.commit()

    row = CrmLeadStatusHistory.query.one()
    assert (row.from_status, row.to_status) == ('New', 'Working')
    assert row.source == 'agent' and row.note == 'First touch sent'
    assert c.lead_status == 'Working'


def test_re_asserting_the_same_status_writes_nothing(app, db_session):
    """The reply poller and the daily cycle both re-assert the current status
    routinely. Logging those would bury the real transitions."""
    c = _lead('Pat Grower', 'pat@maple.org', lead_status='Working')
    assert record_lead_status(c, 'Working', source='agent') is False
    _db.session.commit()
    assert CrmLeadStatusHistory.query.count() == 0


def test_an_invalid_status_is_refused_rather_than_stored(app, db_session):
    c = _lead('Pat Grower', 'pat@maple.org')
    assert record_lead_status(c, 'Enagged', source='agent') is False
    assert record_lead_status(c, '', source='agent') is False
    _db.session.commit()
    assert c.lead_status == 'New'
    assert CrmLeadStatusHistory.query.count() == 0


def test_the_history_reads_as_a_path(app, db_session):
    c = _lead('Pat Grower', 'pat@maple.org')
    for status, source in (('Working', 'agent'), ('Engaged', 'reply'),
                           ('Customer', 'platform')):
        record_lead_status(c, status, source=source)
    _db.session.commit()

    path = [(h.from_status, h.to_status, h.source) for h in
            CrmLeadStatusHistory.query.order_by(CrmLeadStatusHistory.id).all()]
    assert path == [('New', 'Working', 'agent'),
                    ('Working', 'Engaged', 'reply'),
                    ('Engaged', 'Customer', 'platform')]


def test_a_reply_records_that_the_reply_moved_it(app, db_session):
    """Not just that the lead is Engaged — that answering is what did it."""
    c = _lead('Pat Grower', 'pat@maple.org', lead_status='Working',
              last_contacted_at=_utcnow())
    autonomy.apply_reply(c)
    _db.session.commit()

    row = CrmLeadStatusHistory.query.filter_by(to_status='Engaged').one()
    assert row.source == 'reply'


# ---------------------------------------------------------------------------
# Which ask the email made
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('body,expected', [
    ('<p><a href="https://www.yardharvest.app/register">Set it up free</a></p>', 'signup'),
    ('<p><a href="https://www.yardharvest.app/book">Grab a time</a></p>', 'book'),
    ('<p><a href="https://www.yardharvest.app/about/guide/funding">Read this</a></p>', 'guide'),
    ('<p>Just reply if it would help.</p>', 'reply'),
    ('<p>Hope the season is going well.</p>', 'none'),
])
def test_the_ask_is_read_off_the_copy_that_went_out(app, body, expected):
    """Derived rather than declared: a self-reported label becomes a second
    source of truth and drifts from the email itself."""
    from app.crm.agent_service import cta_of
    assert cta_of(body) == expected


def test_a_stronger_ask_wins_when_an_email_carries_two(app):
    from app.crm.agent_service import cta_of
    both = ('<p><a href="https://www.yardharvest.app/about/guide/x">Guide</a> '
            'or <a href="https://www.yardharvest.app/register">sign up</a></p>')
    assert cta_of(both) == 'signup'


# ---------------------------------------------------------------------------
# Reply rates — the point of all of it
# ---------------------------------------------------------------------------
def _sent(contact, *, touch, when, cta='signup'):
    a = CrmAgentAction(action_type='follow_up_email', status='executed',
                       contact_id=contact.id, company_id=contact.company_id,
                       title='Follow up', reviewed_at=when, cta_type=cta,
                       payload_json=f'{{"touch_number": {touch}}}')
    _db.session.add(a)
    _db.session.commit()
    return a


def _answered(contact, *, when, classification='interested'):
    r = CrmInboundReply(contact_id=contact.id, from_email=contact.email,
                        subject='Re: hello', message_id=f'<r{contact.id}-{when}@x>',
                        classification=classification)
    _db.session.add(r)
    _db.session.commit()
    r.created_at = when
    _db.session.commit()
    return r


def test_reply_rate_is_broken_down_by_touch_org_type_and_ask(app, db_session):
    from app.crm.autonomy_cycle import funnel_rates

    city = _org('Parks Department', org_type='City-Sponsored')
    indie = _org('Maple Roots', org_type='Independent')
    now = _utcnow()

    answered = _lead('Dana Parks', 'dana@denver.gov', city)
    ignored = _lead('Pat Grower', 'pat@maple.org', indie)
    _sent(answered, touch=1, when=now - timedelta(days=5))
    _sent(ignored, touch=1, when=now - timedelta(days=5))
    _answered(answered, when=now - timedelta(days=3))

    rates = funnel_rates(now=now)
    assert rates['sends'] == 2

    by_touch = {r['key']: r for r in rates['by_touch']}
    assert by_touch['touch 1']['sent'] == 2
    assert by_touch['touch 1']['replied'] == 1
    assert by_touch['touch 1']['rate'] == pytest.approx(50.0)

    by_org = {r['key']: r['rate'] for r in rates['by_org']}
    assert by_org['City-Sponsored'] == pytest.approx(100.0)
    assert by_org['Independent'] == pytest.approx(0.0)

    by_cta = {r['key']: r['sent'] for r in rates['by_cta']}
    assert by_cta['signup'] == 2


def test_bounces_and_out_of_office_are_not_replies(app, db_session):
    """They say something about the address, nothing about the message."""
    from app.crm.autonomy_cycle import funnel_rates

    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co)
    now = _utcnow()
    _sent(c, touch=1, when=now - timedelta(days=4))
    _answered(c, when=now - timedelta(days=2), classification='out_of_office')

    rates = funnel_rates(now=now)
    assert rates['by_touch'][0]['replied'] == 0


def test_a_reply_long_after_the_send_is_not_credited_to_it(app, db_session):
    from app.crm.autonomy_cycle import funnel_rates

    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co)
    now = _utcnow()
    _sent(c, touch=1, when=now - timedelta(days=25))
    _answered(c, when=now - timedelta(days=1))          # 24 days later

    assert funnel_rates(now=now)['by_touch'][0]['replied'] == 0


def test_no_sends_produces_an_empty_report_rather_than_a_divide_by_zero(app, db_session):
    from app.crm.autonomy_cycle import funnel_rates
    rates = funnel_rates()
    assert rates['sends'] == 0 and rates['by_touch'] == []


def test_the_digest_states_what_is_working(app, db_session):
    from app.crm.autonomy_cycle import build_digest_html, funnel_rates

    co = _org('Parks Department', org_type='City-Sponsored')
    c = _lead('Dana Parks', 'dana@denver.gov', co)
    now = _utcnow()
    _sent(c, touch=2, when=now - timedelta(days=4))
    _answered(c, when=now - timedelta(days=2))

    html = build_digest_html({'date': 'Fri', 'cap': 15, 'sent': [], 'replies': [],
                              'rates': funnel_rates(now=now)}, AgentSettings.get())
    assert 'What is working' in html
    assert 'touch 2' in html and 'City-Sponsored' in html
    assert '100%' in html


# ---------------------------------------------------------------------------
# The product telling the CRM, in the moment
# ---------------------------------------------------------------------------
def _garden(name, email):
    user = User(username=email.split('@')[0], email=email, role='both')
    user.set_password('Password1')
    _db.session.add(user)
    _db.session.flush()
    g = CommunityGarden(name=name, slug=name.lower().replace(' ', '-'),
                        organizer_id=user.id)
    _db.session.add(g)
    _db.session.commit()
    return g, user


def test_a_trial_start_engages_the_lead_and_books_a_day_five_check_in(app, db_session):
    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co, lead_status='Working',
              last_contacted_at=_utcnow())
    g, user = _garden('Maple Garden', 'pat@maple.org')

    touched = autonomy.record_platform_event('trial_started', g, user)
    assert touched.id == c.id

    c = _db.session.get(Contact, c.id)
    assert c.lead_status == 'Engaged'
    assert c.platform_status == 'trialing'
    assert c.next_action_at == (_utcnow() + timedelta(days=5)).date()
    assert 'setup call' in c.next_action_note
    assert CrmLeadStatusHistory.query.filter_by(source='platform').count() == 1


def test_paying_makes_them_a_customer_and_closes_a_deal_at_the_real_price(app, db_session):
    from app.pricing import garden_pro_pricing

    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co, lead_status='Engaged',
              next_action_at=date.today())
    op = _operator()
    _db.session.add(CrmAgentAction(action_type='follow_up_email', status='pending',
                                   contact_id=c.id, title='Follow up',
                                   created_by_id=op.id))
    _db.session.commit()
    g, user = _garden('Maple Garden', 'pat@maple.org')

    autonomy.record_platform_event('paid', g, user)

    c = _db.session.get(Contact, c.id)
    assert c.lead_status == 'Customer'
    assert c.platform_status == 'active'
    # Nothing left to chase, and the queued follow-up is withdrawn.
    assert c.next_action_at is None
    assert CrmAgentAction.query.filter_by(status='pending').count() == 0

    deal = Deal.query.one()
    assert deal.stage == 'Closed Won'
    assert deal.amount == pytest.approx(garden_pro_pricing()['yearly'])


def test_an_existing_open_deal_is_won_rather_than_duplicated(app, db_session):
    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co, lead_status='Qualified')
    _db.session.add(Deal(title='Maple — Garden Pro', contact_id=c.id,
                         company_id=co.id, stage='Proposal', amount=240.0))
    _db.session.commit()
    g, user = _garden('Maple Garden', 'pat@maple.org')

    autonomy.record_platform_event('paid', g, user)

    deal = Deal.query.one()          # not two
    assert deal.stage == 'Closed Won'
    assert deal.amount == pytest.approx(240.0)   # a negotiated price is kept


def test_a_lapse_puts_them_back_on_someone_s_list(app, db_session):
    co = _org()
    c = _lead('Pat Grower', 'pat@maple.org', co, lead_status='Customer')
    g, user = _garden('Maple Garden', 'pat@maple.org')

    autonomy.record_platform_event('past_due', g, user)

    c = _db.session.get(Contact, c.id)
    assert c.platform_status == 'past_due'
    assert c.next_action_at == _utcnow().date()
    assert 'offer help' in c.next_action_note
    # They were a customer; a payment failure is not a demotion.
    assert c.lead_status == 'Customer'


def test_an_unmatched_organizer_is_not_an_error(app, db_session):
    """Organizers often sign up from a different address than the scraped
    info@. That is expected, and must not raise inside a payment request."""
    g, user = _garden('Nobody Garden', 'stranger@example.org')
    assert autonomy.record_platform_event('paid', g, user) is None


def test_a_crm_problem_never_breaks_a_payment(app, db_session, monkeypatch):
    co = _org()
    _lead('Pat Grower', 'pat@maple.org', co)
    g, user = _garden('Maple Garden', 'pat@maple.org')

    monkeypatch.setattr(autonomy, '_close_won_deal',
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError('boom')))
    assert autonomy.record_platform_event('paid', g, user) is None


def test_the_queue_has_a_lane_for_who_converted(client, app, db_session):
    client.post('/crm/register', data={'username': 'fhadmin', 'password': 'secret123',
                                       'confirm': 'secret123'}, follow_redirects=True)
    co = _org()
    _lead('Converted Lead', 'won@maple.org', co, lead_status='Customer',
          platform_status='active')
    _lead('Cold Lead', 'cold@maple.org', co)

    body = client.get('/crm/leads?status=platform').data.decode()
    assert 'Converted Lead' in body
    # A Customer is not an open lead, so the due filter must not empty the one
    # view that answers "what did outreach convert".
    assert 'Cold Lead' not in body
