"""Pre-send quality gate: placeholder-name detection, the deterministic lint,
the model reviewer, and the cycle's hold-instead-of-send behavior."""
from datetime import date, datetime, timedelta

import pytest

from app import db as _db
from app.crm import agent_service
import app.crm.autonomy as autonomy
from app.crm.models import (AgentSettings, Company, Contact, CrmAgentAction, _utcnow)

NOW = datetime(2026, 7, 14, 15, 0, 0)   # Tue 10:00 America/Chicago


# ---------------------------------------------------------------------------
# Name sanity
# ---------------------------------------------------------------------------
@pytest.mark.parametrize('name,placeholder,first', [
    ('Pat Grower', False, 'Pat'),
    ('Robin', False, 'Robin'),
    ('Dr. Jane Smith', False, 'Jane'),          # honorific skipped
    ('Info — Maple Garden', True, ''),          # our enrichment placeholder
    ('info@maple.org', True, ''),
    ('Garden Coordinator', True, ''),
    ('Volunteer Committee', True, ''),
    ('Community Garden', True, ''),
    ('MAPLE GARDENS', True, ''),
    ('Parks & Recreation Department', True, ''),
    ('', True, ''),
])
def test_placeholder_name_detection(name, placeholder, first):
    assert agent_service.is_placeholder_name(name) is placeholder
    assert agent_service.first_name_of(name) == first


def test_merge_renders_empty_first_name_for_shared_inbox(app):
    """{{first_name}} must render EMPTY for a shared inbox — never "Info" —
    so a misfired "Hi Info," can't reach a real person."""
    from app.crm.helpers import merge_context
    with app.app_context():
        co = Company(name='Maple Garden')
        _db.session.add(co)
        _db.session.flush()
        inbox = Contact(name='Info — Maple Garden', email='info@maple.org', company_id=co.id)
        person = Contact(name='Pat Grower', email='pat@maple.org', company_id=co.id)
        _db.session.add_all([inbox, person])
        _db.session.commit()
        assert merge_context(inbox)['first_name'] == ''
        assert merge_context(person)['first_name'] == 'Pat'


# ---------------------------------------------------------------------------
# Deterministic lint
# ---------------------------------------------------------------------------
def _issues(subject, body, name='Pat Grower'):
    return ' | '.join(agent_service.lint_email(subject, body, contact_name=name))


def test_lint_passes_a_good_email():
    assert agent_service.lint_email(
        'Waitlist season is coming',
        '<p>Hi {{first_name}},</p><p>Plot renewals pile up in February. Our chapter on '
        'waitlists might help: <a href="https://www.yardharvest.app/about/guide/getting-started">'
        'read it</a>.</p><p>Best,</p>', contact_name='Pat Grower') == []


def test_lint_blocks_greeting_a_shared_inbox_by_name():
    out = _issues('plot renewals', '<p>Hi Info,</p><p>Thought this might help.</p>',
                  name='Info — Maple Garden')
    assert 'non-person' in out


def test_lint_blocks_empty_greeting():
    assert 'no name after it' in _issues('hello there', '<p>Hi ,</p><p>Thought this might help.</p>')


def test_lint_blocks_signature_in_body():
    out = _issues('quick note', '<p>Hi Pat,</p><p>Best,<br>James Goodman<br>Founder, '
                                'YardHarvest.app</p>')
    assert 'signature' in out
    assert 'signature' in _issues('quick note', '<p>Hi Pat,</p><p>{{sender_name}}</p>')


def test_lint_blocks_amateur_tells():
    body = ('<p>Hi Pat,</p><p>I hope this email finds you well. I wanted to reach out about '
            '[Garden Name]. THIS IS HUGE!! Reply to me or '
            '<a href="https://www.yardharvest.app/book">book a time</a>.</p>')
    out = _issues('A Very Important Message For You', body)
    for expected in ('Title Case', 'finds you well', 'reach out', '[brackets]',
                     'exclamation', 'ALL CAPS', 'call to action'):
        assert expected in out, f'missing: {expected} — got {out}'


def test_lint_blocks_unknown_merge_tokens_and_length():
    assert 'unknown merge token' in _issues('hi', '<p>Hi {{first_name}}, {{plot_count}} plots</p>')
    assert 'too long' in _issues('hi', '<p>' + ('word ' * 240) + '</p>')


# ---------------------------------------------------------------------------
# Model reviewer
# ---------------------------------------------------------------------------
def _fake_review(monkeypatch, verdict, *, subject='fixed subject', body='<p>fixed</p>', issues=()):
    def fake(subj, bod, **kw):
        fake.calls.append({'subject': subj, 'body': bod, **kw})
        return ({'verdict': verdict, 'issues': list(issues), 'subject': subject, 'body': body},
                {'input_tokens': 5, 'output_tokens': 5})
    fake.calls = []
    monkeypatch.setattr(agent_service, 'review_email', fake)
    return fake


def test_review_email_falls_back_when_ai_unavailable(monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: False)
    out, usage = agent_service.review_email('s', '<p>b</p>', contact_name='Pat',
                                            known_issues=['something'])
    assert out['verdict'] == 'send' and out['issues'] == ['something'] and usage == {}


def test_review_email_passes_recipient_and_flags_to_the_model(monkeypatch):
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    import tests.test_agent_models as tam
    capture = {'response_json': '{"verdict":"send","issues":[],"subject":"s","body":"<p>b</p>"}'}
    tam._install_fake_anthropic(monkeypatch, capture)
    agent_service.review_email('s', '<p>b</p>', contact_name='Info — Maple Garden',
                               company='Maple Garden', known_issues=['greets a non-person'])
    prompt = capture['kwargs']['messages'][0]['content']
    assert 'NOT a person' in prompt and 'greets a non-person' in prompt
    assert capture['model'] == agent_service.QA_MODEL


# ---------------------------------------------------------------------------
# The cycle holds bad drafts instead of sending them
# ---------------------------------------------------------------------------
@pytest.fixture
def cycle_ready(app, client, monkeypatch):
    client.post('/crm/register', data={'username': 'qaadmin', 'password': 'secret123',
                                       'confirm': 'secret123'}, follow_redirects=True)
    sends = []
    monkeypatch.setattr(agent_service, 'is_configured', lambda: True)
    monkeypatch.setattr(autonomy, 'email_ready', lambda: True)
    monkeypatch.setattr(autonomy, 'smtp_send',
                        lambda to, s, b, bcc=True, headers=None: sends.append((to, s)) or True)
    import app.email_service as es
    monkeypatch.setattr(es, 'send_email', lambda *a, **k: True)
    with app.app_context():
        app.config['CRM_MAILING_ADDRESS'] = '123 Garden St'
        app.config['CRM_IMAP_PASSWORD'] = 'x'
        app.config['CRM_IMAP_USER'] = 'james@yardharvest.app'
        s = AgentSettings.get()
        s.autonomy_enabled = True
        s.last_reply_poll_ok_at = _utcnow()
        _db.session.commit()
    yield sends
    with app.app_context():
        for k in ('CRM_MAILING_ADDRESS', 'CRM_IMAP_PASSWORD', 'CRM_IMAP_USER'):
            app.config.pop(k, None)


def _lead(app, name, email):
    with app.app_context():
        co = Company(name=f'{name} Org', city='Lincoln', state='NE')
        _db.session.add(co)
        _db.session.flush()
        c = Contact(name=name, email=email, company_id=co.id, lead_status='Working',
                    next_action_at=date.today())
        _db.session.add(c)
        _db.session.commit()
        return c.id


def _draftr(monkeypatch, subject, body):
    monkeypatch.setattr(agent_service, 'draft_followups',
                        lambda leads, sender_name='', model=None: (
                            [{'lead_id': ld['lead_id'], 'title': 'Follow up', 'rationale': 'due',
                              'subject': subject, 'body': body} for ld in leads],
                            {'input_tokens': 1, 'output_tokens': 1}))


def test_cycle_holds_a_bad_draft_instead_of_sending(app, cycle_ready, monkeypatch):
    cid = _lead(app, 'Pat Grower', 'pat@example.com')
    _draftr(monkeypatch, 'A Very Important Message',
            '<p>Hi Pat,</p><p>I hope this email finds you well.</p><p>Best,<br>James Goodman</p>')
    _fake_review(monkeypatch, 'hold', issues=['fabricated claim about their garden'])
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert cycle_ready == []                      # nothing sent
        assert summary['sent'] == []
        assert summary['held'] and summary['held'][0]['contact'] == 'Pat Grower'
        # the draft is queued for a human, clearly flagged
        a = CrmAgentAction.query.filter_by(contact_id=cid).one()
        assert a.status == 'pending' and a.title.startswith('[Needs review]')
        assert _db.session.get(Contact, cid).followup_count == 0   # cadence untouched


def test_cycle_sends_the_reviewers_corrected_copy(app, cycle_ready, monkeypatch):
    cid = _lead(app, 'Pat Grower', 'pat2@example.com')
    _draftr(monkeypatch, 'Original Subject Line Here', '<p>Hi Pat,</p><p>Original body.</p>')
    _fake_review(monkeypatch, 'fixed', subject='plot renewals coming up',
                 body='<p>Hi {{first_name}},</p><p>Corrected body.</p><p>Best,</p>',
                 issues=['subject was Title Case'])
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert len(cycle_ready) == 1
        # The FIXED subject went out — sentence-cased on the way, because
        # the reviewer's rewrite passes through normalize_subject too.
        assert cycle_ready[0][1] == 'Plot renewals coming up'
        assert summary['fixed'] and summary['fixed'][0]['contact'] == 'Pat Grower'
        a = CrmAgentAction.query.filter_by(contact_id=cid).one()
        assert a.status == 'executed' and a.payload['body'].startswith('<p>Hi {{first_name}}')


def test_cycle_holds_when_a_fix_still_fails_the_lint(app, cycle_ready, monkeypatch):
    """A 'fixed' draft is re-linted — the reviewer can't wave through a bad email."""
    _lead(app, 'Pat Grower', 'pat3@example.com')
    _draftr(monkeypatch, 'ok subject', '<p>Hi Pat,</p><p>Fine.</p>')
    _fake_review(monkeypatch, 'fixed', subject='still bad',
                 body='<p>Hi ,</p><p>Best,<br>James Goodman<br>Founder</p>')
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert cycle_ready == [] and summary['held']


def test_cycle_holds_flagged_draft_when_reviewer_is_down(app, cycle_ready, monkeypatch):
    _lead(app, 'Pat Grower', 'pat4@example.com')
    _draftr(monkeypatch, 'Title Case Subject Line', '<p>Hi Pat,</p><p>Body.</p>')
    monkeypatch.setattr(agent_service, 'review_email',
                        lambda *a, **k: (_ for _ in ()).throw(agent_service.AgentError('down')))
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert cycle_ready == [] and summary['held']


def test_clean_draft_sends_when_reviewer_is_down(app, cycle_ready, monkeypatch):
    _lead(app, 'Pat Grower', 'pat5@example.com')
    _draftr(monkeypatch, 'plot renewals coming up',
            '<p>Hi {{first_name}},</p><p>Short and useful.</p><p>Best,</p>')
    monkeypatch.setattr(agent_service, 'review_email',
                        lambda *a, **k: (_ for _ in ()).throw(agent_service.AgentError('down')))
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert len(cycle_ready) == 1 and summary['held'] == []


def test_digest_lists_held_emails(app, cycle_ready):
    with app.app_context():
        html = autonomy.build_digest_html(
            {'date': 'Tue', 'cap': 15, 'sent': [], 'promoted': [], 'replies': [],
             'held': [{'contact': 'Pat Grower', 'why': 'greets a non-person by name'}],
             'fixed': [{'contact': 'Sam', 'why': 'subject was Title Case'}]},
            AgentSettings.get())
        assert 'Held for your review (1)' in html and 'greets a non-person' in html
        assert 'Auto-corrected before sending' in html


def test_one_email_per_organization_per_day(app, cycle_ready, monkeypatch):
    """Two people at the same garden must not both get a note the same
    morning — that reads as a blast, not a person writing."""
    with app.app_context():
        co = Company(name='Shared Garden', city='Lincoln', state='NE')
        _db.session.add(co)
        _db.session.flush()
        for nm, em in (('Ana Reed', 'ana@shared.org'), ('Ben Cole', 'ben@shared.org')):
            _db.session.add(Contact(name=nm, email=em, company_id=co.id,
                                    lead_status='Working', next_action_at=date.today()))
        _db.session.commit()
    _draftr(monkeypatch, 'plot renewals coming up',
            '<p>Hi {{first_name}},</p><p>Short and useful.</p><p>Best,</p>')
    _fake_review(monkeypatch, 'send', subject='plot renewals coming up',
                 body='<p>Hi {{first_name}},</p><p>Short and useful.</p><p>Best,</p>')
    with app.app_context():
        summary = autonomy.run_daily_cycle(now=NOW, poll=False)
        assert len(summary['sent']) == 1          # one of the two, not both
        assert len(cycle_ready) == 1
