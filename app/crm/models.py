"""SQLAlchemy models for the CRM module.

All table names are prefixed ``crm_`` to keep the CRM domain cleanly separated
from the YardHarvest core schema in the shared database. The CRM ``User``
table is renamed to ``CrmUser`` so it doesn't collide with YH's ``User``.
"""
from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


STAGES = ['Lead', 'Qualification', 'Proposal', 'Closed Won', 'Closed Lost']

# Default win-probability per stage (used for weighted forecasting).
STAGE_PROBABILITY = {
    'Lead': 0.10,
    'Qualification': 0.30,
    'Proposal': 0.60,
    'Closed Won': 1.00,
    'Closed Lost': 0.00,
}

# Roles a contact can play on a deal (decision-maker mapping).
DEAL_ROLES = ['Champion', 'Economic Buyer', 'Approver',
              'Influencer', 'Procurement', 'Other']

# Mail-merge tokens available in email templates & campaigns.
# (token, human description) — rendering logic lives in app/crm/helpers.py.
MERGE_FIELDS = [
    ('{{first_name}}', "Contact's first name"),
    ('{{last_name}}', "Contact's last name"),
    ('{{contact_name}}', "Contact's full name"),
    ('{{email}}', "Contact email"),
    ('{{phone}}', "Contact phone"),
    ('{{company}}', "Organization name"),
    ('{{city}}', "Organization city"),
    ('{{state}}', "Organization state"),
    ('{{org_type}}', "Independent / City-Sponsored"),
    ('{{website}}', "Organization website"),
    ('{{deal_title}}', "Lead title (lead emails only)"),
    ('{{deal_amount}}', "Lead amount (lead emails only)"),
    ('{{deal_stage}}', "Lead stage (lead emails only)"),
    ('{{today}}', "Today's date"),
    ('{{sender_name}}', "Your name (the sender)"),
]


class CrmUser(UserMixin, db.Model):
    """Sales-team user account for the CRM. Distinct from YH's ``User``."""
    __tablename__ = 'crm_user'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='member')  # admin / member / readonly
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    @property
    def is_admin(self):
        return self.role == 'admin'

    @property
    def can_edit(self):
        return self.role in ('admin', 'member')


class Company(db.Model):
    __tablename__ = 'crm_company'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    city = db.Column(db.String(80))
    state = db.Column(db.String(20))
    org_type = db.Column(db.String(40))   # 'Independent' or 'City-Sponsored'
    website = db.Column(db.String(255))
    tags = db.Column(db.String(255))             # comma-separated
    fiscal_year_end = db.Column(db.String(40))   # e.g. "June 30"
    revenue = db.Column(db.Float)
    employees = db.Column(db.Integer)
    billing_cycle = db.Column(db.String(20))

    @property
    def tag_list(self):
        return [t.strip() for t in (self.tags or '').split(',') if t.strip()]

    contacts = db.relationship('Contact', backref='company', lazy=True)
    deals = db.relationship('Deal', backref='company', lazy=True)
    notes = db.relationship('Note', backref='company', lazy=True,
                            cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='company', lazy=True,
                            cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='company', lazy=True,
                                 cascade='all, delete-orphan')


class Contact(db.Model):
    __tablename__ = 'crm_contact'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(30))
    image = db.Column(db.String(255))
    email_opt_out = db.Column(db.Boolean, default=False)  # consent (CAN-SPAM)
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))

    notes = db.relationship('Note', backref='contact', lazy=True,
                            cascade='all, delete-orphan')
    deals = db.relationship('Deal', backref='contact', lazy=True)
    tasks = db.relationship('Task', backref='contact', lazy=True,
                            cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='contact', lazy=True,
                                 cascade='all, delete-orphan')
    deal_links = db.relationship('DealContact', backref='contact', lazy=True,
                                 cascade='all, delete-orphan')


class Deal(db.Model):
    __tablename__ = 'crm_deal'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float)
    stage = db.Column(db.String(50), default='Lead')
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    owner = db.relationship('CrmUser')

    # Close tracking / forecasting
    close_date = db.Column(db.Date)
    closed_reason = db.Column(db.String(200))
    last_activity_at = db.Column(db.DateTime)

    # Gov/nonprofit vertical fields
    funding_source = db.Column(db.String(120))   # e.g. grant name / dept budget
    grant_status = db.Column(db.String(40))      # None/Applied/Awarded/Denied
    budget_decision_date = db.Column(db.Date)    # expected fiscal decision
    rfp_due_date = db.Column(db.Date)            # procurement RFP deadline

    notes = db.relationship('Note', backref='deal', lazy=True,
                            cascade='all, delete-orphan')
    tasks = db.relationship('Task', backref='deal', lazy=True,
                            cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='deal', lazy=True,
                                 cascade='all, delete-orphan')
    contact_links = db.relationship('DealContact', backref='deal', lazy=True,
                                    cascade='all, delete-orphan')

    @property
    def probability(self):
        return STAGE_PROBABILITY.get(self.stage, 0.0)

    @property
    def weighted_amount(self):
        return (self.amount or 0) * self.probability

    @property
    def is_open(self):
        return self.stage not in ('Closed Won', 'Closed Lost')

    @property
    def days_since_activity(self):
        ref = self.last_activity_at or self.created_at
        if not ref:
            return None
        return (datetime.utcnow() - ref).days

    @property
    def is_stale(self):
        d = self.days_since_activity
        return self.is_open and d is not None and d >= 14


class DealContact(db.Model):
    """Associates additional contacts with a deal, each with a role."""
    __tablename__ = 'crm_deal_contact'

    id = db.Column(db.Integer, primary_key=True)
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), nullable=False)
    role = db.Column(db.String(40), default='Influencer')


class Note(db.Model):
    __tablename__ = 'crm_note'

    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Task(db.Model):
    __tablename__ = 'crm_task'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date)
    done = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='Medium')  # Low/Medium/High
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))


class EmailTemplate(db.Model):
    __tablename__ = 'crm_email_template'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Campaign(db.Model):
    __tablename__ = 'crm_campaign'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft / sent
    audience_desc = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    sent_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('crm_user.id'))

    recipients = db.relationship('CampaignRecipient', backref='campaign',
                                 lazy=True, cascade='all, delete-orphan')

    def count(self, status):
        return sum(1 for r in self.recipients if r.status == status)


class CampaignRecipient(db.Model):
    __tablename__ = 'crm_campaign_recipient'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('crm_campaign.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    # sent / logged / opted_out / no_email / failed
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    contact = db.relationship('Contact')


class Activity(db.Model):
    """Auto-recorded audit/timeline entries."""
    __tablename__ = 'crm_activity'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40))        # created / updated / stage_change / note / task / email
    description = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))

    actor = db.relationship('CrmUser')
