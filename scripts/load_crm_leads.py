"""Load the 50-state community-garden lead dataset into the CRM tables.

Reads data/leads_50_states.json (web-researched organizations) and inserts
each as a crm_company, skipping anything already present (case-insensitive
name match). Organizations with a public general email also get an
"Info — <Org>" crm_contact so campaigns can reach them. The research note is
saved as a note on the company.

Run from the repo root (uses DATABASE_URL / default local SQLite):
    python scripts/load_crm_leads.py [--dry-run]
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app, db  # noqa: E402

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    'data', 'leads_50_states.json')


def norm(name):
    return ''.join(ch for ch in (name or '').lower() if ch.isalnum())


def main(dry_run=False):
    with open(DATA, encoding='utf-8') as f:
        leads = json.load(f)

    app = create_app()
    with app.app_context():
        from app.crm.models import Activity, Company, Contact, Note

        existing = {norm(c.name) for c in Company.query.all()}
        created, skipped, contacts = 0, 0, 0
        by_state = Counter()

        for lead in leads:
            key = norm(lead['name'])
            if not key or key in existing:
                skipped += 1
                continue
            existing.add(key)

            company = Company(
                name=lead['name'].strip(),
                city=(lead.get('city') or '').strip() or None,
                state=(lead.get('state') or '').strip() or None,
                org_type=lead.get('org_type') if lead.get('org_type') in
                ('Independent', 'City-Sponsored') else None,
                website=(lead.get('website') or '').strip() or None,
                tags=(lead.get('tags') or '').strip() or None,
            )
            if not dry_run:
                db.session.add(company)
                db.session.flush()
                if lead.get('note'):
                    db.session.add(Note(
                        content=f"[Lead research] {lead['note']}",
                        company_id=company.id))
                db.session.add(Activity(
                    kind='created',
                    description=f'Lead imported: "{company.name}"',
                    company_id=company.id))
                email = (lead.get('email') or '').strip()
                if email and '@' in email:
                    db.session.add(Contact(
                        name=f"Info — {company.name}"[:120],
                        email=email, company_id=company.id))
                    contacts += 1
            created += 1
            by_state[company.state or '?'] += 1

        if not dry_run:
            db.session.commit()

        print(f"{'[dry-run] ' if dry_run else ''}created {created} companies, "
              f"{contacts} contacts, skipped {skipped} (already present)")
        print('new by state:', dict(sorted(by_state.items())))
        print('total companies now:', Company.query.count())
        states = {c.state for c in Company.query.all() if c.state}
        print(f'states covered: {len(states)}')


if __name__ == '__main__':
    main(dry_run='--dry-run' in sys.argv)
