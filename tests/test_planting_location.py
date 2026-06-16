"""The planting calendar/guide adapt to the caller's location: frost dates are
estimated from latitude and every planting window is shifted accordingly."""
from app.api.planting_api import frost_profile, BASE_LAST_FROST_DOY


def test_frost_profile_shifts_with_latitude():
    base = frost_profile(None)
    north = frost_profile(47.6)   # ~Seattle
    south = frost_profile(30.0)   # ~Houston
    assert base['zone'] == '5b' and base['last_frost_doy'] == BASE_LAST_FROST_DOY
    assert not base['estimated']
    # Spring frost is later as you go north, earlier as you go south.
    assert north['last_frost_doy'] > BASE_LAST_FROST_DOY
    assert south['last_frost_doy'] < BASE_LAST_FROST_DOY
    # Fall frost is earlier up north (shorter season).
    assert north['first_frost_doy'] < base['first_frost_doy']
    assert north['estimated'] and south['estimated']


def test_calendar_default_is_omaha(client):
    data = client.get('/api/planting/calendar').get_json()
    assert set(data) >= {'location', 'categories'}
    assert data['location']['zone'] == '5b'
    assert data['location']['estimated'] is False
    assert data['location']['last_frost']['label'] == 'Apr 25'
    assert isinstance(data['categories'], list) and len(data['categories']) > 0


def test_calendar_uses_lat_param_and_shifts(client):
    base = client.get('/api/planting/calendar').get_json()
    north = client.get('/api/planting/calendar?lat=47&lon=-122').get_json()
    assert north['location']['estimated'] is True
    assert north['location']['last_frost_doy'] > base['location']['last_frost_doy']

    def first_start(payload, category):
        entry = next((c for c in payload['categories']
                      if c['category'] == category), None)
        if not entry or not entry['activities']:
            return None
        return min(a['start_doy'] for a in entry['activities'])

    cat = base['categories'][0]['category']
    b, n = first_start(base, cat), first_start(north, cat)
    if b is not None and n is not None:
        assert n >= b   # northern calendar starts no earlier than Omaha's


def test_guide_endpoint_shape_and_location(client):
    data = client.get('/api/planting/guide?lat=30&lon=-95').get_json()
    assert set(data) >= {'location', 'guides'}
    assert data['location']['estimated'] is True
    assert isinstance(data['guides'], list) and len(data['guides']) > 0
