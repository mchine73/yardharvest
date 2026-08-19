"""Platform emails must look like the site, whatever is in the config row.

The header wordmark is white, so ``header_color`` is not a free choice: a light
value renders white-on-light. A leftover green from the marketplace-era palette
did exactly that in production — 2.5:1, well under AA — so the shell now checks
the colour rather than trusting it.
"""
import pytest

from app.email_service import (BRAND_INK, BRAND_LIME, BRAND_MUTED,
                               _contrast_with_white, _relative_luminance,
                               header_band_color)


# The green that was actually rendering in the trial re-engagement email.
LEGACY_GREEN = '#5cb85c'


# ---------------------------------------------------------------------------
# The contrast guard
# ---------------------------------------------------------------------------
def test_the_legacy_green_header_failed_aa_with_white_text():
    """Guard the regression itself: if this ever passes, the guard below is
    testing nothing."""
    assert _contrast_with_white(LEGACY_GREEN) < 4.5
    assert _contrast_with_white(BRAND_INK) >= 4.5


@pytest.mark.parametrize('configured', [
    LEGACY_GREEN,          # the one from the screenshot
    BRAND_LIME,            # lime is a background for INK text, never white
    '#ffffff',
    '#e3ff8f',
    'not-a-colour',        # a fat-fingered admin value must not render raw
    '',
    None,
])
def test_a_header_white_text_cannot_sit_on_falls_back_to_ink(configured):
    assert header_band_color(configured) == BRAND_INK


@pytest.mark.parametrize('configured', [
    '#166f4c',             # the pre-redesign default: dark enough, still legible
    '#22242a',
    '#1a3d5c',
])
def test_a_dark_brand_colour_is_left_alone(configured):
    """The knob still works — this is a contrast floor, not a lockout."""
    assert header_band_color(configured) == configured


def test_shorthand_hex_is_understood():
    assert header_band_color('#222') == '#222'
    assert header_band_color('#fff') == BRAND_INK


def test_relative_luminance_matches_the_wcag_endpoints():
    assert _relative_luminance('#000000') == pytest.approx(0.0)
    assert _relative_luminance('#ffffff') == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# What actually renders
# ---------------------------------------------------------------------------
def test_a_drifted_config_row_still_renders_an_on_brand_header(app, db_session):
    """End to end: the row says green, the email says ink."""
    from app.email_service import _render
    from app.models import SiteEmailConfig

    _db = db_session
    _db.add(SiteEmailConfig(header_color=LEGACY_GREEN,
                            tagline='Neighbors gardening with neighbors'))
    _db.commit()

    with app.test_request_context():
        html = _render('<p>Body copy.</p>')

    assert LEGACY_GREEN not in html
    assert f'background-color: {BRAND_INK}' in html


def test_the_shell_carries_the_brand(app, db_session):
    from app.email_service import _render

    with app.test_request_context():
        html = _render('<p>Body copy.</p>')

    assert BRAND_LIME in html          # the CTA and the header rule
    assert BRAND_INK in html
    assert 'Onest' in html             # brand typeface, with a system fallback


def test_no_pre_redesign_greys_or_greens_remain_in_the_email_service():
    """These crept in one email at a time. #888/#666 are not the brand's grey
    and #2d6a2e is from the old palette."""
    import io
    import app.email_service as es

    source = io.open(es.__file__, encoding='utf-8').read()
    for stale in ('#888', '#666', '#2d6a2e'):
        assert stale not in source, f'{stale} is not a brand colour'
    assert BRAND_MUTED in source


def test_the_reengagement_email_is_on_brand_and_priced_from_config(app, db_session,
                                                                   make_user, monkeypatch):
    """The email in question, rendered end to end."""
    import app.email_service as es
    from app.models import CommunityGarden, SiteEmailConfig

    db_session.add(SiteEmailConfig(header_color=LEGACY_GREEN))
    organizer = make_user(username='organiser', email='organiser@example.com')
    garden = CommunityGarden(name='Wallstreet Garden', slug='wallstreet-garden',
                             organizer_id=organizer.id)
    db_session.add(garden)
    db_session.commit()

    captured = {}
    monkeypatch.setattr(es, 'send_email',
                        lambda to, subject, html, **kw: captured.update(
                            to=to, subject=subject, html=html) or True)

    with app.test_request_context():
        es.send_garden_trial_reengagement(garden, organizer)

    html = captured['html']
    assert captured['subject'].endswith('Wallstreet Garden is ready when you are')
    # Header corrected...
    assert LEGACY_GREEN not in html
    assert f'background-color: {BRAND_INK}' in html
    # ...CTA still lime, body greys are the brand's.
    assert f'background-color: {BRAND_LIME}' in html
    assert '#888' not in html
    # The price shown is whatever the platform actually charges.
    pricing = es._pro_pricing()
    assert es._usd(pricing['yearly_cents']) in html
