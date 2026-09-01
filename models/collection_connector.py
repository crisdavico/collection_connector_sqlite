# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import os
import sqlite3

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools.translate import _

from ..hooks import ensure_sample_sqlite_source

_SQLITE_PATH_REJECT_CHARS = ("?", "#", "\x00")
_SQLITE_REQUIRED_COLUMNS = frozenset({"id", "name", "mobile", "active"})
_SQLITE_CUSTOMER_COLUMNS = frozenset(
    {"id", "seller_id", "name", "identification", "customer_code", "active"}
)
_SQLITE_INVOICE_COLUMNS = frozenset(
    {
        "id",
        "customer_id",
        "number",
        "issue_date",
        "due_date",
        "amount",
        "balance",
        "state",
    }
)


def sqlite_path_is_rejected(path):
    """Return True when a SQLite path must not be opened."""
    if not path or not isinstance(path, str):
        return True
    if not os.path.isabs(path):
        return True
    return any(char in path for char in _SQLITE_PATH_REJECT_CHARS)


class CollectionConnectorSqlite(models.Model):
    _inherit = "collection.connector"

    type = fields.Selection(
        selection_add=[("sqlite", "SQLite")],
        ondelete={"sqlite": "cascade"},
    )
    sqlite_path = fields.Char(string="SQLite Path")
    sqlite_filename = fields.Char(compute="_compute_sqlite_file")
    sqlite_file = fields.Binary(
        string="SQLite File",
        compute="_compute_sqlite_file",
        attachment=False,
    )

    @api.model
    def _ensure_sample_sqlite_source(self):
        ensure_sample_sqlite_source(self.env)

    @api.depends("type", "sqlite_path")
    def _compute_sqlite_file(self):
        for rec in self:
            rec.sqlite_filename = False
            rec.sqlite_file = False
            if rec.type != "sqlite":
                continue
            path = rec.sqlite_path or ""
            if sqlite_path_is_rejected(path):
                continue
            if not os.path.isfile(path) or not os.access(path, os.R_OK):
                continue
            try:
                with open(path, "rb") as handle:
                    rec.sqlite_file = base64.b64encode(handle.read())
            except OSError:
                continue
            rec.sqlite_filename = os.path.basename(path)

    @api.private
    def _sqlite_misconfigured(self):
        raise UserError(_("The collection connector is not configured."))

    @api.private
    def _sqlite_safe_path(self):
        self.ensure_one()
        path = self.sqlite_path or ""
        if sqlite_path_is_rejected(path):
            self._sqlite_misconfigured()
        return path

    @api.private
    def _sqlite_connect(self, path):
        if not os.path.isfile(path) or not os.access(path, os.R_OK):
            self._sqlite_misconfigured()
        try:
            return sqlite3.connect("file:%s?mode=ro" % path, uri=True)  # noqa: UP031
        except sqlite3.Error:
            self._sqlite_misconfigured()

    @api.private
    def _sqlite_assert_schema(self, conn):
        try:
            rows = conn.execute("PRAGMA table_info(sellers)").fetchall()
        except sqlite3.Error:
            self._sqlite_misconfigured()
        columns = {row[1] for row in rows}
        if not _SQLITE_REQUIRED_COLUMNS.issubset(columns):
            self._sqlite_misconfigured()

    @api.private
    def _sqlite_fetch_sellers(self, path):
        conn = self._sqlite_connect(path)
        try:
            self._sqlite_assert_schema(conn)
            try:
                rows = conn.execute(
                    "SELECT id, name, mobile, active FROM sellers"
                ).fetchall()
            except sqlite3.Error:
                self._sqlite_misconfigured()
        finally:
            conn.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "mobile": row[2],
                "active": row[3],
            }
            for row in rows
        ]

    @api.private
    def _sqlite_assert_customer_schema(self, conn):
        try:
            rows = conn.execute("PRAGMA table_info(customers)").fetchall()
        except sqlite3.Error:
            self._sqlite_misconfigured()
        columns = {row[1] for row in rows}
        if not _SQLITE_CUSTOMER_COLUMNS.issubset(columns):
            self._sqlite_misconfigured()

    @api.private
    def _sqlite_fetch_customers(self, path, external_seller_id):
        conn = self._sqlite_connect(path)
        try:
            self._sqlite_assert_customer_schema(conn)
            try:
                rows = conn.execute(
                    """
                    SELECT id, name, identification, customer_code, active
                      FROM customers
                     WHERE seller_id = ?
                     ORDER BY id
                    """,
                    (external_seller_id,),
                ).fetchall()
            except sqlite3.Error:
                self._sqlite_misconfigured()
        finally:
            conn.close()
        return [
            {
                "id": row[0],
                "name": row[1],
                "identification": row[2],
                "customer_code": row[3],
                "active": row[4],
            }
            for row in rows
        ]

    @api.private
    def _sqlite_list_customers(self, external_seller_id):
        self.ensure_one()
        path = self._sqlite_safe_path()
        return self._sqlite_fetch_customers(path, external_seller_id)

    @api.private
    def _sqlite_assert_invoice_schema(self, conn):
        try:
            rows = conn.execute("PRAGMA table_info(invoices)").fetchall()
        except sqlite3.Error:
            self._sqlite_misconfigured()
        columns = {row[1] for row in rows}
        if not _SQLITE_INVOICE_COLUMNS.issubset(columns):
            self._sqlite_misconfigured()

    @api.private
    def _sqlite_fetch_customer_debt(self, path, external_seller_id, identification):
        conn = self._sqlite_connect(path)
        try:
            self._sqlite_assert_customer_schema(conn)
            self._sqlite_assert_invoice_schema(conn)
            try:
                customer_rows = conn.execute(
                    """
                    SELECT id, name, identification, customer_code, active
                      FROM customers
                     WHERE seller_id = ? AND identification = ?
                    """,
                    (external_seller_id, identification),
                ).fetchall()
            except sqlite3.Error:
                self._sqlite_misconfigured()
            if len(customer_rows) != 1:
                return {"customer": None, "invoices": []}
            customer_row = customer_rows[0]
            try:
                invoice_rows = conn.execute(
                    """
                    SELECT id, number, issue_date, due_date, amount, balance, state
                      FROM invoices
                     WHERE customer_id = ?
                     ORDER BY due_date, number, id
                    """,
                    (customer_row[0],),
                ).fetchall()
            except sqlite3.Error:
                self._sqlite_misconfigured()
        finally:
            conn.close()
        return {
            "customer": {
                "id": customer_row[0],
                "name": customer_row[1],
                "identification": customer_row[2],
                "customer_code": customer_row[3],
                "active": customer_row[4],
            },
            "invoices": [
                {
                    "id": row[0],
                    "number": row[1],
                    "issue_date": row[2],
                    "due_date": row[3],
                    "amount": row[4],
                    "balance": row[5],
                    "state": row[6],
                }
                for row in invoice_rows
            ],
        }

    @api.private
    def _sqlite_get_customer_debt(self, external_seller_id, customer_identification):
        self.ensure_one()
        path = self._sqlite_safe_path()
        return self._sqlite_fetch_customer_debt(
            path, external_seller_id, customer_identification
        )

    @api.private
    def _sqlite_list_sellers(self):
        self.ensure_one()
        path = self._sqlite_safe_path()
        return self._sqlite_fetch_sellers(path)

    @api.private
    def _sqlite_test_connection(self):
        self.ensure_one()
        path = self._sqlite_safe_path()
        self._sqlite_fetch_sellers(path)
        return True
