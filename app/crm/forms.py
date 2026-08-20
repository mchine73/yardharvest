"""WTForms used by the CRM blueprint."""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import (StringField, FloatField, SelectField, TextAreaField,
                     DateField, PasswordField, BooleanField, SubmitField)
from wtforms.validators import DataRequired, Optional, Length, EqualTo

from app.crm.models import (STAGES, DEAL_ROLES, CONTENT_CHANNELS,
                            CONTENT_STATUSES)


class CompanyForm(FlaskForm):
    name = StringField('Organization Name', validators=[DataRequired()])
    city = StringField('City', validators=[Optional()])
    state = StringField('State', validators=[Optional()])
    org_type = SelectField('Type',
                           choices=[('', '—'),
                                    ('Independent', 'Independent'),
                                    ('Nonprofit/Operator', 'Nonprofit/Operator'),
                                    ('City-Sponsored', 'City-Sponsored')],
                           validators=[Optional()])
    website = StringField('Website', validators=[Optional()])
    tags = StringField('Tags (comma-separated)', validators=[Optional()])
    fiscal_year_end = StringField('Fiscal year end', validators=[Optional()])
    submit = SubmitField('Save')


class ContactForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired()])
    email = StringField('Email', validators=[Optional()])
    phone = StringField('Phone', validators=[Optional()])
    company = SelectField('Company', coerce=int, validators=[Optional()],
                          validate_choice=False)
    image = FileField('Photo',
                      validators=[Optional(),
                                  FileAllowed(['jpg', 'jpeg', 'png', 'gif'],
                                              'Images only.')])
    email_opt_out = BooleanField('Do not email (opted out)')
    submit = SubmitField('Save')


class DealForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    amount = FloatField('Amount', validators=[Optional()])
    stage = SelectField('Stage', choices=[(s, s) for s in STAGES], default='Lead')
    contact = SelectField('Contact', coerce=int, validators=[Optional()],
                          validate_choice=False)
    funding_source = StringField('Funding source', validators=[Optional()])
    grant_status = SelectField('Grant status',
                               choices=[('', '—'), ('Applied', 'Applied'),
                                        ('Awarded', 'Awarded'),
                                        ('Denied', 'Denied'), ('N/A', 'N/A')],
                               validators=[Optional()])
    budget_decision_date = DateField('Budget decision date',
                                     validators=[Optional()])
    rfp_due_date = DateField('RFP due date', validators=[Optional()])
    submit = SubmitField('Save')


class NoteForm(FlaskForm):
    content = TextAreaField('Note', validators=[DataRequired()])
    submit = SubmitField('Add Note')


class TaskForm(FlaskForm):
    title = StringField('Task', validators=[DataRequired()])
    due_date = DateField('Due date', validators=[Optional()])
    priority = SelectField('Priority',
                           choices=[('Low', 'Low'), ('Medium', 'Medium'),
                                    ('High', 'High')],
                           default='Medium')
    submit = SubmitField('Add Task')


class DealContactForm(FlaskForm):
    contact = SelectField('Contact', coerce=int, validate_choice=False)
    role = SelectField('Role', choices=[(r, r) for r in DEAL_ROLES],
                       default='Influencer')
    submit = SubmitField('Add')


class EmailTemplateForm(FlaskForm):
    name = StringField('Template name', validators=[DataRequired()])
    subject = StringField('Subject', validators=[Optional()])
    body = TextAreaField('Body', validators=[Optional()])
    submit = SubmitField('Save')


class ComposeEmailForm(FlaskForm):
    template = SelectField('Use template', coerce=int, validators=[Optional()],
                           validate_choice=False)
    subject = StringField('Subject', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()])
    submit = SubmitField('Log / Send Email')


class ImportForm(FlaskForm):
    file = FileField('CSV file',
                     validators=[FileAllowed(['csv'], 'CSV files only.')])
    submit = SubmitField('Import')


class CampaignForm(FlaskForm):
    name = StringField('Campaign name', validators=[DataRequired()])
    template = SelectField('Start from template', coerce=int,
                           validators=[Optional()], validate_choice=False)
    subject = StringField('Subject', validators=[DataRequired()])
    body = TextAreaField('Body', validators=[DataRequired()])
    # Audience filters
    state = SelectField('State', validators=[Optional()], validate_choice=False)
    org_type = SelectField('Type',
                           choices=[('', 'All types'),
                                    ('Independent', 'Independent'),
                                    ('Nonprofit/Operator', 'Nonprofit/Operator'),
                                    ('City-Sponsored', 'City-Sponsored')],
                           validators=[Optional()])
    tag = StringField('Tag contains', validators=[Optional()])
    preview = SubmitField('Preview')
    test = SubmitField('Send test to me')
    send = SubmitField('Send / Log to audience')


class AICampaignForm(FlaskForm):
    """Drives the in-CRM AI marketing agent: a goal + audience filters. The
    agent drafts name/subject/body in the brand voice; the result is saved as a
    DRAFT campaign for human review (never auto-sent)."""
    goal = TextAreaField('Campaign goal', validators=[DataRequired(), Length(min=8)])
    name = StringField('Campaign name (optional)', validators=[Optional()])
    # Audience filters (same semantics as CampaignForm)
    state = SelectField('State', validators=[Optional()], validate_choice=False)
    org_type = SelectField('Type',
                           choices=[('', 'All types'),
                                    ('Independent', 'Independent'),
                                    ('Nonprofit/Operator', 'Nonprofit/Operator'),
                                    ('City-Sponsored', 'City-Sponsored')],
                           validators=[Optional()])
    tag = StringField('Tag contains', validators=[Optional()])
    submit = SubmitField('Draft with AI')


class SegmentForm(FlaskForm):
    name = StringField('Segment name', validators=[DataRequired()])
    description = StringField('Description', validators=[Optional()])
    state = SelectField('State', validators=[Optional()], validate_choice=False)
    org_type = SelectField('Type',
                           choices=[('', 'All types'),
                                    ('Independent', 'Independent'),
                                    ('Nonprofit/Operator', 'Nonprofit/Operator'),
                                    ('City-Sponsored', 'City-Sponsored')],
                           validators=[Optional()])
    tag = StringField('Tag contains', validators=[Optional()])
    submit = SubmitField('Save segment')


class ContentItemForm(FlaskForm):
    title = StringField('Title', validators=[DataRequired()])
    channel = SelectField('Channel',
                          choices=[(c, c) for c in CONTENT_CHANNELS],
                          default='Email')
    status = SelectField('Status',
                         choices=[(s, s) for s in CONTENT_STATUSES],
                         default='Idea')
    scheduled_date = DateField('Scheduled date', validators=[Optional()])
    campaign = SelectField('Linked campaign', coerce=int,
                           validators=[Optional()], validate_choice=False)
    body = TextAreaField('Notes / draft copy', validators=[Optional()])
    submit = SubmitField('Save')


class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    submit = SubmitField('Log in')


class ChangePasswordForm(FlaskForm):
    current_password = PasswordField('Current password',
                                     validators=[DataRequired()])
    new_password = PasswordField('New password',
                                 validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm new password',
                            validators=[DataRequired(),
                                        EqualTo('new_password',
                                                'Passwords must match')])
    submit = SubmitField('Change password')


class ResetPasswordForm(FlaskForm):
    new_password = PasswordField('New password',
                                 validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm new password',
                            validators=[DataRequired(),
                                        EqualTo('new_password',
                                                'Passwords must match')])
    submit = SubmitField('Reset password')


class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3)])
    email = StringField('Email', validators=[Optional()])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6)])
    confirm = PasswordField('Confirm password',
                            validators=[DataRequired(),
                                        EqualTo('password', 'Passwords must match')])
    submit = SubmitField('Create account')
