"""A request body over MAX_CONTENT_LENGTH must return a JSON 413 (not an HTML
error page the SPA can't parse) — the silent 'Upload failed' on large photos."""
import io


def test_oversized_upload_returns_json_413(app, client, make_user):
    with app.app_context():
        make_user(username='bigup', email='bigup@example.com', password='Password1')
    client.post('/api/auth/login', json={'email': 'bigup@example.com', 'password': 'Password1'})

    app.config['MAX_CONTENT_LENGTH'] = 1024  # 1 KB cap for the test
    big = b'x' * 50000  # 50 KB body exceeds the cap
    r = client.post(
        '/api/photos/upload',
        data={'photo': (io.BytesIO(big), 'big.jpg')},
        content_type='multipart/form-data',
    )
    assert r.status_code == 413, r.status_code
    assert 'too large' in r.get_json()['error'].lower()
