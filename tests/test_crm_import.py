"""Verifies the enhanced /crm/import: companies + optional contacts/tags/notes,
and that re-importing the same file is a safe no-op (dedupe by name).

Imports the real researched prospect file (data/new_leads_research.csv) so the
file the user uploads is exercised end-to-end."""
import io
import os

import pytest

from app import db as _db


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV_PATH = os.path.join(PROJECT_ROOT, 'data', 'new_leads_research.csv')


@pytest.fixture()
def crm_admin(client):
    from app.crm.models import Company, Contact, CrmUser, Note
    with client.application.app_context():
        for model in (Note, Contact, Company, CrmUser):
            _db.session.query(model).delete()
        _db.session.commit()
    client.post('/crm/register',
                data={'username': 'importer', 'password': 'secret123',
                      'confirm': 'secret123'},
                follow_redirects=True)
    return client


def _upload(client, raw):
    return client.post(
        '/crm/import',
        data={'file': (io.BytesIO(raw.encode('utf-8')), 'leads.csv')},
        content_type='multipart/form-data',
        follow_redirects=True)


def test_research_csv_imports_orgs_contacts_tags_notes(crm_admin):
    from app.crm.models import Company, Contact, Note
    with open(CSV_PATH, encoding='utf-8') as f:
        raw = f.read()

    resp = _upload(crm_admin, raw)
    assert resp.status_code == 200

    with crm_admin.application.app_context():
        # All 41 researched orgs created.
        assert Company.query.count() == 41

        # Spot-check a flagship lead end-to-end.
        cc = Company.query.filter_by(name='Community Crops').first()
        assert cc is not None
        assert cc.city == 'Lincoln' and cc.state == 'NE'
        assert cc.org_type == 'Independent'
        assert 'Prospect' in (cc.tags or '')
        contact = Contact.query.filter_by(company_id=cc.id).first()
        assert contact is not None
        assert contact.email == 'info@communitycrops.org'
        assert contact.name == 'Ailyne Swartz Taylor'
        note = Note.query.filter_by(company_id=cc.id).first()
        assert note is not None and 'Source:' in note.content

        # Org with a published email but no named person -> "Info —" contact.
        bg = Company.query.filter_by(name='The Big Garden').first()
        bgc = Contact.query.filter_by(company_id=bg.id).first()
        assert bgc.email == 'contact@biggarden.org'
        assert bgc.name.startswith('Info —')

        # Org with only a person + phone (no email) still gets a contact.
        rw = Company.query.filter_by(
            name='Refugee Women Organization of Nebraska (New American Urban Farm)'
        ).first()
        rwc = Contact.query.filter_by(company_id=rw.id).first()
        assert rwc is not None and rwc.phone == '(402) 306-6651'

        # Exactly the rows with contact data produced contacts (24 of 41).
        assert Contact.query.count() == 24


def test_reimport_is_idempotent(crm_admin):
    from app.crm.models import Company, Contact
    with open(CSV_PATH, encoding='utf-8') as f:
        raw = f.read()

    _upload(crm_admin, raw)
    resp = _upload(crm_admin, raw)  # second time: all should be skipped
    assert b'skipped 41 duplicate' in resp.data

    with crm_admin.application.app_context():
        assert Company.query.count() == 41        # no duplicates
        assert Contact.query.count() == 24
