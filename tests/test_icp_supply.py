"""Who gets worked first, and keeping the pool from running dry.

The cold pool was ranked by a Sonnet call over the first 40 rows by id — it
never saw most of the pool, cost money every cycle to answer a question with
no judgement in it, and led with independents while the thesis says the payers
are operators, nonprofits and city programs. Supply was two buttons a human
had to remember to press.
"""
import pytest

from app import db as _db
from app.crm import icp
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentRun, Note,
                            PAYER_ORG_TYPES, _utcnow)


def _org(name, **kw):
    co = Company(name=name, **kw)
    _db.session.add(co)
    _db.session.commit()
    return co


def _lead(name, email, company=None, **kw):
    c = Contact(name=name, email=email, lead_status=kw.pop('lead_status', 'New'),
                company_id=company.id if company else None, **kw)
    _db.session.add(c)
    _db.session.commit()
    return c


# ---------------------------------------------------------------------------
# Telling a person from a mailbox
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('name,email,expected', [
    ('Pat Grower', 'pat@maple.org', True),
    ('Dana Reed', 'd.reed@denver.gov', True),
    ('Info — Maple Roots', 'info@maple.org', False),   # our own placeholder
    ('Info', 'info@maple.org', False),
    ('Garden Coordinator', 'coordinator@maple.org', False),
    ('Pat Grower', 'info@maple.org', False),           # role address wins
    ('Maple', 'hello@maple.org', False),               # one word, role address
    ('', 'pat@maple.org', False),
])
def test_a_named_person_is_told_from_a_shared_inbox(app, db_session, name, email, expected):
    """The same question decides the greeting and whether the lead is worth a
    slot — "Hi Info," is the most embarrassing thing the agent can send."""
    assert icp.is_named_human(_lead(name, email)) is expected


# ---------------------------------------------------------------------------
# The score
# ---------------------------------------------------------------------------
def test_an_operator_with_a_named_contact_outranks_a_bare_volunteer_garden(app, db_session):
    operator = _org('Cedar Collective', org_type='Nonprofit/Operator',
                    website='https://cedar.org', sites_count=6)
    volunteer = _org('Maple Roots', org_type='Independent')
    best = _lead('Dana Reed', 'dana@cedar.org', operator, title='Executive Director')
    worst = _lead('Info — Maple Roots', 'info@maple.org', volunteer)

    ranked = icp.rank([worst, best], operator_weight=2.0)
    assert [r['contact'].id for r in ranked] == [best.id, worst.id]
    # (named 1 + title 1 + website 1 + multi-site 2) x 2.0
    assert ranked[0]['score'] == pytest.approx(10.0)
    assert ranked[1]['score'] == pytest.approx(0.0)
    assert 'Executive Director' in ' '.join(ranked[0]['why'])
    assert 'runs 6 sites' in ' '.join(ranked[0]['why'])


def test_the_operator_weight_is_a_setting_not_a_belief(app, db_session):
    """2.0 is the GTM thesis, not a measurement. Setting it to 1.0 must make
    org type stop mattering, so the thesis can be abandoned on evidence."""
    payer = _org('Parks Department', org_type='City-Sponsored', website='https://d.gov')
    indie = _org('Maple Roots', org_type='Independent', website='https://maple.org')
    a = _lead('Dana Reed', 'dana@d.gov', payer)
    b = _lead('Pat Grower', 'pat@maple.org', indie)

    assert [r['contact'].id for r in icp.rank([b, a], 2.0)] == [a.id, b.id]
    neutral = icp.rank([b, a], 1.0)
    assert {r['score'] for r in neutral} == {2.0}      # tie
    assert [r['contact'].id for r in neutral] == [a.id, b.id]   # tie breaks on id


def test_ranking_is_stable_across_reruns(app, db_session):
    """A cycle that reruns must pick the same leads, not reshuffle equals."""
    co = _org('Maple Roots', org_type='Independent')
    leads = [_lead(f'Pat {i} Grower', f'p{i}@maple.org', co) for i in range(5)]
    first = [r['contact'].id for r in icp.rank(leads, 2.0)]
    assert first == [r['contact'].id for r in icp.rank(list(reversed(leads)), 2.0)]


def test_the_sql_score_agrees_with_the_python_one(app, db_session):
    """One orders the pool, the other explains a row. If they disagree the
    reason shown never matches the position."""
    from sqlalchemy import select
    operator = _org('Cedar Collective', org_type='Nonprofit/Operator',
                    website='https://cedar.org', sites_count=4)
    indie = _org('Maple Roots', org_type='Independent')
    a = _lead('Dana Reed', 'dana@cedar.org', operator, title='Director')
    b = _lead('Pat Grower', 'pat@maple.org', indie)

    expr = icp.score_expression(2.0)
    rows = _db.session.execute(
        select(Contact.id, expr).outerjoin(Company, Contact.company_id == Company.id)
    ).all()
    from_sql = {cid: float(score) for cid, score in rows}
    for contact in (a, b):
        python_score, _ = icp.score_contact(contact, 2.0)
        assert from_sql[contact.id] == pytest.approx(python_score)


def test_the_cold_pool_is_ordered_by_the_score_not_by_id(app, db_session):
    """The old ranker read the first 40 rows by id, so a good lead imported
    late was never seen."""
    from app.crm.autonomy_cycle import _cold_pool

    indie = _org('Maple Roots', org_type='Independent')
    for i in range(3):
        _lead(f'Info — Maple {i}', f'info{i}@maple.org', indie)
    operator = _org('Cedar Collective', org_type='Nonprofit/Operator',
                    website='https://cedar.org', sites_count=8)
    late = _lead('Dana Reed', 'dana@cedar.org', operator, title='Director')

    assert _cold_pool(10)[0].id == late.id


# ---------------------------------------------------------------------------
# Typing the organizations we already hold
# ---------------------------------------------------------------------------
def test_the_importer_stops_flattening_nonprofits(app):
    from app.crm.views import _normalize_org_type

    with app.app_context():
        assert _normalize_org_type('nonprofit') == 'Nonprofit/Operator'
        assert _normalize_org_type('501(c)(3)') == 'Nonprofit/Operator'
        assert _normalize_org_type('collective') == 'Nonprofit/Operator'
        # A city program is still the more specific answer.
        assert _normalize_org_type('Parks Department') == 'City-Sponsored'
        assert _normalize_org_type('community garden') == 'Independent'
        assert _normalize_org_type('nonsense') == ''


def test_the_backfill_types_orgs_from_text_we_already_have(app, db_session):
    trust = _org('Riverside Land Trust')
    parks = _org('City of Denver Parks and Recreation')
    plain = _org('Maple Roots')
    _db.session.add(Note(company_id=plain.id,
                         content='Fit: coordinates 7 community gardens across the north side.'))
    _db.session.commit()

    changed = icp.backfill_org_types()
    assert _db.session.get(Company, trust.id).org_type == 'Nonprofit/Operator'
    assert _db.session.get(Company, parks.id).org_type == 'City-Sponsored'
    plain = _db.session.get(Company, plain.id)
    assert plain.sites_count == 7 and plain.org_type == 'Nonprofit/Operator'
    assert changed['typed'] == 3 and changed['sites'] == 1


def test_the_backfill_never_overwrites_a_decision_somebody_made(app, db_session):
    co = _org('Riverside Land Trust', org_type='Independent', sites_count=1)
    icp.backfill_org_types()
    co = _db.session.get(Company, co.id)
    assert co.org_type == 'Independent' and co.sites_count == 1


def test_a_dry_run_writes_nothing(app, db_session):
    co = _org('Riverside Land Trust')
    changed = icp.backfill_org_types(dry_run=True)
    assert changed['typed'] == 1
    assert _db.session.get(Company, co.id).org_type in (None, '')


def test_an_implausible_site_count_is_not_believed(app, db_session):
    """"400 gardens" in a grant blurb is a parse error, not an operator."""
    co = _org('Maple Roots')
    _db.session.add(Note(company_id=co.id,
                         content='Serves a network of 400 gardens statewide.'))
    _db.session.commit()
    icp.backfill_org_types()
    assert _db.session.get(Company, co.id).sites_count is None


# ---------------------------------------------------------------------------
# Enrichment order and the retry window
# ---------------------------------------------------------------------------
def test_enrichment_goes_after_the_orgs_that_publish_staff_pages_first(app, db_session):
    """Under the no-fabrication rule the only legal path to a decision-maker's
    address is a page that publishes one — which payers do and volunteer
    gardens don't. So the order IS the acquisition strategy."""
    from app.crm.views import _enrichment_targets

    indie = _org('Maple Roots', org_type='Independent')
    city = _org('Parks Department', org_type='City-Sponsored')
    big = _org('Cedar Collective', org_type='Nonprofit/Operator', sites_count=9)

    order = [c.id for c in _enrichment_targets().all()]
    assert order.index(big.id) < order.index(indie.id)
    assert order.index(city.id) < order.index(indie.id)
    # Among payers, the one running more sites is worth more.
    assert order.index(big.id) < order.index(city.id)


def test_a_company_we_already_searched_is_not_retried_for_90_days(app, db_session):
    """It used to chew the same first fifteen rows on every click and never
    reach the tail of the list."""
    from datetime import timedelta
    from app.crm.views import ENRICH_RETRY_DAYS, _enrichment_targets

    fresh = _org('Never Tried', org_type='Independent')
    just_done = _org('Just Tried', org_type='Independent',
                     enrich_attempted_at=_utcnow())
    long_ago = _org('Tried Long Ago', org_type='Independent',
                    enrich_attempted_at=_utcnow() - timedelta(days=ENRICH_RETRY_DAYS + 1))
    _db.session.commit()

    ids = [c.id for c in _enrichment_targets().all()]
    assert fresh.id in ids and long_ago.id in ids
    assert just_done.id not in ids
    # Never-attempted comes before one we looked at three months ago.
    assert ids.index(fresh.id) < ids.index(long_ago.id)


def test_an_org_with_an_emailable_contact_is_not_a_target(app, db_session):
    from app.crm.views import _enrichment_targets

    covered = _org('Has Contact', org_type='Independent')
    _lead('Pat Grower', 'pat@has.org', covered)
    assert covered.id not in [c.id for c in _enrichment_targets().all()]


# ---------------------------------------------------------------------------
# The spend breaker
# ---------------------------------------------------------------------------
def test_the_cycle_stops_when_the_day_s_ai_budget_is_spent(app, db_session):
    """Enrichment and scouting can now fire unattended, so a stuck loop
    quietly spending all night is the failure worth engineering against."""
    from app.crm.autonomy_cycle import ai_spend_today, cycle_gates, local_now

    settings = AgentSettings.get()
    settings.daily_ai_budget_usd = 5
    _db.session.add(CrmAgentRun(kind='autonomous', status='done', cost_usd=6.0))
    _db.session.commit()

    now_local = local_now(settings)
    spent, budget = ai_spend_today(settings, now_local)
    assert spent == pytest.approx(6.0) and budget == pytest.approx(5.0)
    assert any('AI budget' in g for g in cycle_gates(settings, now_local))


def test_spend_from_a_previous_day_does_not_block_today(app, db_session):
    from datetime import timedelta
    from app.crm.autonomy_cycle import ai_spend_today, local_now

    settings = AgentSettings.get()
    settings.daily_ai_budget_usd = 5
    old = CrmAgentRun(kind='autonomous', status='done', cost_usd=99.0)
    _db.session.add(old)
    _db.session.commit()
    old.created_at = _utcnow() - timedelta(days=2)
    _db.session.commit()

    spent, _ = ai_spend_today(settings, local_now(settings))
    assert spent == pytest.approx(0.0)


def test_a_zero_budget_means_no_ceiling(app, db_session):
    from app.crm.autonomy_cycle import ai_spend_today, local_now

    settings = AgentSettings.get()
    settings.daily_ai_budget_usd = 0
    _db.session.add(CrmAgentRun(kind='autonomous', status='done', cost_usd=500.0))
    _db.session.commit()
    assert ai_spend_today(settings, local_now(settings)) == (0.0, 0.0)


# ---------------------------------------------------------------------------
# Keeping the pool full without being asked
# ---------------------------------------------------------------------------
def test_supply_tops_up_only_when_the_pool_is_thin(app, db_session, monkeypatch):
    import app.crm.autonomy_cycle as cyc

    settings = AgentSettings.get()
    settings.auto_enrich = True
    settings.daily_ai_budget_usd = 5
    _db.session.commit()

    calls = []
    monkeypatch.setattr(cyc, '_runway', lambda s: {'due': 99, 'cold': 99, 'days': 30})
    monkeypatch.setattr('app.crm.views._async_enrich',
                        lambda ids, actor: calls.append(ids) or {})
    summary = {'errors': []}
    cyc._top_up_supply(settings, summary, cyc._Usage(), cyc.local_now(settings))
    assert calls == []                       # plenty of runway, nothing to do

    monkeypatch.setattr(cyc, '_runway', lambda s: {'due': 1, 'cold': 0, 'days': 0})
    _org('Needs Enrichment', org_type='Nonprofit/Operator')
    cyc._top_up_supply(settings, summary, cyc._Usage(), cyc.local_now(settings))
    assert calls and len(calls[0]) == 1


def test_supply_respects_the_budget_and_says_so(app, db_session, monkeypatch):
    import app.crm.autonomy_cycle as cyc

    settings = AgentSettings.get()
    settings.auto_enrich = True
    settings.daily_ai_budget_usd = 5
    _db.session.add(CrmAgentRun(kind='autonomous', status='done', cost_usd=9.0))
    _org('Needs Enrichment', org_type='Nonprofit/Operator')
    _db.session.commit()

    calls = []
    monkeypatch.setattr(cyc, '_runway', lambda s: {'due': 0, 'cold': 0, 'days': 0})
    monkeypatch.setattr('app.crm.views._async_enrich',
                        lambda ids, actor: calls.append(ids) or {})
    summary = {'errors': []}
    cyc._top_up_supply(settings, summary, cyc._Usage(), cyc.local_now(settings))

    assert calls == []
    assert any('budget is spent' in line for line in summary['supply'])


def test_scouting_does_not_pile_up_proposals_nobody_approved(app, db_session, monkeypatch):
    import app.crm.autonomy_cycle as cyc
    from app.crm.models import CrmAgentAction, CrmUser

    op = CrmUser(username='op', role='admin')
    op.set_password('secret123')
    _db.session.add(op)
    _db.session.flush()
    settings = AgentSettings.get()
    settings.auto_new_leads = True
    settings.operator_user_id = op.id
    for i in range(cyc.MAX_PENDING_NEW_LEADS):
        _db.session.add(CrmAgentAction(action_type='new_lead', status='pending',
                                       title=f'New lead {i}', created_by_id=op.id))
    _db.session.commit()

    calls = []
    monkeypatch.setattr(cyc, '_runway', lambda s: {'due': 0, 'cold': 0, 'days': 0})
    monkeypatch.setattr('app.crm.views._async_scout_web',
                        lambda focus, exclude, actor: calls.append(focus) or {})
    summary = {'errors': []}
    cyc._top_up_supply(settings, summary, cyc._Usage(), cyc.local_now(settings))

    assert calls == []
    assert any('already waiting' in line for line in summary['supply'])


def test_supply_stays_off_unless_switched_on(app, db_session, monkeypatch):
    import app.crm.autonomy_cycle as cyc

    settings = AgentSettings.get()
    settings.auto_enrich = False
    settings.auto_new_leads = False
    _db.session.commit()

    monkeypatch.setattr(cyc, '_runway', lambda s: {'due': 0, 'cold': 0, 'days': 0})
    monkeypatch.setattr('app.crm.views._async_enrich',
                        lambda ids, actor: pytest.fail('should not enrich'))
    summary = {'errors': []}
    cyc._top_up_supply(settings, summary, cyc._Usage(), cyc.local_now(settings))
    assert 'supply' not in summary


def test_a_bare_county_no_longer_types_a_community_group_as_a_city_program(app, db_session):
    """"Khmer Community of Seattle King County" is a community organization.
    A mis-typed payer is worse than an untyped one — it sends the wrong CTA
    and pulls enrichment away from orgs that would have answered."""
    misread = _org('Khmer Community of Seattle King County')
    real = _org('King County Parks')
    icp.backfill_org_types()

    assert _db.session.get(Company, misread.id).org_type in (None, '')
    assert _db.session.get(Company, real.id).org_type == 'City-Sponsored'


def test_correcting_the_importer_bug_is_opt_in(app, db_session):
    """~121 orgs are stamped 'Independent' because the importer mapped
    nonprofit that way. That is a bug's output, not a decision — but keyword
    evidence is not proof, so rewriting it needs asking for."""
    flattened = _org('Tulsa Urban Ag Coalition', org_type='Independent')
    genuine = _org('Maple Roots', org_type='Independent')

    default = icp.backfill_org_types()
    assert default['retyped'] == 0
    assert _db.session.get(Company, flattened.id).org_type == 'Independent'

    corrected = icp.backfill_org_types(retype_flattened=True)
    assert corrected['retyped'] == 1
    assert _db.session.get(Company, flattened.id).org_type == 'Nonprofit/Operator'
    # An org with no contrary evidence keeps what it had.
    assert _db.session.get(Company, genuine.id).org_type == 'Independent'


def test_the_backfill_reports_each_change_so_it_can_be_read_first(app, db_session):
    _org('Riverside Land Trust')
    _org('Tulsa Urban Ag Coalition', org_type='Independent')
    result = icp.backfill_org_types(dry_run=True, retype_flattened=True)

    by_name = {name: (was, now) for name, was, now in result['changes']}
    assert by_name['Riverside Land Trust'] == ('(untyped)', 'Nonprofit/Operator')
    assert by_name['Tulsa Urban Ag Coalition'] == ('Independent', 'Nonprofit/Operator')


# ---------------------------------------------------------------------------
# One taxonomy, shared by everything that writes an org type
# ---------------------------------------------------------------------------
def test_whatever_a_writer_produces_is_a_type_the_readers_know(app, db_session):
    """The real contract, checked as behaviour rather than by grepping source:
    every path that writes an org_type must emit a value the queue filter and
    the ICP score recognise. The scout used to emit a bare 'Nonprofit', which
    neither did — so its payers scored as volunteer gardens."""
    import json
    from app.crm.agent_service import _parse_lead_array
    from app.crm.models import ORG_TYPE_CHOICES, normalize_org_type

    vocabularies = [
        'Nonprofit', 'nonprofit', 'Non-Profit', '501(c)(3)', 'Operator',
        'network', 'collective', 'coalition', 'land trust',
        'City-Sponsored', 'city parks program', 'Municipal', 'Parks Dept',
        'Independent', 'community garden', 'indie',
        'something nobody planned for', '', None,
    ]
    for raw in vocabularies:
        assert normalize_org_type(raw) in ORG_TYPE_CHOICES + ['']

        payload = json.dumps([{'name': 'X', 'city': 'T', 'state': 'OK',
                               'org_type': raw, 'website': '',
                               'contact_name': '', 'contact_email': '',
                               'contact_title': '', 'fit': 'f',
                               'source_url': 'https://x.org/a'}])
        scouted = _parse_lead_array(payload)[0]['org_type']
        assert scouted in ORG_TYPE_CHOICES + [''], f'{raw!r} -> {scouted!r}'


def test_a_scouted_nonprofit_lands_where_the_score_can_see_it(app, db_session):
    """End to end, this was the bug: the scout found a 12-garden operator and
    filed it as 'Nonprofit', which scored the same as a volunteer garden."""
    import json
    from app.crm.agent_service import _parse_lead_array
    from app.crm.models import ORG_TYPE_CHOICES

    payload = json.dumps([{
        'name': 'Tulsa Urban Ag Coalition', 'city': 'Tulsa', 'state': 'OK',
        'org_type': 'Nonprofit', 'sites_count': 12, 'website': 'https://tuac.org',
        'contact_name': 'Dana Reed', 'contact_email': 'dana@tuac.org',
        'contact_title': 'Executive Director', 'fit': 'Runs 12 gardens.',
        'source_url': 'https://tuac.org/about'}])
    lead = _parse_lead_array(payload)[0]

    assert lead['org_type'] == 'Nonprofit/Operator'
    assert lead['org_type'] in ORG_TYPE_CHOICES
    assert lead['org_type'] in PAYER_ORG_TYPES
    assert icp.org_weight(lead['org_type'], 2.0) == 2.0
    assert lead['sites_count'] == 12


def test_the_scout_will_not_report_an_implausible_site_count(app, db_session):
    import json
    from app.crm.agent_service import _parse_lead_array

    def parsed(sites):
        payload = json.dumps([{'name': 'X', 'city': 'T', 'state': 'OK',
                               'org_type': 'Independent', 'sites_count': sites,
                               'website': '', 'contact_name': '', 'contact_email': '',
                               'contact_title': '', 'fit': 'f',
                               'source_url': 'https://x.org/a'}])
        return _parse_lead_array(payload)[0]['sites_count']

    assert parsed(12) == 12
    assert parsed(400) is None      # a misread number, not an operator
    assert parsed(1) is None        # tells us nothing
    assert parsed('lots') is None


def test_the_backfill_repairs_a_type_no_reader_recognises(app, db_session):
    """Rows the old scout already wrote say 'Nonprofit'. Renaming to the
    canonical form is a correction, not a judgement — no opt-in needed."""
    stray = _org('Tulsa Urban Ag Coalition', org_type='Nonprofit')
    result = icp.backfill_org_types()

    assert _db.session.get(Company, stray.id).org_type == 'Nonprofit/Operator'
    assert result['retyped'] == 1
