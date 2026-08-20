"""Which cold leads to work first, decided in SQL rather than by a model.

Ranking the cold pool used to be a Sonnet call over the first 40 leads by id,
which had three problems: it never saw most of the pool, it cost money on
every cycle to answer a question with no judgement in it, and its prompt led
with independents while the GTM thesis says the payers are operators,
nonprofits and city programs.

The score below is a handful of facts we already store, weighted. It reads the
whole pool, costs nothing, and — because the org weight is a setting — the
thesis is a number James can change when the reply rates disagree with it.
"""
import re

from sqlalchemy import case, func

from app.crm.models import Company, Contact, Note, PAYER_ORG_TYPES

# Facts that make a lead worth a slot today. Deliberately small: each one is
# something we can point at, not a proxy for a feeling.
NAMED_CONTACT_POINTS = 1.0     # a person, not info@ — someone can decide
WEBSITE_POINTS = 1.0           # a real org with a public presence
MULTI_SITE_POINTS = 2.0        # runs more than one garden: seats and budget
TITLE_POINTS = 1.0             # we know their role, so the email can fit it

# Placeholder names our own scouting writes when only a shared inbox exists.
_GENERIC_NAME_RE = re.compile(r'^\s*(info|office|hello|contact|admin|team|'
                              r'garden|mail|enquiries|inquiries)\b', re.I)
_GENERIC_LOCAL_RE = re.compile(r'^(info|office|hello|contact|admin|team|mail|'
                               r'enquiries|inquiries|no-?reply|support)$', re.I)


def is_named_human(contact):
    """True when the contact is a person rather than a shared mailbox.

    Our own placeholder is "Info — <org>", and the address itself gives the
    rest away. Greeting a role account by name is the most embarrassing thing
    the agent can do, so this same question decides both the greeting and
    whether the lead is worth a send."""
    name = (contact.name or '').strip()
    local = (contact.email or '').split('@')[0]
    if not name or _GENERIC_NAME_RE.match(name) or '—' in name:
        return False
    if local and _GENERIC_LOCAL_RE.match(local):
        return False
    return ' ' in name          # a first and last name


def org_weight(org_type, operator_weight):
    """Multiplier for the organization's type.

    The default is 2.0 for the payer types, which is a thesis rather than a
    measurement: gardens run by volunteers have no budget line, and the money
    is with operators, nonprofits and city programs. It is a setting precisely
    so it can be lowered the moment reply rates say otherwise."""
    return float(operator_weight or 1.0) if org_type in PAYER_ORG_TYPES else 1.0


def score_expression(operator_weight):
    """The score as SQL, so the whole pool can be ordered by it in the query.

    Kept in one place with score_contact() below; the two must agree, and a
    test pins that they do.
    """
    named = case((Contact.name.ilike('% %'), NAMED_CONTACT_POINTS), else_=0.0)
    titled = case((func.coalesce(Contact.title, '') != '', TITLE_POINTS), else_=0.0)
    site = case((func.coalesce(Company.website, '') != '', WEBSITE_POINTS), else_=0.0)
    multi = case((func.coalesce(Company.sites_count, 0) > 1, MULTI_SITE_POINTS), else_=0.0)
    weight = case((Company.org_type.in_(PAYER_ORG_TYPES), float(operator_weight or 1.0)),
                  else_=1.0)
    return (named + titled + site + multi) * weight


def score_contact(contact, operator_weight):
    """The same score in Python, for explaining a single row.

    The SQL version orders the pool; this one produces the reason shown on the
    proposal, because "why is this lead first" is a question the operator will
    ask and a number alone does not answer."""
    co = contact.company
    points, why = 0.0, []
    if is_named_human(contact):
        points += NAMED_CONTACT_POINTS
        why.append('a named person, not a shared inbox')
    if (contact.title or '').strip():
        points += TITLE_POINTS
        why.append(f'{contact.title}')
    if co and (co.website or '').strip():
        points += WEBSITE_POINTS
        why.append('has a website')
    if co and (co.sites_count or 0) > 1:
        points += MULTI_SITE_POINTS
        why.append(f'runs {co.sites_count} sites')
    weight = org_weight(co.org_type if co else None, operator_weight)
    if weight != 1.0 and co:
        why.append(f'{co.org_type} — the type with a budget line')
    return points * weight, why


def rank(contacts, operator_weight, limit=None):
    """Best-first, with the reason attached. Ties break on id so a cycle that
    reruns picks the same leads rather than shuffling."""
    scored = [(score_contact(c, operator_weight), c) for c in contacts]
    scored.sort(key=lambda pair: (-pair[0][0], pair[1].id))
    out = [{'contact': c, 'score': round(pts, 2), 'why': why}
           for (pts, why), c in scored]
    return out[:limit] if limit else out


# ---------------------------------------------------------------------------
# One-time backfill: type the orgs we already hold
# ---------------------------------------------------------------------------
_OPERATOR_PATTERNS = (
    (re.compile(r'\b(\d+)\s+(?:community\s+)?(?:gardens|sites|plots?\s+sites|locations)\b', re.I), 'sites'),
    (re.compile(r'\bcoordinates?\s+(\d+)\b', re.I), 'sites'),
    (re.compile(r'\b(?:manages|operates|runs)\s+(\d+)\b', re.I), 'sites'),
)
_NONPROFIT_WORDS = re.compile(
    r'\b(nonprofit|non-profit|501\(c\)|land trust|food bank|coalition|'
    r'network|collective|foundation|alliance|conservancy)\b', re.I)
# Deliberately narrow. A bare "county" matched "Khmer Community of Seattle
# King County" — a community organization, not a county program — and a
# mis-typed payer is worse than an untyped one: it sends the wrong call to
# action and skews the enrichment order away from orgs that would answer.
_CITY_WORDS = re.compile(
    r'\b(parks (?:and recreation|recreation|department|dept|district)'
    r'|city of|municipality|municipal (?:government|parks|department)'
    r'|county (?:of|parks|extension|government|health|department)'
    r'|public works|recreation department)\b', re.I)


def backfill_org_types(dry_run=False, retype_flattened=False):
    """Type existing organizations from text we already have.

    Deterministic keyword matching over the org name, website and its notes —
    no model, no fabrication. By default it only fills gaps: an org already
    typed, or with a sites_count already set, is left alone, because a human
    or a scout may have decided that deliberately.

    ``retype_flattened`` also corrects rows currently stamped 'Independent'
    where the evidence says otherwise. Those were mostly written by the
    importer bug that mapped nonprofit → Independent, so they are a bug's
    output rather than anyone's decision — but keyword evidence is not proof,
    and this rewrites data somebody may have set by hand, so it stays opt-in
    and is worth reading under --dry-run first.

    Returns {'typed': n, 'sites': n, 'retyped': n, 'changes': [...]}.
    """
    from app import db

    changed = {'typed': 0, 'sites': 0, 'retyped': 0, 'changes': []}
    companies = Company.query.all()
    notes_by_company = {}
    for note in Note.query.filter(Note.company_id.isnot(None)).all():
        notes_by_company.setdefault(note.company_id, []).append(note.content or '')

    for co in companies:
        haystack = ' '.join(filter(None, [
            co.name or '', co.website or '', co.tags or '',
            ' '.join(notes_by_company.get(co.id, [])),
        ]))
        current = (co.org_type or '').strip()
        evidence = ('City-Sponsored' if _CITY_WORDS.search(haystack)
                    else 'Nonprofit/Operator' if _NONPROFIT_WORDS.search(haystack)
                    else None)
        if evidence and not current:
            co.org_type = evidence
            changed['typed'] += 1
            changed['changes'].append((co.name, '(untyped)', evidence))
        elif evidence and retype_flattened and current == 'Independent':
            co.org_type = evidence
            changed['retyped'] += 1
            changed['changes'].append((co.name, current, evidence))
        if co.sites_count is None:
            for pattern, _kind in _OPERATOR_PATTERNS:
                m = pattern.search(haystack)
                if m:
                    try:
                        count = int(m.group(1))
                    except (TypeError, ValueError):
                        continue
                    # A garden claiming 400 sites is a parse error, not an
                    # operator; a claim of 1 tells us nothing.
                    if 1 < count <= 200:
                        co.sites_count = count
                        changed['sites'] += 1
                        if not (co.org_type or '').strip():
                            co.org_type = 'Nonprofit/Operator'
                            changed['typed'] += 1
                            changed['changes'].append((co.name, '(untyped)',
                                                       'Nonprofit/Operator'))
                    break

    if dry_run:
        db.session.rollback()
    else:
        db.session.commit()
    return changed


def register_cli(crm_bp):
    """`flask crm backfill-org-types` — the one-time typing pass."""
    import click

    @crm_bp.cli.command('backfill-org-types')
    @click.option('--dry-run', is_flag=True,
                  help='Report what would change without writing anything.')
    @click.option('--retype-flattened', is_flag=True,
                  help="Also correct orgs stamped 'Independent' by the old "
                       'importer when the evidence says nonprofit or city. '
                       'Read it under --dry-run first.')
    @click.option('--show', default=25, show_default=True,
                  help='How many individual changes to print.')
    def backfill_command(dry_run, retype_flattened, show):
        """Type existing organizations from names, websites and notes."""
        result = backfill_org_types(dry_run=dry_run,
                                    retype_flattened=retype_flattened)
        verb = 'Would type' if dry_run else 'Typed'
        click.echo(f'{verb} {result["typed"]} untyped organization(s); '
                   f'set sites_count on {result["sites"]}; '
                   f'corrected {result["retyped"]} previously flattened.')
        for name, was, now in result['changes'][:show]:
            click.echo(f'    {name}: {was} -> {now}')
        extra = len(result['changes']) - show
        if extra > 0:
            click.echo(f'    ... and {extra} more')
        if not retype_flattened:
            click.echo('Rows already stamped Independent were left alone. '
                       'Add --retype-flattened to correct the importer bug too.')
        if dry_run:
            click.echo('Nothing was written. Re-run without --dry-run to apply.')
