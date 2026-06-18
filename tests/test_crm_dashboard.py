"""Regression: /crm/dashboard must render when the pipeline has real tasks and
activities. The original dashboard test ran on an empty DB, so the
`{% if overdue_tasks %}` / `{% if recent_activity %}` blocks were skipped and
the _task_row.html / _activity_icon.html partials never rendered — hiding a
missing `today` template var that 500'd every dashboard load in production
(the global 500 handler then served the SPA, surfacing as "Page Not Found").
"""
import datetime as dt

from app import db as _db


def _register_first_admin(client, username='crmadmin', password='secret123'):
    return client.post('/crm/register',
                       data={'username': username, 'password': password,
                             'confirm': password},
                       follow_redirects=True)


def test_dashboard_renders_with_tasks_and_activity(client, app):
    from app.crm.models import (Activity, Company, Contact, CrmUser, Deal, Task)
    with app.app_context():
        for m in (Activity, Task, Deal, Contact, Company, CrmUser):
            _db.session.query(m).delete()
        _db.session.commit()

    _register_first_admin(client)

    with app.app_context():
        co = Company(name='Test Org', city='Omaha', state='NE', tags='Prospect')
        _db.session.add(co)
        _db.session.flush()
        ct = Contact(name='Jane Doe', email='jane@example.com', company_id=co.id)
        _db.session.add(ct)
        _db.session.flush()
        d = Deal(title='Test Org — Lead', stage='Lead',
                 company_id=co.id, contact_id=ct.id)  # amount intentionally None
        _db.session.add(d)
        _db.session.flush()
        today = dt.date.today()
        _db.session.add_all([
            Task(title='Overdue task', due_date=today - dt.timedelta(days=3),
                 done=False, priority='High', deal_id=d.id),
            Task(title='Upcoming task', due_date=today + dt.timedelta(days=2),
                 done=False, company_id=co.id),
            Activity(kind='created', description='Created deal', deal_id=d.id),
            Activity(kind='email', description='Sent email', contact_id=ct.id),
        ])
        _db.session.commit()

    resp = client.get('/crm/dashboard')
    assert resp.status_code == 200, resp.data[:3000].decode('utf-8', 'replace')
    assert b'Overdue task' in resp.data
    assert b'Upcoming task' in resp.data
