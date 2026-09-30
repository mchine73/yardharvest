"""Erasing an account.

Forty-six tables carry a foreign key to ``user`` and almost every one of them
is NOT NULL, so ``db.session.delete(user)`` is not an option: it either fails
on a constraint or cascades through other people's context - the dues ledger a
treasurer has to reconcile, the comment thread a garden was having, the plot
history that explains who had bed 12 last season.

So the row survives as a tombstone with every personal field scrubbed, and
the work is deciding, per table, which of three things each row is:

  purge      Theirs alone and of no interest to anyone else - a cart, a
             notification, a like, a waitlist place. Erasure means erasure.
  release    Theirs to hold, someone else's to use next. A plot assignment
             is the clear case: leaving it assigned to a deleted account
             means the bed sits empty and the waitlist never moves.
  retain     Either a financial record we are required to keep (Art. 17(3)(b)
             - tax and accounting do not bend to an erasure request), or
             something that is also somebody else's: a message has two
             parties, a comment thread is a conversation. Those keep their
             content and lose their attribution, which now resolves to the
             scrubbed tombstone and reads as "Deleted user".

This is erasure as the GDPR actually defines it, not as the word sounds:
Art. 17(3) is explicit that the right is not absolute.

One thing is a hard blocker rather than a judgement call. ``organizer_id`` on
community_garden is NOT NULL, so a garden owner cannot be erased without
orphaning the garden and everyone in it. They are told to transfer it first.
"""
import logging
import secrets
from datetime import datetime, timezone

from app import db

log = logging.getLogger(__name__)

#: What a scrubbed account looks like to anyone who still sees a reference.
TOMBSTONE_NAME = 'Deleted user'


def deletion_blockers(user):
    """Reasons this account cannot be erased yet, in words the user can act on.

    Empty list means go ahead. Each entry says what is in the way AND what to
    do about it - a refusal that does not tell you how to proceed is just a
    dead end, and this is the one screen where a dead end reads as the product
    refusing to let you leave.
    """
    from app.models import CommunityGarden

    blockers = []

    gardens = CommunityGarden.query.filter_by(organizer_id=user.id).all()
    if gardens:
        names = ', '.join(g.name for g in gardens[:3])
        more = '' if len(gardens) <= 3 else f' and {len(gardens) - 3} more'
        blockers.append(
            f'You organize {names}{more}. A garden cannot be left without an '
            f'organizer, so transfer it to another member or delete the garden '
            f'first, then come back.')

    # A connected payout account can hold money that has not landed yet.
    # Scrubbing the link would leave funds attached to an account nobody can
    # reach, which is a worse outcome for them than a short wait.
    if user.stripe_connect_account_id and user.stripe_payouts_enabled:
        blockers.append(
            'Your Stripe payout account is still connected. Please make sure '
            'any remaining balance has paid out, then disconnect it before '
            'deleting your account.')

    return blockers


def _purge(user_id, summary):
    """Rows that are the account's alone. Nobody else loses context."""
    from app.models import (AnalyticsEvent, CartItem, EventRSVP, GardenCommentLike,
                            GardenMembership, GardenPhotoLike, GardenWaitlist,
                            GroupMembership, HarvestInterest, Notification,
                            PhotoLike, ShiftSignup)
    for model, field in (
        (CartItem, 'buyer_id'),
        (Notification, 'user_id'),
        (GardenWaitlist, 'user_id'),
        (HarvestInterest, 'user_id'),
        (PhotoLike, 'user_id'),
        (GardenPhotoLike, 'user_id'),
        (GardenCommentLike, 'user_id'),
        (EventRSVP, 'user_id'),
        (ShiftSignup, 'user_id'),
        (GardenMembership, 'user_id'),
        (GroupMembership, 'user_id'),
        (AnalyticsEvent, 'user_id'),
    ):
        try:
            n = model.query.filter(getattr(model, field) == user_id).delete(
                synchronize_session=False)
            if n:
                summary[model.__tablename__] = n
        except Exception:
            # One missing table must not abort an erasure half-done. Log it
            # loudly - an incomplete erasure is the thing we most need to know
            # about - and carry on scrubbing the rest.
            log.exception('Could not purge %s for user %s', model.__name__, user_id)


def _release(user_id, summary):
    """Things they were holding that someone else should now be able to use."""
    from app.models import GardenPlot, Listing, SharedResource, SubscriptionPlan

    # A plot still assigned to a deleted account is a bed nobody can claim and
    # a waitlist that never moves.
    for field in ('assigned_to_id', 'reserved_by_id'):
        n = GardenPlot.query.filter(getattr(GardenPlot, field) == user_id).update(
            {field: None, 'status': 'available'}, synchronize_session=False)
        if n:
            summary[f'plots_{field}'] = n

    n = SharedResource.query.filter_by(checked_out_to_id=user_id).update(
        {'checked_out_to_id': None}, synchronize_session=False)
    if n:
        summary['resources_returned'] = n

    # Nothing of theirs should stay purchasable.
    for model in (Listing, SubscriptionPlan):
        try:
            n = model.query.filter_by(seller_id=user_id).update(
                {'is_active': False}, synchronize_session=False)
            if n:
                summary[f'{model.__tablename__}_deactivated'] = n
        except Exception:
            log.exception('Could not deactivate %s for user %s', model.__name__, user_id)


def _scrub(user):
    """Empty the account of everything that identifies a person."""
    uid = user.id
    user.email = f'deleted-{uid}@deleted.invalid'    # unique, unroutable
    user.username = f'deleted_user_{uid}'
    user.display_name = TOMBSTONE_NAME
    user.public_id = secrets.token_hex(16)

    for field in ('bio', 'gardening_story', 'address', 'city', 'state', 'zip_code',
                  'profile_image', 'gallery_image_1', 'gallery_image_2',
                  'gallery_image_3', 'phone_number', 'device_token',
                  'device_platform', 'stripe_customer_id',
                  'stripe_connect_account_id', 'stripe_requirements_due',
                  'stripe_disabled_reason'):
        setattr(user, field, None)
    for field in ('latitude', 'longitude', 'years_gardening'):
        setattr(user, field, None)

    # Silence every channel. A deleted account that still receives the garden
    # newsletter is the most visible way to get this wrong.
    user.sms_opt_in = False
    for field in ('email_order_updates', 'email_messages', 'email_harvest_alerts',
                  'email_garden_announcements'):
        setattr(user, field, False)
    user.stripe_onboarding_complete = False
    user.stripe_charges_enabled = False
    user.stripe_payouts_enabled = False

    # No one signs in again: unusable password, no active flag, and a bumped
    # token_version so any JWT already issued stops working immediately.
    user.set_password(secrets.token_urlsafe(32))
    user.is_active_user = False
    user.is_admin = False
    user.token_version = (user.token_version or 0) + 1
    user.deleted_at = datetime.now(timezone.utc)


def delete_account(user):
    """Erase ``user``. Returns a summary of what was removed or released.

    Raises ValueError if something blocks it, so a caller cannot half-do this
    by forgetting to check first.
    """
    blockers = deletion_blockers(user)
    if blockers:
        raise ValueError(blockers[0])

    uid = user.id
    # Captured before the scrub, for the one message that has to go out after
    # it. An erasure nobody is told about is indistinguishable from an
    # account takeover, and this is the last moment the address exists.
    address = user.email
    name = user.display_name or user.username
    language = getattr(user, 'language', None)

    summary = {}
    try:
        _purge(uid, summary)
        _release(uid, summary)
        _scrub(user)
        db.session.commit()
    except Exception:
        db.session.rollback()
        log.exception('Account erasure failed for user %s', uid)
        raise

    # Deliberately no email address and no name in this line: the whole point
    # of the operation is that those are gone, and a log is not an exception
    # to that.
    log.info('Account %s erased. %s', uid, summary or 'nothing to purge')
    _send_confirmation(address, name, language)
    return summary


def _send_confirmation(address, name, language):
    """Tell the person it happened. Best effort, and never fatal.

    This is the only message that may go to an address we have just erased,
    and it earns that: it is the completion of their own request, and if the
    request was not theirs it is the only thing that will tell them. Sent
    after the commit, so a mail failure cannot leave an account half-deleted.
    """
    if not address:
        return
    try:
        from app import i18n
        from app.email_service import send_email

        with i18n.force_locale(language):
            send_email(
                address,
                'Your YardHarvest account has been deleted',
                f'<p>Hi {name},</p>'
                '<p>Your YardHarvest account has been deleted, along with your '
                'profile, contact details and any plots or signups you held.</p>'
                '<p>Payment and dues records are kept, because we are required '
                'to keep them for tax and accounting. Anything you posted to a '
                'garden stays, but is no longer shown under your name.</p>'
                '<p><strong>If you did not ask for this, reply to this email '
                'straight away.</strong></p>')
    except Exception:
        log.exception('Could not send the deletion confirmation')
