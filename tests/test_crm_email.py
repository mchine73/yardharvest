"""Tests for the CRM's efficient ZeptoMail batch-send campaign path.

Two surfaces are covered, all network-mocked (NO real HTTP):

1. ``app.email_service.send_batch_via_zeptomail`` in isolation — payload
   shape, auth header, regional URL derivation, the unconfigured no-op, and
   non-2xx -> failure.
2. ``new_campaign()`` send path end-to-end via the ``/crm/campaigns/new``
   form POST — that ZEPTOMAIL_TOKEN set yields ONE batch call with opted-out
   contacts excluded from the payload (but still recorded ``opted_out``) and
   correct per-recipient ``merge_info``; and that with the token unset the
   per-contact ``smtp_send`` loop runs N times.

Follows the conventions in ``tests/conftest.py`` / ``tests/test_crm.py``:
temp-file SQLite, WTF_CSRF_ENABLED=False, CRM models under ``app.crm.models``,
first admin seeded via ``/crm/register``.
"""
import os
from unittest import mock

import pytest

from app import db as _db


# ---------------------------------------------------------------------------
# Fixtures (mirror tests/test_crm.py)
# ---------------------------------------------------------------------------
@pytest.fixture()
def crm_clean(app):
    """Wipe crm_* tables before each test so auth/state is deterministic."""
    from app.crm.models import (Activity, Campaign, CampaignRecipient, Company,
                                Contact, CrmUser, Deal, DealContact,
                                EmailTemplate, Note, Task)
    with app.app_context():
        for model in (Activity, CampaignRecipient, Campaign, Note, Task,
                      DealContact, Deal, Contact, Company, EmailTemplate,
                      CrmUser):
            _db.session.query(model).delete()
        _db.session.commit()
    yield


def _register_first_admin(client, username='crmadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password,
                             'confirm': password},
                       follow_redirects=True)


def _seed_audience(app):
    """Create a company + three contacts (one opted out). Returns their ids."""
    from app.crm.models import Company, Contact
    with app.app_context():
        company = Company(name='City of Madison Parks', state='WI',
                          org_type='City-Sponsored', city='Madison')
        _db.session.add(company)
        _db.session.flush()
        ada = Contact(name='Ada Lovelace', email='ada@example.com',
                      company_id=company.id, email_opt_out=False)
        bob = Contact(name='Bob Stone', email='bob@example.com',
                      company_id=company.id, email_opt_out=False)
        carl = Contact(name='Carl Optout', email='carl@example.com',
                       company_id=company.id, email_opt_out=True)
        _db.session.add_all([ada, bob, carl])
        _db.session.commit()
        return company.id, ada.id, bob.id, carl.id


def _post_send(client):
    return client.post('/crm/campaigns/new',
                       data={'name': 'Spring Outreach',
                             'subject': 'Hello {{first_name}}',
                             'body': 'Hi {{first_name}} at {{company}} in {{city}}!',
                             'state': 'WI', 'org_type': '', 'tag': '',
                             'send': 'Send / Log to audience'},
                       follow_redirects=True)


# ---------------------------------------------------------------------------
# 1. The batch function itself
# ---------------------------------------------------------------------------
def test_batch_not_configured_returns_falsy(app):
    """No ZEPTOMAIL_TOKEN -> returns a 'not configured' signal, no HTTP."""
    from app.email_service import send_batch_via_zeptomail
    with app.app_context():
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop('ZEPTOMAIL_TOKEN', None)
            app.config['ZEPTOMAIL_TOKEN'] = ''
            with mock.patch('requests.post') as post:
                result = send_batch_via_zeptomail(
                    [{'email': 'a@x.com', 'merge_info': {'first_name': 'A'}}],
                    'Subj {{first_name}}', '<pre>Body {{first_name}}</pre>')
    assert result['configured'] is False
    assert result['ok'] is False
    post.assert_not_called()


def test_crm_smtp_send_uses_crm_from_address(app):
    """Individual CRM emails send from CRM_FROM_EMAIL (james@yardharvest.app),
    not the platform's no_reply address."""
    from app.crm.helpers import smtp_send
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok-123'}, clear=False):
            os.environ.pop('ZEPTOMAIL_FROM_EMAIL', None)
            os.environ.pop('CRM_FROM_EMAIL', None)
            app.config['ZEPTOMAIL_FROM_EMAIL'] = ''
            app.config['CRM_FROM_EMAIL'] = 'james@yardharvest.app'
            with mock.patch('requests.post', return_value=fake) as post:
                ok = smtp_send('lead@example.com', 'Hi', 'Body text')
    assert ok is True
    assert post.call_args.kwargs['json']['from']['address'] == 'james@yardharvest.app'
    # Personal display name: "James Goodman <james@yardharvest.app>".
    assert post.call_args.kwargs['json']['from']['name'] == 'James Goodman'


def test_crm_smtp_send_falls_back_to_james_when_config_blank(app):
    """Even if CRM_FROM_EMAIL is blank/unset, CRM mail must still send as
    james@yardharvest.app — never the platform no_reply address."""
    from app.crm.helpers import smtp_send
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok-123'}, clear=False):
            os.environ.pop('CRM_FROM_EMAIL', None)
            app.config['CRM_FROM_EMAIL'] = ''            # blank — must not leak no_reply
            app.config['ZEPTOMAIL_FROM_EMAIL'] = 'no_reply@yardharvest.app'
            with mock.patch('requests.post', return_value=fake) as post:
                ok = smtp_send('lead@example.com', 'Hi', 'Body text')
    assert ok is True
    assert post.call_args.kwargs['json']['from']['address'] == 'james@yardharvest.app'


def test_batch_payload_shape_and_auth(app):
    """One POST with from/to[].email_address/merge_info + Zoho auth header."""
    from app.email_service import send_batch_via_zeptomail
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok-123'},
                             clear=False):
            os.environ.pop('ZEPTOMAIL_API_URL', None)
            app.config['ZEPTOMAIL_API_URL'] = ''
            app.config['ZEPTOMAIL_FROM_EMAIL'] = 'sales@yardharvest.com'
            app.config['ZEPTOMAIL_FROM_NAME'] = 'YH Sales'
            with mock.patch('requests.post', return_value=fake) as post:
                result = send_batch_via_zeptomail(
                    [{'email': 'ada@example.com',
                      'merge_info': {'first_name': 'Ada'}},
                     {'email': 'bob@example.com',
                      'merge_info': {'first_name': 'Bob'}}],
                    'Hello {{first_name}}', '<pre>Hi {{first_name}}</pre>')

    assert result == {'ok': True, 'configured': True, 'count': 2, 'status': 201}
    post.assert_called_once()
    args, kwargs = post.call_args
    # Endpoint derived to /email/batch
    assert (args[0] if args else kwargs['url']).endswith('/v1.1/email/batch')
    # Auth header
    assert kwargs['headers']['Authorization'] == 'Zoho-enczapikey tok-123'
    payload = kwargs['json']
    assert payload['from'] == {'address': 'sales@yardharvest.com',
                               'name': 'YH Sales'}
    assert payload['subject'] == 'Hello {{first_name}}'
    assert payload['htmlbody'] == '<pre>Hi {{first_name}}</pre>'
    assert payload['to'] == [
        {'email_address': {'address': 'ada@example.com'},
         'merge_info': {'first_name': 'Ada'}},
        {'email_address': {'address': 'bob@example.com'},
         'merge_info': {'first_name': 'Bob'}},
    ]


def test_batch_honors_regional_url(app):
    """A regional .../v1.1/email host becomes .../v1.1/email/batch."""
    from app.email_service import send_batch_via_zeptomail
    fake = mock.Mock(status_code=200)
    with app.app_context():
        with mock.patch.dict(os.environ,
                             {'ZEPTOMAIL_TOKEN': 'tok',
                              'ZEPTOMAIL_API_URL':
                                  'https://api.zeptomail.eu/v1.1/email'},
                             clear=False):
            with mock.patch('requests.post', return_value=fake) as post:
                send_batch_via_zeptomail(
                    [{'email': 'a@x.com', 'merge_info': {}}], 'S', '<pre>B</pre>')
    # The endpoint is passed positionally (requests.post(url, ...)).
    called_url = post.call_args.args[0] if post.call_args.args \
        else post.call_args.kwargs['url']
    assert called_url == 'https://api.zeptomail.eu/v1.1/email/batch'


def test_batch_non_2xx_is_failure(app):
    """A non-2xx response yields ok=False but configured=True."""
    from app.email_service import send_batch_via_zeptomail
    fake = mock.Mock(status_code=400)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok'},
                             clear=False):
            with mock.patch('requests.post', return_value=fake):
                result = send_batch_via_zeptomail(
                    [{'email': 'a@x.com', 'merge_info': {}}], 'S', '<pre>B</pre>')
    assert result['ok'] is False
    assert result['configured'] is True
    assert result['status'] == 400


# ---------------------------------------------------------------------------
# 2. Campaign send path — batch when ZEPTOMAIL_TOKEN is set
# ---------------------------------------------------------------------------
def test_campaign_uses_single_batch_call(client, crm_clean, app):
    """One batch POST; opted-out excluded from payload but recorded opted_out."""
    _register_first_admin(client)
    cid, ada_id, bob_id, carl_id = _seed_audience(app)

    fake = mock.Mock(status_code=201)
    with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok-xyz'},
                         clear=False):
        with mock.patch('requests.post', return_value=fake) as post:
            resp = _post_send(client)

    assert resp.status_code == 200
    # Two HTTP calls: the batch for all recipients + one operator copy.
    assert post.call_count == 2
    _, kwargs = post.call_args_list[0]          # the batch call
    payload = kwargs['json']
    addresses = {t['email_address']['address'] for t in payload['to']}
    # Opted-out contact (carl) is excluded from the batch payload.
    assert addresses == {'ada@example.com', 'bob@example.com'}
    # Raw templates carry {{tokens}} for server-side substitution.
    assert payload['subject'] == 'Hello {{first_name}}'
    assert '{{first_name}}' in payload['htmlbody']
    # Per-recipient merge_info carries the right values.
    by_addr = {t['email_address']['address']: t['merge_info']
               for t in payload['to']}
    assert by_addr['ada@example.com']['first_name'] == 'Ada'
    assert by_addr['ada@example.com']['company'] == 'City of Madison Parks'
    assert by_addr['ada@example.com']['city'] == 'Madison'
    assert by_addr['bob@example.com']['first_name'] == 'Bob'

    # 2nd call: the single operator copy (one per campaign) to the BCC address.
    _, op_kwargs = post.call_args_list[1]
    op_payload = op_kwargs['json']
    assert [t['email_address']['address'] for t in op_payload['to']] == ['james@yardharvest.app']
    assert op_payload['subject'].startswith('[Campaign sent')

    # Recipient rows: 2 sent (batch ok), 1 opted_out.
    from app.crm.models import CampaignRecipient, Note, Activity
    with app.app_context():
        statuses = sorted(r.status for r in CampaignRecipient.query.all())
        assert statuses == ['opted_out', 'sent', 'sent']
        # Notes/Activities created only for the two sendable contacts.
        assert Note.query.count() == 2
        assert Activity.query.filter_by(kind='email').count() == 2


def test_campaign_batch_failure_records_logged(client, crm_clean, app):
    """Batch non-2xx -> every sendable recipient recorded 'logged', still 1 call."""
    _register_first_admin(client)
    _seed_audience(app)
    fake = mock.Mock(status_code=500)
    with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok'}, clear=False):
        with mock.patch('requests.post', return_value=fake) as post:
            _post_send(client)
    post.assert_called_once()
    from app.crm.models import CampaignRecipient
    with app.app_context():
        statuses = sorted(r.status for r in CampaignRecipient.query.all())
        assert statuses == ['logged', 'logged', 'opted_out']


# ---------------------------------------------------------------------------
# 3. Campaign send path — fallback per-contact loop when token unset
# ---------------------------------------------------------------------------
def test_campaign_fallback_per_contact_loop(client, crm_clean, app):
    """No ZEPTOMAIL_TOKEN -> per-contact smtp_send N times, no batch call."""
    _register_first_admin(client)
    _seed_audience(app)

    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop('ZEPTOMAIL_TOKEN', None)
        # Patch the shared backend used by smtp_send so nothing hits network.
        with mock.patch('app.email_service.send_email', return_value=True) \
                as send_email, \
             mock.patch('requests.post') as post:
            resp = _post_send(client)

    assert resp.status_code == 200
    # No batch HTTP call on the fallback path.
    post.assert_not_called()
    # One send per non-opted-out contact (2 of 3) + one operator copy = 3.
    assert send_email.call_count == 3
    from app.crm.models import CampaignRecipient
    with app.app_context():
        statuses = sorted(r.status for r in CampaignRecipient.query.all())
        assert statuses == ['opted_out', 'sent', 'sent']


# ---------------------------------------------------------------------------
# 4. Operator BCC — every individual CRM email copies CRM_BCC_EMAIL (james@)
# ---------------------------------------------------------------------------
def test_smtp_send_bccs_operator(app):
    """smtp_send adds the operator as BCC on the ZeptoMail payload."""
    from app.crm.helpers import smtp_send
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok'}, clear=False):
            with mock.patch('requests.post', return_value=fake) as post:
                ok = smtp_send('lead@example.com', 'Subject', '<p>Body</p>')
    assert ok is True
    payload = post.call_args.kwargs['json']
    assert payload['bcc'] == [{'email_address': {'address': 'james@yardharvest.app'}}]
    assert [t['email_address']['address'] for t in payload['to']] == ['lead@example.com']


def test_smtp_send_no_self_bcc(app):
    """No BCC copy when the operator IS the direct recipient (no duplicate)."""
    from app.crm.helpers import smtp_send
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok'}, clear=False):
            with mock.patch('requests.post', return_value=fake) as post:
                smtp_send('james@yardharvest.app', 'S', '<p>B</p>')
    assert 'bcc' not in post.call_args.kwargs['json']


def test_send_email_bcc_threads_to_payload(app):
    """send_email(bcc=...) reaches the ZeptoMail payload as a bcc list."""
    from app.email_service import send_email
    fake = mock.Mock(status_code=201)
    with app.app_context():
        with mock.patch.dict(os.environ, {'ZEPTOMAIL_TOKEN': 'tok'}, clear=False):
            with mock.patch('requests.post', return_value=fake) as post:
                send_email('a@b.com', 'S', '<p>B</p>', bcc='ops@yardharvest.app')
    assert post.call_args.kwargs['json']['bcc'] == [
        {'email_address': {'address': 'ops@yardharvest.app'}}]
