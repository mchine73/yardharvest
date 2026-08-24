"""Who can do what inside one garden.

Until now every garden-admin check in the codebase was the same line —
``garden.organizer_id == me or is_admin`` — while the UI told organizers that
appointing a co-organizer or a treasurer would hand over real abilities. It
handed over a label. An organizer who stepped back had given away nothing, and
found out only when something needed doing.

This module is the single place that answers the question. Roles map to
capabilities; endpoints ask for a capability, never for a role. Adding a role
or moving one capability is then a one-line change here rather than a sweep
through eighty endpoints, and the answer cannot drift between them.

Three properties this has to keep, because they are the difference between
delegation and losing your garden:

* **Ownership is not delegable.** ``organizer`` comes from
  ``CommunityGarden.organizer_id`` alone, never from a membership row. A
  membership labelled 'organizer' grants nothing on its own — otherwise
  anyone who could edit roles could promote themselves.
* **Money's destination stays with the owner.** Connect onboarding and the
  Garden Pro subscription are ``BILLING``, which only the organizer holds. A
  co-organizer can collect and spend, but cannot change whose bank account the
  garden's money lands in.
* **Fail closed.** An unknown role, a missing membership, or a capability
  nobody has been granted all resolve to "no".
"""

# ---- Roles -----------------------------------------------------------------

ORGANIZER = 'organizer'
CO_ORGANIZER = 'co_organizer'
TREASURER = 'treasurer'
VOLUNTEER_LEAD = 'volunteer_lead'
MEMBER = 'member'

#: Assignable through the members tab. `organizer` is deliberately absent —
#: it follows ownership, and ownership moves via the site-admin transfer.
ASSIGNABLE_ROLES = (CO_ORGANIZER, TREASURER, VOLUNTEER_LEAD, MEMBER)

ALL_ROLES = (ORGANIZER,) + ASSIGNABLE_ROLES


# ---- Capabilities ----------------------------------------------------------

#: Open the admin portal and see the overview. Everyone with any role above
#: plain member needs this or they cannot reach their own tabs.
VIEW = 'view'
#: Plots, layout, garden settings, weather.
GARDEN = 'garden'
#: The roster, waitlist, plot reservations, removing members.
PEOPLE = 'people'
#: Announcements, the community wall, photos, messages, announcement emails.
CONTENT = 'content'
EVENTS = 'events'
SHIFTS = 'shifts'
RESOURCES = 'resources'
#: Dues, expenses, the finance tab, and taking payment in person.
MONEY = 'money'
#: Funder and volunteer reports.
REPORTS = 'reports'
#: Changing what role someone holds. Organizer only — whoever holds this can
#: hand out every other capability.
ROLES = 'roles'
#: Garden Pro subscription and Stripe Connect payout setup. Organizer only:
#: this decides where the garden's money goes and whose card is charged.
BILLING = 'billing'

ALL_CAPABILITIES = (VIEW, GARDEN, PEOPLE, CONTENT, EVENTS, SHIFTS, RESOURCES,
                    MONEY, REPORTS, ROLES, BILLING)

ROLE_CAPABILITIES = {
    ORGANIZER: frozenset(ALL_CAPABILITIES),
    # Runs the garden day to day. Everything except handing out roles and
    # everything except redirecting the money.
    CO_ORGANIZER: frozenset({VIEW, GARDEN, PEOPLE, CONTENT, EVENTS, SHIFTS,
                             RESOURCES, MONEY, REPORTS}),
    # Does the books. Dues and expenses carry the names they need, so this
    # deliberately stops short of the full roster.
    TREASURER: frozenset({VIEW, MONEY, REPORTS}),
    VOLUNTEER_LEAD: frozenset({VIEW, EVENTS, SHIFTS}),
    MEMBER: frozenset(),
}

#: Plain-English descriptions, shown when an organizer changes someone's role.
#: These must describe what the capability map actually grants — the previous
#: copy promised abilities nothing enforced.
ROLE_DESCRIPTIONS = {
    ORGANIZER: 'Full control, including roles, billing and payout setup.',
    CO_ORGANIZER: 'Can run the garden: plots, members, events, shifts, '
                  'resources, dues and reports. Cannot change roles, billing '
                  'or where payouts go.',
    TREASURER: 'Can manage dues, expenses and reports. No access to plots, '
               'members or settings.',
    VOLUNTEER_LEAD: 'Can manage events and volunteer shifts. No access to '
                    'money or members.',
    MEMBER: 'No administrative access.',
}


# ---- Resolution ------------------------------------------------------------

def garden_role(user, garden):
    """This user's role in this garden, or None.

    Ownership wins over any membership row: a membership labelled 'organizer'
    for someone who does not own the garden is not treated as ownership, which
    is what stops role editing from becoming a way to seize a garden.
    """
    if not user or not garden or not getattr(user, 'is_authenticated', True):
        return None
    uid = getattr(user, 'id', None)
    if uid is None:
        return None
    if garden.organizer_id == uid:
        return ORGANIZER

    from app.models import GardenMembership
    membership = GardenMembership.query.filter_by(
        garden_id=garden.id, user_id=uid).first()
    if not membership:
        return None
    role = (membership.role or MEMBER).strip()
    # A stale 'organizer' membership (left behind by an ownership transfer, or
    # set before this module existed) confers nothing beyond membership.
    if role == ORGANIZER:
        return CO_ORGANIZER
    return role if role in ALL_ROLES else MEMBER


def capabilities_for(user, garden):
    """Everything this user may do in this garden, as a set of capability names.

    Site admins get everything — that is the existing support arrangement, not
    a new grant.
    """
    if not user or not getattr(user, 'id', None):
        return frozenset()
    if getattr(user, 'is_admin', False):
        return frozenset(ALL_CAPABILITIES)
    role = garden_role(user, garden)
    return ROLE_CAPABILITIES.get(role, frozenset())


def can(user, garden, capability):
    """True if this user holds this capability in this garden."""
    if capability not in ALL_CAPABILITIES:
        # An endpoint asking for a capability that does not exist is a bug, and
        # the safe reading of a bug in an authorization check is "no".
        return False
    return capability in capabilities_for(user, garden)


def describe(role):
    return ROLE_DESCRIPTIONS.get(role, ROLE_DESCRIPTIONS[MEMBER])
