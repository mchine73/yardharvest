"""Garden Pro is priced in one place: the admin console.

Every surface that quotes a price — the billing page, the payment modal, trial
emails, the public pricing page, the schema.org offers search engines index —
reads app.pricing.garden_pro_pricing(). A second copy is a copy that
eventually disagrees, and it did: the structured data advertised config.py's
$15/$125 while the checkout charged whatever the console held.
"""
import json

import pytest

from app.models import PricingConfig
from app.pricing import garden_pro_pricing


@pytest.fixture()
def console_price(db_session):
    """Set Garden Pro pricing the way an admin would, and hand back the row."""
    def _set(monthly_cents=6000, yearly_cents=6000, trial_days=21, enabled=True):
        row = PricingConfig.query.first()
        if row is None:
            row = PricingConfig()
            db_session.add(row)
        row.garden_pro_monthly_cents = monthly_cents
        row.garden_pro_yearly_cents = yearly_cents
        row.garden_pro_trial_days = trial_days
        row.garden_pro_enabled = enabled
        db_session.commit()
        return row
    return _set


# ---------------------------------------------------------------------------
# The resolver
# ---------------------------------------------------------------------------
def test_the_resolver_returns_what_the_console_holds(app, console_price):
    console_price(monthly_cents=750, yearly_cents=6000, trial_days=30)
    pro = garden_pro_pricing()
    assert pro['monthly_cents'] == 750 and pro['yearly_cents'] == 6000
    assert pro['monthly'] == 7.5 and pro['yearly'] == 60.0
    assert pro['trial_days'] == 30 and pro['enabled'] is True


def test_with_no_row_it_falls_back_to_the_model_defaults(app, db_session):
    """The column defaults are the single written-down default — not a literal
    repeated in each caller."""
    assert PricingConfig.query.first() is None
    pro = garden_pro_pricing()
    columns = PricingConfig.__table__.columns
    assert pro['monthly_cents'] == columns['garden_pro_monthly_cents'].default.arg
    assert pro['yearly_cents'] == columns['garden_pro_yearly_cents'].default.arg
    assert pro['trial_days'] == columns['garden_pro_trial_days'].default.arg


def test_pricing_never_raises_into_a_page_render(app, db_session, monkeypatch):
    """A pricing lookup runs on the marketing site's every render. A database
    outage takes out the query, not the table metadata, so the resolver must
    still hand back the column defaults rather than 500 the page."""
    class Exploding:
        @staticmethod
        def first():
            raise RuntimeError('database is down')

    monkeypatch.setattr(PricingConfig, 'query', Exploding)
    pro = garden_pro_pricing()
    columns = PricingConfig.__table__.columns
    assert pro['monthly_cents'] == columns['garden_pro_monthly_cents'].default.arg
    assert pro['trial_days'] == columns['garden_pro_trial_days'].default.arg


# ---------------------------------------------------------------------------
# Every surface agrees
# ---------------------------------------------------------------------------
def test_the_public_pricing_page_quotes_the_console(client, app, console_price):
    console_price(monthly_cents=750, yearly_cents=6000, trial_days=21)
    body = client.get('/api/admin/public-pricing').get_json()['garden_pro']
    assert body['monthly'] == 7.5 and body['yearly'] == 60.0
    assert body['trial_days'] == 21


def test_the_structured_data_search_engines_read_quotes_the_console(app, console_price):
    """This is the one that was wrong: schema.org offers came from config.py."""
    from app.seo import _software_jsonld

    console_price(monthly_cents=750, yearly_cents=6000, trial_days=21)
    with app.test_request_context():
        offers = _software_jsonld('https://www.yardharvest.app')['offers']

    prices = {o['price'] for o in offers}
    assert prices == {'7.50', '60.00'}
    assert any('21-day free trial' in o['name'] for o in offers)


def test_billing_and_email_read_the_same_resolver(app, console_price):
    from app.api.garden_billing_api import _get_pro_pricing
    from app.email_service import _pro_pricing

    console_price(monthly_cents=750, yearly_cents=6000, trial_days=21)
    assert _get_pro_pricing() == _pro_pricing() == garden_pro_pricing()


def test_a_trial_email_quotes_the_console_price(app, db_session, make_user,
                                                console_price, monkeypatch):
    import app.email_service as es
    from app.models import CommunityGarden

    console_price(monthly_cents=750, yearly_cents=6000)
    organizer = make_user(username='priced', email='priced@example.com')
    garden = CommunityGarden(name='Wallstreet Garden', slug='wallstreet-garden',
                             organizer_id=organizer.id)
    db_session.add(garden)
    db_session.commit()

    captured = {}
    monkeypatch.setattr(es, 'send_email',
                        lambda to, subject, html, **kw: captured.update(html=html) or True)
    with app.test_request_context():
        es.send_garden_trial_reengagement(garden, organizer)

    assert '$60/year' in captured['html']
    assert '$125' not in captured['html']


# ---------------------------------------------------------------------------
# No second copy anywhere
# ---------------------------------------------------------------------------
def test_no_surface_hardcodes_a_garden_pro_price():
    """Grep is the test here on purpose: the failure mode is somebody adding a
    literal back, and only a source scan catches that."""
    import io
    import pathlib

    root = pathlib.Path(__file__).resolve().parent.parent
    offenders = []

    # Server: the config keys are retired; nothing may reintroduce them.
    for path in (root / 'config.py',):
        text = io.open(path, encoding='utf-8').read()
        for key in ('GARDEN_PRO_PRICE_MONTHLY =', 'GARDEN_PRO_PRICE_YEARLY =',
                    'GARDEN_TRIAL_DAYS ='):
            if key in text:
                offenders.append(f'{path.name}: {key}')

    # Client: a price must arrive from the server, never a literal default.
    for rel in ('frontend/src/components/GardenPaymentModal.jsx',
                'frontend/src/pages/gardens/GardenBilling.jsx',
                'frontend/src/pages/Pricing.jsx'):
        text = io.open(root / rel, encoding='utf-8').read()
        for literal in ('monthly: 15', 'yearly: 125'):
            if literal in text:
                offenders.append(f'{rel}: {literal}')

    assert not offenders, 'hardcoded Garden Pro price: ' + '; '.join(offenders)


def test_llms_txt_quotes_the_console(client, console_price):
    """llms.txt said $15/$125 for months while checkout charged the console's
    price - and it is the page answer engines quote verbatim."""
    console_price(monthly_cents=750, yearly_cents=6000, trial_days=21)
    body = client.get('/llms.txt').get_data(as_text=True)
    assert '$7.50/month or $60/year' in body
    assert '21-day free trial' in body
    assert '$15/month' not in body and '$125/year' not in body


def test_the_faq_structured_data_quotes_the_console(app, console_price):
    from app.seo import _faq_page_jsonld

    console_price(monthly_cents=750, yearly_cents=6000, trial_days=21)
    with app.test_request_context():
        answers = {e['name']: e['acceptedAnswer']['text']
                   for e in _faq_page_jsonld()['mainEntity']}
    pro = answers['What does Garden Pro cost, and what does it add?']
    assert pro.startswith('$7.50 a month or $60 a year')
    assert 'free trial of 21 days' in pro
    assert not any('{{' in a for a in answers.values())


@pytest.mark.parametrize('fee,says,never', [
    (0, 'YardHarvest takes nothing', 'keeps'),
    (2.5, 'YardHarvest keeps 2.5% of each payment', 'takes nothing'),
])
def test_the_faq_never_says_no_cut_while_one_is_set(client, app, console_price,
                                                     db_session, fee, says, never):
    """The fee is an admin setting. The public endpoint carries it, and both
    the page and the structured data answer from it."""
    from app.seo import _faq_page_jsonld

    row = console_price()
    row.garden_dues_fee_percent = fee
    db_session.commit()
    assert client.get('/api/admin/public-pricing').get_json()['garden'] == {
        'dues_fee_percent': fee}
    with app.test_request_context():
        answer = next(e['acceptedAnswer']['text'] for e in _faq_page_jsonld()['mainEntity']
                      if e['name'] == 'Does YardHarvest take a cut of what we collect?')
    assert says in answer and never not in answer
