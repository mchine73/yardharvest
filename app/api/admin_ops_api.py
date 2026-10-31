"""Admin operations: API usage reporting, and messaging garden managers.

Two features the console lacked:

* **API Usage** — what the platform spends on metered APIs (ZeptoMail, Twilio,
  Anthropic), how often those calls fail, and the run rate. See app.api_usage.

* **Message garden managers** — the console's "Communication" page only held
  settings; there was no way to actually write to the people who run gardens.
  This sends one message to a filtered audience by email and/or in-app
  notification, with a preview step that must agree with the send.

The preview/send handshake is deliberate. A send names the recipient count the
admin saw in the preview; if the audience has changed since (a garden joined,
a plan lapsed), the send is refused rather than reaching people nobody looked
at. It is the same two-step pattern the CRM's campaign send uses.
"""
import html
import json
import logging

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from app import db
from app.api.token_auth import get_current_user, token_or_session
from app.helpers import admin_required
from app.models import (CommunityGarden, GardenMembership, ManagerBroadcast,
                        User)

log = logging.getLogger(__name__)

admin_ops_api = Blueprint('admin_ops_api', __name__, url_prefix='/api/admin')

# Who counts as a "manager", widest last.
ROLE_SETS = {
    'owners': (),
    'owners_and_co': ('co_organizer',),
    'all_staff': ('co_organizer', 'treasurer', 'volunteer_lead'),
}
PLANS = ('active', 'trialing', 'none', 'expired')
CHANNELS = ('email', 'inapp')
MAX_SUBJECT, MAX_BODY = 200, 5000


# ---------------------------------------------------------------------------
# API usage
# ---------------------------------------------------------------------------

@admin_ops_api.route('/api-usage', methods=['GET'])
@token_or_session
@admin_required
def api_usage():
    from app import api_usage as usage
    try:
        days = int(request.args.get('days', 30))
    except (TypeError, ValueError):
        days = 30
    return jsonify(usage.report(days))


# ---------------------------------------------------------------------------
# Garden manager audience
# ---------------------------------------------------------------------------

def _clean_audience(raw):
    """The filters, validated. Unknown values are dropped rather than trusted."""
    raw = raw or {}
    roles = raw.get('roles') if raw.get('roles') in ROLE_SETS else 'owners_and_co'
    plans = [p for p in (raw.get('plans') or []) if p in PLANS]
    states = sorted({str(s).strip().upper()[:2] for s in (raw.get('states') or [])
                     if str(s).strip()})
    garden_ids = []
    for g in raw.get('garden_ids') or []:
        try:
            garden_ids.append(int(g))
        except (TypeError, ValueError):
            continue
    return {
        'roles': roles,
        'plans': plans,               # empty = every plan
        'states': states,             # empty = everywhere
        'garden_ids': sorted(set(garden_ids)),   # empty = every matching garden
        'active_only': raw.get('active_only', True) is not False,
    }


def resolve_audience(audience):
    """[{user, gardens:[names]}] — one entry per PERSON, not per garden.

    Someone who manages three gardens gets one message naming all three, not
    three copies. Deleted and deactivated accounts are never included: a
    deleted account's email has been scrubbed, and a deactivated one was
    turned off on purpose.
    """
    q = CommunityGarden.query
    if audience['active_only']:
        q = q.filter(CommunityGarden.is_active.is_(True))
    if audience['plans']:
        # 'none' also covers a NULL status, which is how older gardens read.
        conds = [CommunityGarden.subscription_status.in_(audience['plans'])]
        if 'none' in audience['plans']:
            conds.append(CommunityGarden.subscription_status.is_(None))
        q = q.filter(db.or_(*conds))
    if audience['states']:
        q = q.filter(func.upper(CommunityGarden.state).in_(audience['states']))
    if audience['garden_ids']:
        q = q.filter(CommunityGarden.id.in_(audience['garden_ids']))
    gardens = q.all()
    if not gardens:
        return []

    by_user = {}

    def add(user_id, garden):
        by_user.setdefault(user_id, []).append(garden.name)

    for g in gardens:
        if g.organizer_id:
            add(g.organizer_id, g)
    extra_roles = ROLE_SETS[audience['roles']]
    if extra_roles:
        ids = [g.id for g in gardens]
        name_of = {g.id: g for g in gardens}
        for m in (GardenMembership.query
                  .filter(GardenMembership.garden_id.in_(ids),
                          GardenMembership.role.in_(extra_roles)).all()):
            add(m.user_id, name_of[m.garden_id])

    users = (User.query.filter(User.id.in_(list(by_user)))
             .filter(User.deleted_at.is_(None))
             .filter(db.or_(User.is_active_user.is_(True),
                            User.is_active_user.is_(None))).all())
    out = [{'user': u, 'gardens': sorted(set(by_user[u.id]))} for u in users]
    out.sort(key=lambda r: (r['user'].display_name or r['user'].username or '').lower())
    return out


def _name(user):
    return (user.display_name or user.username or '').strip() or 'there'


@admin_ops_api.route('/manager-audience/options', methods=['GET'])
@token_or_session
@admin_required
def manager_audience_options():
    """What the filter UI offers: states that have gardens, counts per plan."""
    states = [s for (s,) in (db.session.query(func.upper(CommunityGarden.state))
                             .filter(CommunityGarden.state.isnot(None))
                             .distinct().all()) if s]
    plan_counts = dict(
        (status or 'none', n) for status, n in
        db.session.query(CommunityGarden.subscription_status,
                         func.count(CommunityGarden.id))
        .filter(CommunityGarden.is_active.is_(True))
        .group_by(CommunityGarden.subscription_status).all())
    gardens = [{'id': g.id, 'name': g.name, 'state': g.state,
                'plan': g.subscription_status or 'none'}
               for g in (CommunityGarden.query
                         .filter(CommunityGarden.is_active.is_(True))
                         .order_by(CommunityGarden.name).all())]
    return jsonify({'states': sorted(states), 'plan_counts': plan_counts,
                    'gardens': gardens})


@admin_ops_api.route('/manager-broadcast/preview', methods=['POST'])
@token_or_session
@admin_required
def manager_broadcast_preview():
    from app.api_usage import ZEPTOMAIL_USD_PER_RECIPIENT
    from app.email_service import is_email_suppressed

    data = request.get_json(silent=True) or {}
    audience = _clean_audience(data.get('audience'))
    people = resolve_audience(audience)
    suppressed = [p for p in people if is_email_suppressed(p['user'].email)]
    emailable = len(people) - len(suppressed)
    return jsonify({
        'audience': audience,
        'count': len(people),
        'emailable': emailable,
        'suppressed': len(suppressed),
        # The admin should see who this reaches before it reaches them.
        'recipients': [{
            'id': p['user'].id,
            'name': _name(p['user']),
            'email': p['user'].email,
            'gardens': p['gardens'],
            'suppressed': p in suppressed,
        } for p in people[:200]],
        'truncated': len(people) > 200,
        'est_email_cost_usd': round(emailable * ZEPTOMAIL_USD_PER_RECIPIENT, 4),
    })


def _email_html(user, gardens, subject, body):
    """The admin's words in the platform shell, greeting the reader by name.

    The body is escaped and its line breaks become paragraphs. The admin is
    writing plain text, and an angle bracket in it must arrive as an angle
    bracket, not as markup in two hundred inboxes.
    """
    paras = [p.strip() for p in body.replace('\r\n', '\n').split('\n\n') if p.strip()]
    body_html = ''.join(
        '<p>%s</p>' % html.escape(p).replace('\n', '<br>') for p in paras)
    managing = ''
    if gardens:
        managing = ('<p style="color:#6b7280;font-size:13px;margin-top:24px;">'
                    'You are receiving this because you manage %s on YardHarvest.</p>'
                    % html.escape(', '.join(gardens)))
    return ('<p>Hi %s,</p>%s%s' % (html.escape(_name(user)), body_html, managing))


@admin_ops_api.route('/manager-broadcast', methods=['POST'])
@token_or_session
@admin_required
def manager_broadcast_send():
    from app.api.notifications_api import notify
    from app.email_service import (_render, _subject, is_email_suppressed,
                                   send_email)

    data = request.get_json(silent=True) or {}
    subject = (data.get('subject') or '').strip()
    body = (data.get('body') or '').strip()
    channels = [c for c in (data.get('channels') or []) if c in CHANNELS]
    audience = _clean_audience(data.get('audience'))

    if not subject or not body:
        return jsonify({'error': 'A subject and a message are both required.'}), 400
    if len(subject) > MAX_SUBJECT:
        return jsonify({'error': 'Subject is over %d characters.' % MAX_SUBJECT}), 400
    if len(body) > MAX_BODY:
        return jsonify({'error': 'Message is over %d characters.' % MAX_BODY}), 400
    if not channels:
        return jsonify({'error': 'Choose at least one way to deliver it.'}), 400

    people = resolve_audience(audience)
    if not people:
        return jsonify({'error': 'That audience matches nobody.'}), 400

    # The handshake: the count the admin previewed must still be the count.
    try:
        expected = int(data.get('expected_count'))
    except (TypeError, ValueError):
        return jsonify({'error': 'Preview the audience before sending.'}), 400
    if expected != len(people):
        return jsonify({
            'error': ('The audience changed since you previewed it (%d then, %d now). '
                      'Preview again before sending.' % (expected, len(people))),
            'count': len(people),
        }), 409

    sender = get_current_user()
    rec = ManagerBroadcast(
        sender_id=getattr(sender, 'id', None), subject=subject, body=body,
        audience=json.dumps(audience), channels=','.join(channels),
        recipient_count=len(people))
    db.session.add(rec)
    db.session.flush()

    emailed = failed = suppressed = notified = 0
    for p in people:
        user = p['user']
        if 'inapp' in channels:
            try:
                # The notification body carries the whole message: there is no
                # separate in-app page to send them to.
                notify(user.id, 'platform_message', subject, body=body[:2000])
                notified += 1
            except Exception:
                log.exception('Manager broadcast: notification failed for %s', user.id)
        if 'email' in channels:
            # Unsubscribed, bounced and complained addresses are skipped. This is
            # one message to many people, which is exactly what that list is for.
            if is_email_suppressed(user.email):
                suppressed += 1
                continue
            ok = False
            try:
                ok = send_email(user.email, _subject(subject),
                                _render(_email_html(user, p['gardens'], subject, body)),
                                bulk=True)
            except Exception:
                log.exception('Manager broadcast: email failed for %s', user.id)
            if ok:
                emailed += 1
            else:
                failed += 1

    rec.emailed, rec.email_failed = emailed, failed
    rec.suppressed, rec.notified = suppressed, notified
    db.session.commit()
    log.info('Manager broadcast %s: %d people, %d emailed, %d failed, %d suppressed, '
             '%d notified', rec.id, len(people), emailed, failed, suppressed, notified)
    return jsonify({'broadcast': _broadcast_dict(rec)}), 201


def _broadcast_dict(b):
    try:
        audience = json.loads(b.audience or '{}')
    except ValueError:
        audience = {}
    return {
        'id': b.id,
        'created_at': b.created_at.isoformat() if b.created_at else None,
        'sender': (b.sender.display_name or b.sender.username) if b.sender else None,
        'subject': b.subject,
        'body': b.body,
        'audience': audience,
        'channels': (b.channels or '').split(',') if b.channels else [],
        'recipient_count': b.recipient_count or 0,
        'emailed': b.emailed or 0,
        'email_failed': b.email_failed or 0,
        'suppressed': b.suppressed or 0,
        'notified': b.notified or 0,
    }


@admin_ops_api.route('/manager-broadcasts', methods=['GET'])
@token_or_session
@admin_required
def manager_broadcasts():
    rows = ManagerBroadcast.query.order_by(ManagerBroadcast.created_at.desc()).limit(50).all()
    return jsonify({'broadcasts': [_broadcast_dict(b) for b in rows]})
