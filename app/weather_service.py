"""Weather service using OpenWeatherMap API.

Gracefully degrades to mock data when API key is not set (dev mode).
Env var: OPENWEATHER_API_KEY
"""
import os
import json
from urllib.request import urlopen, Request
from urllib.error import URLError

OPENWEATHER_KEY = os.environ.get('OPENWEATHER_API_KEY', '')
BASE_URL = 'https://api.openweathermap.org/data/2.5'


def _fetch_json(url):
    """Fetch JSON from URL with timeout."""
    try:
        req = Request(url, headers={'User-Agent': 'YardHarvest/1.0'})
        with urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode())
    except (URLError, Exception) as e:
        print(f"[Weather] API error: {e}")
        return None


def get_current_weather(lat, lon):
    """Get current weather conditions for a location.

    Returns dict with temp, humidity, conditions, wind, icon.
    Falls back to mock data when API key is not set.
    """
    if not OPENWEATHER_KEY:
        return _mock_weather()

    url = (f'{BASE_URL}/weather?lat={lat}&lon={lon}'
           f'&appid={OPENWEATHER_KEY}&units=imperial')
    data = _fetch_json(url)
    if not data:
        return _mock_weather()

    return {
        'temp_f': round(data['main']['temp'], 1),
        'feels_like_f': round(data['main']['feels_like'], 1),
        'humidity': data['main']['humidity'],
        'conditions': data['weather'][0]['description'].title() if data.get('weather') else 'Unknown',
        'icon': data['weather'][0]['icon'] if data.get('weather') else '01d',
        'wind_mph': round(data['wind']['speed'], 1) if data.get('wind') else 0,
        'source': 'openweathermap',
    }


def get_frost_alert(lat, lon):
    """Check if min temp < 35°F in next 48h.

    Returns dict with is_frost_risk, min_temp, when.
    """
    if not OPENWEATHER_KEY:
        return {'is_frost_risk': False, 'min_temp': 45, 'source': 'mock'}

    url = (f'{BASE_URL}/forecast?lat={lat}&lon={lon}'
           f'&appid={OPENWEATHER_KEY}&units=imperial&cnt=16')
    data = _fetch_json(url)
    if not data or 'list' not in data:
        return {'is_frost_risk': False, 'min_temp': 45, 'source': 'error'}

    min_temp = 100
    frost_time = None
    for entry in data['list']:
        temp = entry['main']['temp_min']
        if temp < min_temp:
            min_temp = temp
            frost_time = entry.get('dt_txt', '')

    return {
        'is_frost_risk': min_temp < 35,
        'min_temp': round(min_temp, 1),
        'when': frost_time,
        'source': 'openweathermap',
    }


def _mock_weather():
    """Return mock weather data for development."""
    return {
        'temp_f': 72.5,
        'feels_like_f': 70.0,
        'humidity': 55,
        'conditions': 'Partly Cloudy',
        'icon': '02d',
        'wind_mph': 8.2,
        'source': 'mock',
    }
