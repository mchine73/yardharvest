"""SQLAlchemy models for the CRM module.

All table names are prefixed ``crm_`` to keep the CRM domain cleanly separated
from the YardHarvest core schema in the shared database. The CRM ``User``
table is renamed to ``CrmUser`` so it doesn't collide with YH's ``User``.
"""
from datetime import datetime, timezone
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

# Pin the hashing method explicitly (matches the YH User model) so a library
# default change can't silently weaken stored hashes; scrypt is Werkzeug's
# current strong default.
PASSWORD_HASH_METHOD = 'scrypt'

from app import db


def _utcnow():
    """Naive UTC timestamp — replaces the deprecated ``datetime.utcnow``.

    Returns a naive datetime (tzinfo stripped) so it matches the existing
    naive values these columns already store; this keeps date arithmetic and
    comparisons consistent on both SQLite (dev/test) and Postgres (prod).
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


# BDR lead lifecycle — the status a rep (or the AI BDR agent) works a contact
# through, distinct from a Deal's pipeline stage (which begins after qualifying).
LEAD_STATUSES = ['New', 'Working', 'Engaged', 'Qualified',
                 'Customer', 'Disqualified', 'Nurture']
LEAD_OPEN_STATUSES = ['New', 'Working', 'Engaged']   # still actively prospected
LEAD_SOURCES = ['Import', 'Referral', 'Web', 'LinkedIn', 'Event', 'Scout', 'Other']

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
    created_at = db.Column(db.DateTime, default=_utcnow)

    def set_password(self, pw):
        self.password_hash = generate_password_hash(pw, method=PASSWORD_HASH_METHOD)

    def check_password(self, pw):
        return check_password_hash(self.password_hash, pw)

    def needs_password_rehash(self):
        """True when the stored hash isn't on the current pinned method, so the
        login flow can transparently upgrade it on next successful sign-in."""
        return not (self.password_hash or '').startswith(PASSWORD_HASH_METHOD + ':')

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

    # ---- email deliverability (ZeptoMail bounce webhook) ----
    # Soft bounces are transient: we count strikes and only suppress after a
    # threshold. Hard bounces / complaints suppress immediately (email_opt_out).
    # An open/click resets soft_bounce_count (the address recovered).
    soft_bounce_count = db.Column(db.Integer, default=0, nullable=False)
    last_bounce_at = db.Column(db.DateTime)
    last_bounce_type = db.Column(db.String(12))      # 'soft' | 'hard' | 'complaint'
    last_bounce_reason = db.Column(db.String(255))

    # ---- BDR lead lifecycle ----
    lead_status = db.Column(db.String(20), default='New', index=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    source = db.Column(db.String(60))
    last_contacted_at = db.Column(db.DateTime)
    next_action_at = db.Column(db.Date, index=True)   # when the next touch is due
    next_action_note = db.Column(db.String(200))
    # No-reply agent follow-ups sent so far. Drives escalating spacing
    # (4d → 8d) and the auto-Nurture cap; reset to 0 when the lead replies
    # or books a meeting (they're engaged — the clock starts over).
    followup_count = db.Column(db.Integer, default=0, nullable=False)

    owner = db.relationship('CrmUser')

    notes = db.relationship('Note', backref='contact', lazy=True,
                            cascade='all, delete-orphan')
    deals = db.relationship('Deal', backref='contact', lazy=True)
    tasks = db.relationship('Task', backref='contact', lazy=True,
                            cascade='all, delete-orphan')
    activities = db.relationship('Activity', backref='contact', lazy=True,
                                 cascade='all, delete-orphan')
    deal_links = db.relationship('DealContact', backref='contact', lazy=True,
                                 cascade='all, delete-orphan')

    @property
    def lead_score(self):
        """0–100 marketing-fit score from profile completeness + engagement."""
        score = 0
        if self.email and not self.email_opt_out:
            score += 15
        if self.phone:
            score += 10
        if self.company_id:
            score += 15
        score += min(len(self.notes or []) * 5, 15)
        score += min(len(self.activities or []) * 2, 10)
        open_deals = [d for d in (self.deals or []) if d.is_open]
        won_deals = [d for d in (self.deals or []) if d.stage == 'Closed Won']
        if open_deals:
            score += 25
        if won_deals:
            score += 10
        return min(score, 100)

    @property
    def lead_grade(self):
        s = self.lead_score
        return 'Hot' if s >= 60 else ('Warm' if s >= 30 else 'Cold')

    @property
    def is_open_lead(self):
        """Still being actively prospected (vs qualified/won/dead)."""
        return (self.lead_status or 'New') in LEAD_OPEN_STATUSES

    @property
    def is_due(self):
        """The agent/rep should touch this lead now: an open lead that's either
        never been contacted or whose next action date has arrived."""
        if not self.is_open_lead:
            return False
        if self.next_action_at is not None:
            return self.next_action_at <= _utcnow().date()
        # Never-worked leads are due only once someone OWNS them — a bulk
        # import (which assigns no owner) must not flood the queue with
        # hundreds of instantly-due unknown-provenance rows. Scout-approve,
        # log-touch, and the lead form all assign an owner/next action, which
        # is the explicit "promote to queue" step.
        return self.last_contacted_at is None and self.owner_id is not None

    @property
    def days_since_contact(self):
        if not self.last_contacted_at:
            return None
        return (_utcnow() - self.last_contacted_at).days


class Segment(db.Model):
    """A saved audience definition reusable across campaigns."""
    __tablename__ = 'crm_segment'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(255))
    state = db.Column(db.String(20))
    org_type = db.Column(db.String(40))
    tag = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=_utcnow)

    @property
    def filter_desc(self):
        bits = [b for b in (self.state, self.org_type,
                            f'tag:{self.tag}' if self.tag else '') if b]
        return ', '.join(bits) if bits else 'All contacts with email'


CONTENT_CHANNELS = ['Email', 'Social', 'Blog', 'Event', 'Ad']
CONTENT_STATUSES = ['Idea', 'Draft', 'Scheduled', 'Published']


class ContentItem(db.Model):
    """A planned piece of marketing content on the calendar."""
    __tablename__ = 'crm_content_item'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    channel = db.Column(db.String(20), default='Email')
    status = db.Column(db.String(20), default='Idea')
    scheduled_date = db.Column(db.Date)
    body = db.Column(db.Text)
    campaign_id = db.Column(db.Integer, db.ForeignKey('crm_campaign.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    created_at = db.Column(db.DateTime, default=_utcnow)

    campaign = db.relationship('Campaign')
    owner = db.relationship('CrmUser')


class Deal(db.Model):
    __tablename__ = 'crm_deal'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    amount = db.Column(db.Float)
    stage = db.Column(db.String(50), default='Lead')
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    owner_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    created_at = db.Column(db.DateTime, default=_utcnow)

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
        return (_utcnow() - ref).days

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
    created_at = db.Column(db.DateTime, default=_utcnow)


class Task(db.Model):
    __tablename__ = 'crm_task'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.Date)
    done = db.Column(db.Boolean, default=False)
    priority = db.Column(db.String(20), default='Medium')  # Low/Medium/High
    created_at = db.Column(db.DateTime, default=_utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))


class EmailTemplate(db.Model):
    __tablename__ = 'crm_email_template'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow)


class Campaign(db.Model):
    __tablename__ = 'crm_campaign'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    subject = db.Column(db.String(200))
    body = db.Column(db.Text)
    status = db.Column(db.String(20), default='draft')  # draft / sent
    audience_desc = db.Column(db.String(255))
    # Structured audience filters so a saved draft can be sent later (the
    # detail page reconstructs recipients from these). Mirror the campaign form.
    audience_state = db.Column(db.String(20))
    audience_org_type = db.Column(db.String(40))
    audience_tag = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=_utcnow)
    sent_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey('crm_user.id'))

    recipients = db.relationship('CampaignRecipient', backref='campaign',
                                 lazy=True, cascade='all, delete-orphan')

    def count(self, status):
        return sum(1 for r in self.recipients if r.status == status)

    @property
    def opened_count(self):
        return sum(1 for r in self.recipients if r.opened_at)

    @property
    def clicked_count(self):
        return sum(1 for r in self.recipients if r.clicked_at)

    @property
    def delivered_count(self):
        """Recipients whose send ZeptoMail actually accepted — the open-rate
        base. 'logged' (dev-mode/failed sends) and 'suppressed' (globally
        unsubscribed, silently dropped) are excluded: counting them deflated
        open/bounce rates with mail that never reached anyone."""
        return sum(1 for r in self.recipients if r.status == 'sent')


class CampaignRecipient(db.Model):
    __tablename__ = 'crm_campaign_recipient'

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(db.Integer, db.ForeignKey('crm_campaign.id'), nullable=False)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    # sent / logged / opted_out / no_email / failed / suppressed
    status = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=_utcnow)
    # First-party engagement tracking (pixel open + click redirect).
    token = db.Column(db.String(48), index=True)
    opened_at = db.Column(db.DateTime)
    clicked_at = db.Column(db.DateTime)

    contact = db.relationship('Contact')


class CrmEmailEvent(db.Model):
    """One row per email delivery event from the ZeptoMail webhook (hard/soft
    bounce, complaint, open, click). Contact columns keep only the LATEST
    bounce state — this table keeps the history the deliverability dashboard
    charts. ``contact_id`` is a soft link (no FK) so deleting a contact never
    erases the delivery trail for its address."""
    __tablename__ = 'crm_email_event'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), index=True)
    event_type = db.Column(db.String(12), index=True)  # hard|soft|complaint|open|click
    reason = db.Column(db.String(255))
    contact_id = db.Column(db.Integer, index=True)
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)


class Activity(db.Model):
    """Auto-recorded audit/timeline entries."""
    __tablename__ = 'crm_activity'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(40))        # created / updated / stage_change / note / task / email
    description = db.Column(db.String(400))
    created_at = db.Column(db.DateTime, default=_utcnow)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))

    actor = db.relationship('CrmUser')


# Types of next-step the AI BDR agent can propose, and the review states each
# proposal moves through. All types share this queue + approval flow (and, in
# autonomous mode, the same execute path — see app/crm/autonomy.py).
# 'executing' is the transient atomic-claim state between pending and a
# terminal outcome; a proposal never rests there.
AGENT_ACTION_TYPES = ['follow_up_email', 'scout', 'new_lead', 'campaign',
                      'facebook_post', 'reply_email']
AGENT_ACTION_STATUSES = ['pending', 'executing', 'executed', 'rejected', 'failed']


class CrmAgentAction(db.Model):
    """A next step the AI BDR agent proposes.

    The agent writes a proposal here with a plain-English rationale and an
    editable payload (e.g. a drafted email). Either a human reviews, optionally
    edits, then approves (which executes the action) or rejects it — or, for
    action types the operator has switched to autonomous (AgentSettings), the
    daily cycle claims and executes it itself and stamps ``auto_executed``.
    Both paths run app/crm/autonomy.execute_action.
    """
    __tablename__ = 'crm_agent_action'
    __table_args__ = (
        db.Index('ix_crm_agent_action_contact_status', 'contact_id', 'status'),
    )

    id = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(30), default='follow_up_email', nullable=False)
    status = db.Column(db.String(20), default='pending', nullable=False, index=True)

    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'))
    company_id = db.Column(db.Integer, db.ForeignKey('crm_company.id'))
    deal_id = db.Column(db.Integer, db.ForeignKey('crm_deal.id'))

    title = db.Column(db.String(200), nullable=False)    # human summary of the step
    rationale = db.Column(db.Text)                       # why the agent proposes it
    payload_json = db.Column(db.Text)                    # editable content (e.g. {subject, body})
    result = db.Column(db.String(400))                   # what happened on execute

    created_at = db.Column(db.DateTime, default=_utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    reviewed_at = db.Column(db.DateTime)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    # True when the autonomous cycle executed it (no human click).
    auto_executed = db.Column(db.Boolean, default=False, nullable=False,
                              server_default=db.false())

    contact = db.relationship('Contact', foreign_keys=[contact_id])
    company = db.relationship('Company', foreign_keys=[company_id])
    deal = db.relationship('Deal', foreign_keys=[deal_id])

    @property
    def payload(self):
        import json as _json
        try:
            return _json.loads(self.payload_json) if self.payload_json else {}
        except ValueError:
            return {}


class CrmAgentRun(db.Model):
    """A background drafting job kicked off from the BDR console. Tracks
    in-flight state in the DB (not just in-process) so the console can tell when
    drafting has finished regardless of which gunicorn worker serves the poll.
    A stale 'running' row (worker died) ages out of the 'in progress' check."""
    __tablename__ = 'crm_agent_run'

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(20))                       # follow_up/scout/campaign/facebook/scout_web/enrich
    status = db.Column(db.String(12), default='running', index=True)  # running/done/failed
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)
    finished_at = db.Column(db.DateTime)
    error = db.Column(db.Text)          # short failure detail when status='failed'
    # Usage/cost for spend visibility (estimated; see agent_service.estimate_cost)
    model = db.Column(db.String(40))
    input_tokens = db.Column(db.Integer, default=0)
    output_tokens = db.Column(db.Integer, default=0)
    web_searches = db.Column(db.Integer, default=0)
    cost_usd = db.Column(db.Float, default=0.0)


class AgentSettings(db.Model):
    """Singleton (id=1) operator policy for the autonomous BDR agent.

    Everything the daily cycle needs to decide WHETHER and HOW MUCH to act
    without a human: the master switch, per-action policy flags, the send
    cap/window, breaker thresholds, plus the durable state the cycle and the
    reply poller use to claim work idempotently across processes (cron tick,
    a "Run now" click, two gunicorn workers) — DB rows, never in-process
    counters. Same singleton pattern as app.models.BookingSettings.
    """
    __tablename__ = 'crm_agent_settings'

    id = db.Column(db.Integer, primary_key=True)
    # Master switch + breaker state. paused_reason set => the cycle refuses
    # to send until an operator clears it (Resume).
    autonomy_enabled = db.Column(db.Boolean, nullable=False, default=False,
                                 server_default=db.false())
    paused_reason = db.Column(db.String(300))
    paused_at = db.Column(db.DateTime)
    # Pace
    daily_send_cap = db.Column(db.Integer, nullable=False, default=15, server_default='15')
    weekdays_only = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    send_hour_local = db.Column(db.Integer, nullable=False, default=9, server_default='9')
    timezone = db.Column(db.String(64), nullable=False, default='America/Chicago',
                         server_default='America/Chicago')
    # Oversight
    digest_enabled = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    digest_email = db.Column(db.String(255))            # NULL -> CRM_FROM_EMAIL
    notify_on_interested = db.Column(db.Boolean, nullable=False, default=True,
                                     server_default=db.true())
    operator_user_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    # Per-action policy: which proposal types execute WITHOUT approval.
    auto_followups = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    auto_promote_cold = db.Column(db.Boolean, nullable=False, default=True, server_default=db.true())
    auto_new_leads = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    auto_enrich = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    auto_replies = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    auto_campaigns = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    auto_facebook = db.Column(db.Boolean, nullable=False, default=False, server_default=db.false())
    # Safety
    require_reply_capture = db.Column(db.Boolean, nullable=False, default=True,
                                      server_default=db.true())
    max_consecutive_send_failures = db.Column(db.Integer, nullable=False, default=3,
                                              server_default='3')
    max_hard_bounces_24h = db.Column(db.Integer, nullable=False, default=3, server_default='3')
    # Cycle state / claim
    last_cycle_date = db.Column(db.Date)                # LOCAL date of the last claimed cycle
    last_cycle_started_at = db.Column(db.DateTime)
    last_cycle_finished_at = db.Column(db.DateTime)
    cycle_lock_until = db.Column(db.DateTime)
    last_cycle_summary_json = db.Column(db.Text)
    # Reply-poll state / lease
    poll_lock_until = db.Column(db.DateTime)
    last_reply_poll_at = db.Column(db.DateTime)
    last_reply_poll_ok_at = db.Column(db.DateTime)
    imap_last_error = db.Column(db.String(400))
    imap_uidvalidity = db.Column(db.Integer)
    imap_last_uid = db.Column(db.Integer)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)

    @classmethod
    def get(cls):
        """Return the singleton row, creating it with defaults on first use."""
        row = db.session.get(cls, 1)
        if row is None:
            row = cls(id=1)
            db.session.add(row)
            db.session.commit()
        return row

    @property
    def last_cycle_summary(self):
        import json as _json
        try:
            return _json.loads(self.last_cycle_summary_json) if self.last_cycle_summary_json else None
        except ValueError:
            return None


class CrmInboundReply(db.Model):
    """An inbound email from a lead, captured by the IMAP reply poller.

    The autonomous loop's feedback signal: a stored reply is what stops the
    no-reply follow-up cadence and (for interested/other) spawns a queued
    ``reply_email`` proposal for the operator. ``message_id`` is unique so a
    re-poll can never process the same mail twice."""
    __tablename__ = 'crm_inbound_reply'

    id = db.Column(db.Integer, primary_key=True)
    contact_id = db.Column(db.Integer, db.ForeignKey('crm_contact.id'), index=True)
    from_email = db.Column(db.String(255), index=True)
    from_name = db.Column(db.String(160))
    subject = db.Column(db.String(300))
    snippet = db.Column(db.Text)                        # quoted history stripped, <= 2000 chars
    message_id = db.Column(db.String(255), unique=True)  # fallback 'uid:{validity}:{uid}'
    in_reply_to = db.Column(db.String(255))
    imap_uidvalidity = db.Column(db.Integer)
    imap_uid = db.Column(db.Integer)
    # interested | not_interested | unsubscribe | out_of_office | other | auto
    classification = db.Column(db.String(20), index=True)
    summary = db.Column(db.String(300))
    action_taken = db.Column(db.String(300))
    agent_action_id = db.Column(db.Integer, db.ForeignKey('crm_agent_action.id'))  # drafted reply
    received_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_utcnow, index=True)

    contact = db.relationship('Contact', foreign_keys=[contact_id])
    agent_action = db.relationship('CrmAgentAction', foreign_keys=[agent_action_id])


# ---------------------------------------------------------------------------
# Facebook (Meta) integration — connected Page, published posts, inbox cache
# ---------------------------------------------------------------------------
class CrmFacebookAccount(db.Model):
    """The Facebook Page connected to the CRM (single active connection).

    Stores the long-lived Page access token obtained via the OAuth connect
    flow. ``webhook_verify_token`` is informational; the actual webhook
    handshake uses the env FACEBOOK_WEBHOOK_VERIFY_TOKEN.
    """
    __tablename__ = 'crm_facebook_account'

    id = db.Column(db.Integer, primary_key=True)
    page_id = db.Column(db.String(64), nullable=False)
    page_name = db.Column(db.String(160))
    page_access_token = db.Column(db.Text, nullable=False)
    user_access_token = db.Column(db.Text)
    token_expires_at = db.Column(db.DateTime)
    active = db.Column(db.Boolean, default=True)
    connected_by_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    created_at = db.Column(db.DateTime, default=_utcnow)
    updated_at = db.Column(db.DateTime, default=_utcnow, onupdate=_utcnow)


class CrmFacebookPost(db.Model):
    """A post published (or scheduled) to the connected Page from the CRM."""
    __tablename__ = 'crm_facebook_post'

    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.Text, nullable=False)
    link = db.Column(db.String(500))
    image_url = db.Column(db.String(500))                # optional photo (Graph /photos)
    status = db.Column(db.String(20), default='draft')   # draft/scheduled/published/failed
    scheduled_for = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    fb_post_id = db.Column(db.String(80))
    error = db.Column(db.String(400))
    content_item_id = db.Column(db.Integer, db.ForeignKey('crm_content_item.id'))
    created_by_id = db.Column(db.Integer, db.ForeignKey('crm_user.id'))
    created_at = db.Column(db.DateTime, default=_utcnow)


class CrmFacebookMessage(db.Model):
    """Cached Page (Messenger) message, populated by the webhook + inbox sync."""
    __tablename__ = 'crm_facebook_message'

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.String(120), index=True)
    fb_message_id = db.Column(db.String(120), unique=True)
    sender_id = db.Column(db.String(64))          # PSID (page-scoped user id)
    sender_name = db.Column(db.String(160))
    direction = db.Column(db.String(4))           # 'in' (from user) / 'out' (from page)
    text = db.Column(db.Text)
    created_time = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=_utcnow)
