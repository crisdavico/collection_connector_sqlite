# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import os
import sqlite3

from odoo.modules.module import get_module_path
from odoo.tools import config

SAMPLE_CONNECTOR_XMLID = "collection_connector_sqlite.connector_sample_sellers"
_SAMPLE_SQLITE_NAME = "database.sqlite"


def sample_sqlite_path():
    """Return the absolute path of the install-time sample SQLite file."""
    return os.path.join(
        config["data_dir"], "collection_connector_sqlite", _SAMPLE_SQLITE_NAME
    )


def materialize_sample_sqlite():
    """Create the sample SQLite file from data/database.sql and return its path."""
    sql_path = os.path.join(
        get_module_path("collection_connector_sqlite"), "data", "database.sql"
    )
    dest = sample_sqlite_path()
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    with open(sql_path, encoding="utf-8") as handle:
        script = handle.read()
    if os.path.isfile(dest):
        os.remove(dest)
    conn = sqlite3.connect(dest)
    try:
        conn.executescript(script)
        conn.commit()
    finally:
        conn.close()
    return dest


def ensure_sample_sqlite_source(env):
    """Materialize the sample DB, point the xmlid connector at it, assign company."""
    path = materialize_sample_sqlite()
    connector = env.ref(SAMPLE_CONNECTOR_XMLID)
    connector.write({"type": "sqlite", "sqlite_path": path})
    company = env.ref("base.main_company")
    if not company.collection_connector_id:
        company.collection_connector_id = connector
    return connector


def post_init_hook(env):
    ensure_sample_sqlite_source(env)
