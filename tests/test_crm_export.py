"""CRM system-of-record export: zip of CSVs, secrets excluded by design."""
import io
import zipfile

from app import db as _db


def _seed(app):
    from app.crm.models import Company, Contact, CrmFacebookAccount
    with app.app_context():
        co = Company(name='Export Garden', city='Omaha', state='NE',
                     org_type='Independent')
        _db.session.add(co)
        _db.session.flush()
        _db.session.add(Contact(name='Exp Ort', email='exp@example.com',
                                company_id=co.id))
        # A connected Facebook account with a live token — must NEVER export.
        _db.session.add(CrmFacebookAccount(page_id='pg1', page_name='Page',
                                           page_access_token='SECRET-PAGE-TOKEN',
                                           user_access_token='SECRET-USER-TOKEN'))
        _db.session.commit()


def test_export_zip_contains_records_and_manifest(app):
    _seed(app)
    from app.crm.export import build_export_zip
    with app.app_context():
        data, manifest = build_export_zip()
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = set(zf.namelist())
    assert 'crm_company.csv' in names and 'crm_contact.csv' in names
    assert 'MANIFEST.txt' in names
    companies = zf.read('crm_company.csv').decode()
    assert 'Export Garden' in companies
    assert manifest['tables']['crm_company'] >= 1


def test_export_never_contains_secrets(app):
    _seed(app)
    from app.crm.export import build_export_zip
    from app.crm.export import EXPORT_MODELS
    from app.crm.models import CrmFacebookAccount, CrmUser
    # The token/user tables are not in the export set at all.
    assert CrmFacebookAccount not in EXPORT_MODELS
    assert CrmUser not in EXPORT_MODELS
    with app.app_context():
        data, _ = build_export_zip()
    zf = zipfile.ZipFile(io.BytesIO(data))
    blob = b'\n'.join(zf.read(n) for n in zf.namelist())
    assert b'SECRET-PAGE-TOKEN' not in blob
    assert b'SECRET-USER-TOKEN' not in blob


def test_export_cli_reports_rows(app):
    _seed(app)
    runner = app.test_cli_runner()
    result = runner.invoke(args=['crm-export'])
    assert result.exit_code == 0
    assert 'Export built:' in result.output
    # No CRM_EXPORT_EMAIL configured in tests -> not emailed.
    assert 'NOT emailed' in result.output
