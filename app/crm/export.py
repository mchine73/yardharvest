"""CRM system-of-record export (backup).

The CRM database is the source of truth for the whole outbound pipeline and
lives on a free Postgres plan (90-day expiry risk), so we periodically dump
the record tables to a zip of CSVs that can be emailed off-box and used to
rebuild or audit the pipeline.

Deliberately EXCLUDED from every export:
  - CrmFacebookAccount (holds live Page/user access tokens)
  - CrmUser (password hashes)
  - any column whose name looks secret-ish (token/password/secret), as
    belt-and-suspenders should a model grow one later.
"""
import csv
import io
import zipfile
from datetime import datetime, timezone

from .models import (Company, Contact, Deal, DealContact, Note, Task,
                     Activity, EmailTemplate, Campaign, CampaignRecipient,
                     Segment, ContentItem, CrmAgentAction, CrmAgentRun,
                     CrmEmailEvent)

# The system-of-record tables, in restore-friendly order.
EXPORT_MODELS = [
    Company, Contact, Deal, DealContact, Note, Task, Activity,
    EmailTemplate, Campaign, CampaignRecipient, Segment, ContentItem,
    CrmAgentAction, CrmAgentRun, CrmEmailEvent,
]

_SECRET_MARKERS = ('token', 'password', 'secret')


def _safe_columns(model):
    return [c.name for c in model.__table__.columns
            if not any(m in c.name.lower() for m in _SECRET_MARKERS)]


def _model_csv(model):
    """Dump one model to CSV text (streamed row query, secret columns dropped)."""
    cols = _safe_columns(model)
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for row in model.query.yield_per(500):
        writer.writerow(['' if getattr(row, c) is None else getattr(row, c)
                         for c in cols])
    return buf.getvalue()


def build_export_zip():
    """Build the full export as zip bytes; returns (bytes, manifest dict)."""
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    manifest = {'generated': stamp, 'tables': {}}
    out = io.BytesIO()
    with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as zf:
        for model in EXPORT_MODELS:
            name = model.__tablename__
            data = _model_csv(model)
            # header row is always present; count data rows only
            manifest['tables'][name] = max(0, data.count('\n') - 1)
            zf.writestr(f'{name}.csv', data)
        lines = [f'CRM export generated {stamp}', '']
        lines += [f'{t}: {n} rows' for t, n in manifest['tables'].items()]
        zf.writestr('MANIFEST.txt', '\n'.join(lines) + '\n')
    return out.getvalue(), manifest
