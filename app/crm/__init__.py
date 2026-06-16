"""CRM module (Customer Relationship Management) for YardHarvest.

Mounted at ``/crm`` via the ``crm_bp`` blueprint. Provides company / contact /
deal / task / campaign management for the internal YardHarvest sales team.

This module was originally a standalone Flask app (``yardharvest-crm`` Render
service) and was consolidated into the main yardharvest app to eliminate the
second Render web service + database. Key conventions:

* All database tables are prefixed ``crm_`` to avoid collision with YH tables
  (see ``app/crm/models.py``). The CRM user table is ``crm_user`` and the
  ``CrmUser`` model is *separate* from YH's ``User`` model — CRM auth is
  session-based and lives at ``/crm/login``.
* Templates live under ``app/templates/crm/`` (so ``base.html`` becomes
  ``crm/base.html`` and so on). Static assets live under ``app/static/crm/``.
* The token-authenticated marketing API for the marketing-agent CLI is mounted
  at ``/crm/api/marketing/*`` (was ``/api/marketing/*`` in the standalone app).
"""
from flask import Blueprint

crm_bp = Blueprint(
    'crm',
    __name__,
    url_prefix='/crm',
    # Templates live under app/templates/crm/ and are referenced by
    # ``render_template('crm/<name>.html')`` via Flask's app-level template
    # loader. We deliberately do NOT set ``template_folder`` here because
    # blueprint template folders are *additive* to the global namespace —
    # setting it would also make bare names like 'dashboard.html' resolve from
    # the CRM dir, risking collisions with YH templates.
    static_folder='../static/crm',
    # static_url_path is appended to url_prefix, so '/static' yields the final
    # path '/crm/static' (NOT '/crm/static' here, which would double up to
    # '/crm/crm/static'). Templates use url_for('crm.static', filename=...).
    static_url_path='/static',
)

# Importing the view modules registers their routes on crm_bp. Done at the
# bottom to avoid circular imports — Flask blueprints support late binding.
from app.crm import views  # noqa: E402,F401
from app.crm import marketing_api  # noqa: E402,F401
from app.crm import facebook_views  # noqa: E402,F401
