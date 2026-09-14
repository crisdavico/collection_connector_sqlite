# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

from odoo.addons.collection_connector_sqlite.hooks import ensure_sample_sqlite_source


def migrate(cr, version):
    """Rematerialize the sample SQLite source, including voucher-matched debt."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    ensure_sample_sqlite_source(env)
