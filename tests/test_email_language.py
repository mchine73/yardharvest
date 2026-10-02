"""An email is written in its RECIPIENT's language.

This is the rule the whole i18n design hangs on, and the one that is easiest
to get wrong without noticing: the sender is a request, the recipient is a
person, and they are rarely the same language. An organizer clicking "send
dues reminders" is ONE English request producing forty messages in forty
members' languages.

The failure it guards against is silent and visible only to the person least
able to report it: they set their language, they believe the product knows,
and everything arrives in English anyway.
"""
import re

import pytest

from app import db as _db, email_service
from app.models import User


@pytest.fixture
def capture(monkeypatch):
    """Capture outbound mail instead of sending it."""
    sent = []
    monkeypatch.setattr(email_service, 'send_email',
                        lambda to, subject, html, **k: sent.append(
                            {'to': to, 'subject': subject, 'html': html}) or True)
    return sent


@pytest.fixture
def member(make_user):
    def _make(email, language):
        u = make_user(username=email.split('@')[0], email=email)
        u.language = language
        _db.session.commit()
        return u
    return _make


def text_of(html):
    """The visible words, with the markup taken out."""
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', html)).strip()


# ---------------------------------------------------------------------------
# The rule
# ---------------------------------------------------------------------------
def test_one_english_request_produces_mail_in_each_recipients_language(
        app, capture, member):
    """The whole point. Two members, two languages, one request."""
    member('ana@example.com', 'es')
    member('bob@example.com', 'en')

    with app.test_request_context('/', headers={'Accept-Language': 'en'}):
        email_service.send_plot_assigned_email('Elm Garden', 'A1',
                                              'ana@example.com', 'Ana')
        email_service.send_plot_assigned_email('Elm Garden', 'A2',
                                              'bob@example.com', 'Bob')

    by_to = {m['to']: m for m in capture}
    assert 'asignaron' in text_of(by_to['ana@example.com']['html'])
    assert 'assigned' in text_of(by_to['bob@example.com']['html'])


def test_the_subject_is_translated_too(app, capture, member):
    """A Spanish body behind an English subject line is still an English email
    in the inbox, which is the only place it is seen before being opened."""
    member('ana@example.com', 'es')
    with app.test_request_context('/', headers={'Accept-Language': 'en'}):
        email_service.send_plot_assigned_email('Elm Garden', 'A1',
                                              'ana@example.com', 'Ana')
    assert 'asignaron' in capture[0]['subject'].lower()


def test_the_shared_footer_is_translated(app, capture, member):
    """The shell wraps every platform email, so leaving it English would put a
    paragraph of English at the bottom of every Spanish message."""
    member('ana@example.com', 'es')
    with app.test_request_context('/'):
        email_service.send_plot_assigned_email('Elm Garden', 'A1',
                                              'ana@example.com', 'Ana')
    body = text_of(capture[0]['html'])
    assert 'Recibiste este correo' in body
    assert 'You received this email' not in body


def test_an_address_with_no_account_changes_nothing(app, capture):
    """A booking guest or an invitee who has not signed up has no stored
    preference; the message must still go out."""
    with app.test_request_context('/', headers={'Accept-Language': 'en'}):
        email_service.send_plot_assigned_email('Elm Garden', 'A1',
                                              'stranger@example.com', 'Sam')
    assert len(capture) == 1
    assert 'assigned' in text_of(capture[0]['html'])


def test_the_language_does_not_leak_into_the_next_message(app, capture, member):
    """force_locale has to restore. Otherwise the first Spanish recipient in a
    batch turns the rest of the batch Spanish — which is exactly the bug the
    per-request refresh was added for, in a different disguise."""
    member('ana@example.com', 'es')
    member('bob@example.com', 'en')

    with app.test_request_context('/', headers={'Accept-Language': 'en'}):
        email_service.send_plot_assigned_email('G', 'A1', 'ana@example.com', 'Ana')
        email_service.send_plot_assigned_email('G', 'A2', 'bob@example.com', 'Bob')
        email_service.send_plot_assigned_email('G', 'A3', 'ana@example.com', 'Ana')

    bodies = [text_of(m['html']) for m in capture]
    assert 'asignaron' in bodies[0]
    assert 'assigned' in bodies[1], 'Spanish leaked into the English recipient'
    assert 'asignaron' in bodies[2]


def test_a_second_email_type_follows_the_same_rule(app, capture, member):
    member('ana@example.com', 'es')
    with app.test_request_context('/'):
        email_service.send_plot_waitlisted_email('Elm Garden',
                                                 'ana@example.com', 'Ana', 3)
    body = text_of(capture[0]['html'])
    assert 'lista de espera' in body
    assert '#3' in body, 'the position placeholder survived translation'


# ---------------------------------------------------------------------------
# Interpolation
# ---------------------------------------------------------------------------
def test_placeholders_are_filled_not_printed(app, capture, member):
    """A dropped or renamed placeholder renders a literal %(name)s to the
    reader, which is the most visible way a translation fails."""
    member('ana@example.com', 'es')
    with app.test_request_context('/'):
        email_service.send_plot_assigned_email('Huerto Elm', 'A1',
                                               'ana@example.com', 'Ana')
    html = capture[0]['html']
    assert '%(' not in html, 'an unfilled placeholder reached the reader'
    assert 'Ana' in html and 'Huerto Elm' in html and 'A1' in html
