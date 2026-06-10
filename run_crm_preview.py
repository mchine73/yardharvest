"""Dev-only launcher: run the app against a throwaway demo DB for CRM preview.

Seeds a CRM admin (demo/demo12345) and the 50-state lead dataset so the new
CRM design can be eyeballed without touching the real dev database.

    python run_crm_preview.py   # serves on http://127.0.0.1:5059
"""
import json
import os

os.environ.setdefault('SECRET_KEY', 'preview-secret')
os.environ.pop('DATABASE_URL', None)

from config import Config  # noqa: E402

BASE = os.path.dirname(os.path.abspath(__file__))
DEMO_DB = os.path.join(BASE, 'instance', 'crm_preview.db').replace('\\', '/')
Config.SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DEMO_DB

from app import create_app, db  # noqa: E402

app = create_app()

with app.app_context():
    from app.crm.models import Company, Contact, CrmUser, Note, Segment

    if not CrmUser.query.first():
        u = CrmUser(username='demo', role='admin')
        u.set_password('demo12345')
        db.session.add(u)

    if not Company.query.first():
        with open(os.path.join(BASE, 'data', 'leads_50_states.json'),
                  encoding='utf-8') as f:
            leads = json.load(f)
        for lead in leads:
            company = Company(
                name=lead['name'], city=lead.get('city'),
                state=lead.get('state'), org_type=lead.get('org_type'),
                website=lead.get('website'), tags=lead.get('tags'))
            db.session.add(company)
            db.session.flush()
            if lead.get('note'):
                db.session.add(Note(content=f"[Lead research] {lead['note']}",
                                    company_id=company.id))
            if lead.get('email'):
                db.session.add(Contact(name=f"Info — {lead['name']}"[:120],
                                       email=lead['email'],
                                       company_id=company.id))
        db.session.add(Segment(name='Nebraska gardens', state='NE',
                               description='All NE organizations'))
        db.session.add(Segment(name='City programs',
                               org_type='City-Sponsored',
                               description='Municipal parks & rec audiences'))
    db.session.commit()
    print('demo DB ready:', DEMO_DB)

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5059)
