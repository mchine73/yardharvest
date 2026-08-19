"""The wiring that lets the CRM see a sale.

Before this, nothing connected a CRM contact to a product account: outreach
could not tell whether a lead ever signed up, and cold intros kept going to
gardens that had already converted. These cover the reconciliation, the
exclusions it enables, the baseline command, the morning brief, and the two
cadence caps.
"""
from datetime import date, datetime, timedelta

import pytest

from app import db as _db
from app.crm import autonomy
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction,
                            CrmUser, _utcnow)
from app.models import CommunityGarden, GardenSubscription, User


def _register_first_admin(client, username='convadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password,
                             'confirm': password},
                       follow_redirects=True)


def _garden(name, organizer_email, *, sub_status=None, trial_end=None):
    """A product-side garden with an organizer, optionally subscribed."""
    user = User(username=organizer_email.split('@')[0], email=organizer_email,
                role='both', display_name='Organizer')
    user.set_password('Password1')
    _db.session.add(user)
    _db.session.flush()
    garden = CommunityGarden(name=name, organizer_id=user.id,
                             slug=name.lower().replace(' ', '-'))
    _db.session.add(garden)
    _db.session.flush()
    if sub_status:
        _db.session.add(GardenSubscription(
            garden_id=garden.id, status=sub_status,
            trial_start=_utcnow() - timedelta(days=3),
            trial_end=trial_end or (_utcnow() + timedelta(days=11))))
    _db.session.commit()
    return garden


def _contact(name, email, **kw):
    c = Contact(name=name, email=email, lead_status=kw.pop('lead_status', 'New'), **kw)
    _db.session.add(c)
    _db.session.commit()
    return c


# ---------------------------------------------------------------------------
# Reconciliation — the link that makes a conversion visible
# ---------------------------------------------------------------------------
def test_reconciliation_records_how_far_each_lead_got(app, db_session):
    """A lead who registered, built a garden, started a trial and paid should
    end up marked 'active' — the best status wins, not the last one seen."""
    _garden('Maple Roots', 'pat@maple.org', sub_status='active')
    _garden('Cedar Plots', 'sam@cedar.org', sub_status='trialing')
    _garden('Elm Beds', 'lee@elm.org')                      # garden, no sub
    registered = User(username='reg', email='reg@example.org', role='both')
    registered.set_password('Password1')
    _db.session.add(registered)

    pat = _contact('Pat', 'PAT@maple.org')                  # case-insensitive
    sam = _contact('Sam', 'sam@cedar.org')
    lee = _contact('Lee', 'lee@elm.org')
    reg = _contact('Reg', 'reg@example.org')
    stranger = _contact('Stranger', 'nobody@example.org')
    _db.session.commit()

    matched, total = autonomy.reconcile_platform_status()

    assert _db.session.get(Contact, pat.id).platform_status == 'active'
    assert _db.session.get(Contact, sam.id).platform_status == 'trialing'
    assert _db.session.get(Contact, lee.id).platform_status == 'garden'
    assert _db.session.get(Contact, reg.id).platform_status == 'registered'
    assert _db.session.get(Contact, stranger.id).platform_status is None
    assert stranger.on_platform is False and pat.on_platform is True
    # Both subscriptions found their lead.
    assert (matched, total) == (2, 2)

    s = AgentSettings.get()
    assert s.last_match_matched == 2 and s.last_match_total == 2
    assert s.last_match_run_at is not None


def test_reconciliation_reports_an_honest_match_rate(app, db_session):
    """An organizer who signed up with a different address than the scraped
    info@ cannot be matched — the rate must say so rather than imply coverage."""
    _garden('Unmatched Garden', 'personal.gmail@example.com', sub_status='active')
    _contact('Info — Unmatched Garden', 'info@unmatched.org')
    _db.session.commit()

    matched, total = autonomy.reconcile_platform_status()
    assert (matched, total) == (0, 1)


def test_a_cancelled_subscription_still_reads_as_on_the_platform(app, db_session):
    """They had a garden and paid once. Cold-emailing them an intro would be
    worse than saying nothing."""
    _garden('Lapsed Garden', 'ex@lapsed.org', sub_status='cancelled')
    c = _contact('Ex', 'ex@lapsed.org')
    _db.session.commit()

    autonomy.reconcile_platform_status()
    assert _db.session.get(Contact, c.id).platform_status == 'expired'
    assert _db.session.get(Contact, c.id).on_platform is True


# ---------------------------------------------------------------------------
# The exclusion the link buys
# ---------------------------------------------------------------------------
def test_cold_outreach_skips_anyone_who_already_has_a_garden(app, db_session):
    from app.crm.autonomy_cycle import _cold_pool, _eligible_due_leads

    fresh = _contact('Fresh Lead', 'fresh@example.org')
    signed = _contact('Signed Up', 'signed@example.org',
                      platform_status='trialing')
    _db.session.commit()

    pool_ids = {c.id for c in _cold_pool()}
    assert fresh.id in pool_ids
    assert signed.id not in pool_ids

    # ...and the due-lead path agrees, even when a human set them due.
    for c in (fresh, signed):
        c.owner_id = None
        c.lead_status = 'Working'
        c.next_action_at = date.today()
    _db.session.commit()
    due_ids = {c.id for c in _eligible_due_leads(AgentSettings.get(), 10)}
    assert fresh.id in due_ids and signed.id not in due_ids


# ---------------------------------------------------------------------------
# Cadence caps
# ---------------------------------------------------------------------------
def test_touch_spacing_spans_more_than_one_weekend():
    """A volunteer coordinator reads garden mail weekly. 4/8 days put three
    emails inside twelve days, which reads as pressure from a stranger."""
    assert autonomy.TOUCH_SPACING_DAYS == [5, 14]


def test_a_silent_lead_is_parked_after_two_nurture_cycles(app, db_session):
    from app.crm.helpers import MAX_NURTURE_CYCLES, resurface_nurture_leads

    first = _contact('First Round', 'first@example.org', lead_status='Nurture',
                     next_action_at=date.today(), nurture_cycles=0)
    last = _contact('Sixth Email', 'sixth@example.org', lead_status='Nurture',
                    next_action_at=date.today(),
                    nurture_cycles=MAX_NURTURE_CYCLES)
    _db.session.commit()

    assert resurface_nurture_leads() == 1

    first = _db.session.get(Contact, first.id)
    assert first.lead_status == 'Working' and first.nurture_cycles == 1

    last = _db.session.get(Contact, last.id)
    assert last.lead_status == 'Nurture'          # parked, not disqualified
    assert last.next_action_at is None
    assert 'Parked' in (last.next_action_note or '')


def test_qualified_leads_stay_in_the_work_queue(app, db_session):
    """Qualifying a lead used to drop it out of every queue — the leads
    furthest down the funnel were the only ones nobody chased."""
    from app.crm.models import LEAD_OPEN_STATUSES
    from app.crm.autonomy_cycle import _needs_human_leads

    assert 'Qualified' in LEAD_OPEN_STATUSES

    owner = CrmUser(username='owner', role='admin')
    owner.set_password('secret123')
    _db.session.add(owner)
    _db.session.flush()
    q = _contact('Qualified Lead', 'q@example.org', lead_status='Qualified',
                 next_action_at=date.today(), owner_id=owner.id)
    _db.session.commit()

    assert q.id in {c.id for c in _needs_human_leads()}


# ---------------------------------------------------------------------------
# The baseline — the answer to "is this thing even running?"
# ---------------------------------------------------------------------------
def test_baseline_answers_whether_the_sender_is_live(app, db_session):
    from app.crm.baseline import build_baseline, render_text

    _contact('Info — Maple Garden', 'info@maple.org')
    named = _contact('Pat Grower', 'pat.grower@maple.org')
    named.company_id = None
    _db.session.commit()

    b = build_baseline()
    # Nothing has been sent and the gates are shut, so it must say so plainly.
    assert b['sends_total'] == 0
    assert b['sender_live'] is False and b['gates']
    # A shared inbox is not a decision-maker; the split has to be visible.
    assert b['supply_named'] == 1 and b['supply_generic'] == 1
    assert b['subs_total'] == 0

    text = render_text(b)
    assert 'SENDER LIVE: NO' in text
    assert 'nobody is on the trial path yet' in text
    assert 'named humans' in text
    # It names the mailbox, so the operator can say whether it is a dedicated
    # sales inbox — which decides how far unmatched-reply surfacing may go.
    assert 'mailbox polled:' in text


def test_baseline_endpoint_is_readonly_and_uncached(client, app):
    _register_first_admin(client)
    r = client.get('/crm/agent/baseline')
    assert r.status_code == 200
    assert r.mimetype == 'text/plain'
    assert r.headers['Cache-Control'] == 'no-store'
    assert b'SENDER LIVE' in r.data


# ---------------------------------------------------------------------------
# The morning brief
# ---------------------------------------------------------------------------
def test_today_brief_gathers_the_five_signals(app, db_session):
    from app.crm.views import _today_brief

    owner = CrmUser(username='briefowner', role='admin')
    owner.set_password('secret123')
    _db.session.add(owner)
    _db.session.flush()

    engaged = _contact('Engaged Lead', 'engaged@example.org',
                       lead_status='Engaged', next_action_at=date.today(),
                       owner_id=owner.id)
    _db.session.add(CrmAgentAction(
        action_type='reply_email', status='pending', contact_id=engaged.id,
        title='Reply to Engaged Lead', created_by_id=owner.id))
    _garden('Ending Soon', 'soon@ending.org', sub_status='trialing',
            trial_end=_utcnow() + timedelta(days=3))
    _db.session.commit()

    brief = _today_brief()
    assert len(brief['replies']) == 1
    assert engaged.id in {c.id for c in brief['human_due']}
    assert [s.garden_obj.name for s in brief['trials_ending']] == ['Ending Soon']
    assert brief['sent_24h'] == 0


def test_console_is_the_landing_page(client, app):
    """A one-person garden SaaS opens to what needs answering, not to a
    weighted pipeline forecast that is $0 by construction."""
    _register_first_admin(client)
    r = client.get('/crm/')
    assert r.status_code == 302 and r.headers['Location'].endswith('/crm/agent')


def test_console_renders_the_brief(client, app):
    _register_first_admin(client)
    r = client.get('/crm/agent')
    assert r.status_code == 200
    body = r.data.decode()
    assert 'replies waiting' in body
    assert 'your leads overdue' in body
    assert 'trials ending / went Pro' in body
    # The baseline panel is lazy — a dozen aggregate queries must not run on
    # every console render for a panel that is collapsed.
    assert 'id="baselinePanel"' in body and 'SENDER LIVE' not in body


# ---------------------------------------------------------------------------
# The digest
# ---------------------------------------------------------------------------
def test_digest_leads_with_what_needs_a_human_and_links_to_the_card(app, db_session):
    from app.crm.autonomy_cycle import build_digest_html, send_daily_digest

    owner = CrmUser(username='digestowner', role='admin')
    owner.set_password('secret123')
    _db.session.add(owner)
    _db.session.flush()
    c = _contact('Reply Person', 'reply@example.org', lead_status='Engaged')
    action = CrmAgentAction(action_type='reply_email', status='pending',
                            contact_id=c.id, title='Reply to Reply Person',
                            created_by_id=owner.id)
    _db.session.add(action)
    _db.session.commit()

    html = build_digest_html({'date': 'Tue', 'cap': 15, 'sent': [],
                              'promoted': [], 'replies': []},
                             AgentSettings.get())
    assert 'Needs you (1)' in html
    # A row you cannot click is a row you cannot act on.
    assert f'/crm/agent#action-{action.id}' in html
    assert 'Reply Person' in html
    # The recap comes after the ask, not before it.
    assert html.index('Needs you') < html.index('Yesterday')


def test_digest_subject_leads_with_the_ask(app, db_session, monkeypatch):
    from app.crm import autonomy_cycle

    owner = CrmUser(username='subjowner', role='admin')
    owner.set_password('secret123')
    _db.session.add(owner)
    _db.session.flush()
    _db.session.add(CrmAgentAction(action_type='reply_email', status='pending',
                                   title='Reply', created_by_id=owner.id))
    _db.session.commit()

    sent = {}
    monkeypatch.setattr(autonomy_cycle, '_notice',
                        lambda s, subj, html: sent.update(subject=subj) or True)
    s = AgentSettings.get()
    s.digest_enabled = True
    _db.session.commit()

    autonomy_cycle.send_daily_digest({'date': 'Tue', 'sent': [], 'replies': []}, s)
    assert sent['subject'].startswith('1 needs you')


# ---------------------------------------------------------------------------
# Lead next actions on the console
# ---------------------------------------------------------------------------
def test_overdue_leads_show_their_next_action_not_just_a_count(client, app, db_session):
    """The note is the instruction — "send the pricing they asked for". A bare
    count tells you something is owed but not what, so it sends you to another
    page to find out."""
    _register_first_admin(client)
    owner = CrmUser.query.first()
    co = Company(name='Maple Roots', city='Lincoln', state='NE')
    _db.session.add(co)
    _db.session.flush()
    late = _contact('Dana Reed', 'dana@maple.org', lead_status='Engaged',
                    company_id=co.id, owner_id=owner.id,
                    next_action_at=date.today() - timedelta(days=3),
                    next_action_note='Send the pricing they asked for')
    _db.session.commit()

    body = client.get('/crm/agent').data.decode()
    assert 'Send the pricing they asked for' in body
    assert 'Dana Reed' in body and 'Maple Roots' in body
    assert '3 days overdue' in body


def test_the_overdue_tile_opens_the_leads_it_counted(client, app, db_session):
    """The tile counts Engaged AND Qualified; it used to link to status=Engaged,
    so a Qualified lead was in the number but missing from the page."""
    _register_first_admin(client)
    owner = CrmUser.query.first()
    engaged = _contact('Engaged Lead', 'e@example.org', lead_status='Engaged',
                       owner_id=owner.id, next_action_at=date.today())
    qualified = _contact('Qualified Lead', 'q@example.org', lead_status='Qualified',
                         owner_id=owner.id, next_action_at=date.today())
    _db.session.commit()

    from app.crm.views import _today_brief
    with app.test_request_context():
        counted = {c.id for c in _today_brief()['human_due']}
    assert counted == {engaged.id, qualified.id}

    listed = client.get('/crm/leads?view=due&status=human').data.decode()
    assert 'Engaged Lead' in listed and 'Qualified Lead' in listed


def test_a_lead_with_no_next_action_written_down_says_so(client, app, db_session):
    """Never-contacted owned leads are due by design; showing a blank cell
    would read as a rendering bug rather than missing information."""
    _register_first_admin(client)
    owner = CrmUser.query.first()
    _contact('No Note', 'n@example.org', lead_status='Engaged', owner_id=owner.id,
             next_action_at=date.today() - timedelta(days=1))
    _db.session.commit()

    body = client.get('/crm/agent').data.decode()
    assert 'No next action written down' in body


# ---------------------------------------------------------------------------
# Scoping the lead queue
# ---------------------------------------------------------------------------
def _scoped(client, **params):
    from urllib.parse import urlencode
    return client.get('/crm/leads?' + urlencode({'view': 'all', **params})).data.decode()


def test_the_queue_can_be_scoped_to_who_can_actually_pay(client, app, db_session):
    """400 imported orgs is not a queue you work top to bottom. A city program
    with a budget line looked identical to a 20-plot volunteer garden."""
    _register_first_admin(client)
    city = Company(name='Parks Department', city='Denver', state='CO',
                   org_type='City-Sponsored')
    indie = Company(name='Maple Roots', city='Lincoln', state='NE',
                    org_type='Independent')
    _db.session.add_all([city, indie])
    _db.session.flush()
    _contact('Dana Parks', 'dana@denver.gov', company_id=city.id)
    _contact('Pat Grower', 'pat@maple.org', company_id=indie.id)
    _db.session.commit()

    scoped = _scoped(client, org_type='City-Sponsored')
    assert 'Dana Parks' in scoped and 'Pat Grower' not in scoped

    by_state = _scoped(client, state='ne')          # case-insensitive
    assert 'Pat Grower' in by_state and 'Dana Parks' not in by_state


def test_the_queue_separates_workable_leads_from_the_enrichment_backlog(client, app, db_session):
    """The agent cannot touch a lead with no address; mixing them in makes the
    queue look four times longer than the work actually available."""
    _register_first_admin(client)
    _contact('Has Email', 'reach@example.org')
    _contact('No Email', None)
    _db.session.commit()

    assert 'Has Email' in _scoped(client, reach='emailable')
    assert 'No Email' not in _scoped(client, reach='emailable')

    backlog = _scoped(client, reach='no_email')
    assert 'No Email' in backlog and 'Has Email' not in backlog


def test_the_queue_can_hide_leads_who_already_signed_up(client, app, db_session):
    _register_first_admin(client)
    _contact('Already In', 'in@example.org', platform_status='trialing')
    _contact('Still Cold', 'cold@example.org')
    _db.session.commit()

    fresh = _scoped(client, platform='no')
    assert 'Still Cold' in fresh and 'Already In' not in fresh
    assert 'Already In' in _scoped(client, platform='yes')


def test_search_matches_the_person_or_the_organization(client, app, db_session):
    _register_first_admin(client)
    co = Company(name='Cedar Plots Collective', city='Omaha', state='NE')
    _db.session.add(co)
    _db.session.flush()
    _contact('Sam Rivers', 'sam@cedar.org', company_id=co.id)
    _contact('Unrelated Person', 'other@example.org')
    _db.session.commit()

    assert 'Sam Rivers' in _scoped(client, q='Cedar Plots')
    assert 'Unrelated Person' not in _scoped(client, q='Cedar Plots')
    assert 'Sam Rivers' in _scoped(client, q='rivers')


def test_scoping_survives_the_status_and_view_switches(client, app, db_session):
    """Losing the filter every time you change tab makes the filters useless."""
    _register_first_admin(client)
    co = Company(name='Parks Department', org_type='City-Sponsored', state='CO')
    _db.session.add(co)
    _db.session.flush()
    _contact('Dana Parks', 'dana@denver.gov', company_id=co.id)
    _db.session.commit()

    body = _scoped(client, org_type='City-Sponsored')
    assert 'org_type=City-Sponsored' in body


def test_the_supply_actions_are_on_the_page_that_shows_the_supply(client, app, db_session):
    """"Find new leads" and "Enrich" used to live only inside a collapsed panel
    on the agent console — not where anyone looks for more leads."""
    _register_first_admin(client)
    body = client.get('/crm/leads').data.decode()
    assert 'Find new leads' in body and 'Enrich' in body
    assert '/crm/agent/scout-web' in body and '/crm/agent/enrich' in body
