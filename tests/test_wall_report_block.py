"""Member reporting and blocking on the community wall.

App Store guideline 1.2 requires an app carrying user-generated content to let
a member report objectionable content and block an abusive member, and requires
that reported content reach a human. These cover the three properties the
review depends on:

- reporting a post puts it in the organizer's queue and is idempotent;
- a block hides that member's posts from the blocker and from nobody else;
- actioning a reported post clears the report, so the queue can be emptied.
"""
from app import db as _db
from tests.conftest import login_via_api


def _make_garden(app, owner_id, slug='report-garden'):
    from app.models import CommunityGarden
    with app.app_context():
        g = CommunityGarden(name='Report Garden', slug=slug,
                            organizer_id=owner_id, is_active=True,
                            subscription_status='active')
        _db.session.add(g)
        _db.session.commit()
        return g.id, g.public_id


def _post_as(client, gpub, body):
    r = client.post(f'/api/gardens/{gpub}/comments', json={'body': body})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]
    return r.get_json()['id']


def test_report_flags_post_into_the_organizer_queue(client, make_user, app):
    organizer = make_user(username='rg_org')
    author = make_user(username='rg_author')
    reporter = make_user(username='rg_reporter')
    gid, gpub = _make_garden(app, organizer.id)

    login_via_api(client, 'rg_author@example.com', 'Password1')
    cid = _post_as(client, gpub, 'Buy cheap watches at my website')

    login_via_api(client, 'rg_reporter@example.com', 'Password1')
    r = client.post(f'/api/gardens/{gpub}/comments/{cid}/report',
                    json={'reason': 'spam', 'note': 'an advert'})
    assert r.status_code == 200, r.get_data(as_text=True)[:300]
    assert r.get_json()['already_reported'] is False

    # Reporting again is a success no-op rather than a duplicate row.
    again = client.post(f'/api/gardens/{gpub}/comments/{cid}/report',
                        json={'reason': 'spam'})
    assert again.status_code == 200
    assert again.get_json()['already_reported'] is True

    # The organizer sees it, with the count and the reporter's reason.
    login_via_api(client, 'rg_org@example.com', 'Password1')
    q = client.get(f'/api/garden-admin/{gpub}/comments?status=reported')
    assert q.status_code == 200, q.get_data(as_text=True)[:300]
    payload = q.get_json()
    assert payload['reported_count'] == 1
    row = next(c for c in payload['comments'] if c['id'] == cid)
    assert row['report_count'] == 1
    assert row['status'] == 'flagged'
    assert 'Spam' in (row['moderation_reason'] or '')


def test_cannot_report_your_own_post(client, make_user, app):
    organizer = make_user(username='rg_own')
    gid, gpub = _make_garden(app, organizer.id, slug='report-own')
    login_via_api(client, 'rg_own@example.com', 'Password1')
    cid = _post_as(client, gpub, 'My own perfectly fine post')

    r = client.post(f'/api/gardens/{gpub}/comments/{cid}/report',
                    json={'reason': 'spam'})
    assert r.status_code == 400


def test_actioning_a_reported_post_clears_the_report(client, make_user, app):
    organizer = make_user(username='rg_clear_org')
    reporter = make_user(username='rg_clear_rep')
    gid, gpub = _make_garden(app, organizer.id, slug='report-clear')

    login_via_api(client, 'rg_clear_org@example.com', 'Password1')
    cid = _post_as(client, gpub, 'A post someone will object to')

    login_via_api(client, 'rg_clear_rep@example.com', 'Password1')
    client.post(f'/api/gardens/{gpub}/comments/{cid}/report',
                json={'reason': 'other'})

    login_via_api(client, 'rg_clear_org@example.com', 'Password1')
    assert client.post(
        f'/api/garden-admin/{gpub}/comments/{cid}/approve').status_code == 200

    q = client.get(f'/api/garden-admin/{gpub}/comments?status=reported')
    assert q.get_json()['reported_count'] == 0


def test_block_hides_posts_from_the_blocker_only(client, make_user, app):
    organizer = make_user(username='bk_org')
    noisy = make_user(username='bk_noisy')
    blocker = make_user(username='bk_blocker')
    gid, gpub = _make_garden(app, organizer.id, slug='block-garden')

    login_via_api(client, 'bk_noisy@example.com', 'Password1')
    _post_as(client, gpub, 'A post from the member who gets blocked')
    login_via_api(client, 'bk_org@example.com', 'Password1')
    _post_as(client, gpub, 'A post from someone else entirely')

    login_via_api(client, 'bk_blocker@example.com', 'Password1')
    assert len(client.get(f'/api/gardens/{gpub}/comments').get_json()) == 2

    r = client.post('/api/profile/blocks', json={'user_id': noisy.id})
    assert r.status_code == 201, r.get_data(as_text=True)[:300]

    bodies = [c['body'] for c in
              client.get(f'/api/gardens/{gpub}/comments').get_json()]
    assert len(bodies) == 1
    assert 'gets blocked' not in bodies[0]

    listed = client.get('/api/profile/blocks').get_json()
    assert [b['user_id'] for b in listed] == [noisy.id]

    # Everyone else's wall is untouched by one person's block.
    login_via_api(client, 'bk_org@example.com', 'Password1')
    assert len(client.get(f'/api/gardens/{gpub}/comments').get_json()) == 2

    # And the block is reversible.
    login_via_api(client, 'bk_blocker@example.com', 'Password1')
    assert client.delete(f'/api/profile/blocks/{noisy.id}').status_code == 200
    assert len(client.get(f'/api/gardens/{gpub}/comments').get_json()) == 2


def test_cannot_block_yourself(client, make_user, app):
    me = make_user(username='bk_self')
    login_via_api(client, 'bk_self@example.com', 'Password1')
    r = client.post('/api/profile/blocks', json={'user_id': me.id})
    assert r.status_code == 400


def test_report_reasons_are_served(client):
    r = client.get('/api/gardens/comment-report-reasons')
    assert r.status_code == 200
    ids = {row['id'] for row in r.get_json()}
    assert {'harassment', 'hate', 'spam', 'other'} <= ids
