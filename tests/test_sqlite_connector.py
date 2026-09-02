# Copyright 2026 Seedian
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import base64
import json
import os
import shutil
import sqlite3
import stat
import tempfile
from unittest.mock import patch

from odoo.exceptions import UserError
from odoo.modules.module import load_manifest
from odoo.tests import TransactionCase

from odoo.addons.collection.tests.test_collection_payment import (
    create_internal_seller,
    ensure_enabled_seller,
)

from ..models.collection_connector import sqlite_path_is_rejected

_LEAK_TOKENS = (
    "SELECT",
    "INSERT",
    "UPDATE",
    "DELETE FROM",
    "CREATE TABLE",
    "sqlite3",
    "file:",
    "?mode=",
    ".db",
    "/tmp",
    "/home",
    "/var",
)


class TestSqliteConnector(TransactionCase):
    """SQLite connector: path-safe read-only open, schema, no leak."""

    def _leak_extras(self, *paths):
        extras = []
        for path in paths:
            if not path:
                continue
            extras.append(path)
            extras.append(os.path.basename(path))
        return tuple(extras)

    def _assert_user_error_no_leak(self, func, *paths):
        with self.assertRaises(UserError) as ctx:
            func()
        message = str(ctx.exception)
        for token in _LEAK_TOKENS + self._leak_extras(*paths):
            self.assertNotIn(token, message)
        return ctx.exception

    def _assert_not_connected(self, func, *paths):
        with patch("sqlite3.connect") as mocked:
            self._assert_user_error_no_leak(func, *paths)
            mocked.assert_not_called()

    def _assert_connection_ok(self, connector):
        action = connector.test_connection()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "display_notification")
        self.assertEqual(action["params"]["type"], "success")
        return action

    def _make_sqlite_connector(self, sqlite_path, name="SQLite Connector"):
        return self.env["collection.connector"].create(
            {
                "name": name,
                "type": "sqlite",
                "sqlite_path": sqlite_path,
            }
        )

    def _write_executable(self, filename):
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, filename)
        sentinel = os.path.join(folder, "EXECUTED")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("#!/bin/sh\n")
            handle.write(f"echo executed > '{sentinel}'\n")
        os.chmod(path, stat.S_IRWXU)
        return path, sentinel

    def _sqlite_path_is_rejected(self, path):
        return sqlite_path_is_rejected(path)

    def test_requirements_txt_raises_user_error_not_executed(self):
        """3.2 Absolute requirements.txt MUST UserError, not execute, no leak."""
        path, sentinel = self._write_executable("requirements.txt")
        connector = self._make_sqlite_connector(path, name="SQLite requirements")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)
        self.assertFalse(os.path.exists(sentinel))

    def test_cmakelists_txt_raises_user_error_not_executed(self):
        """3.3 Absolute CMakeLists.txt MUST UserError, not execute, no leak."""
        path, sentinel = self._write_executable("CMakeLists.txt")
        connector = self._make_sqlite_connector(path, name="SQLite CMakeLists")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)
        self.assertFalse(os.path.exists(sentinel))

    def test_executable_markdown_mdx_raises_user_error_not_executed(self):
        """3.4 Executable Markdown/MDX MUST UserError, not execute, no leak."""
        md_path, md_sentinel = self._write_executable("notes.md")
        mdx_path, mdx_sentinel = self._write_executable("notes.mdx")
        md_connector = self._make_sqlite_connector(md_path, name="SQLite Markdown")
        mdx_connector = self._make_sqlite_connector(mdx_path, name="SQLite MDX")
        self._assert_user_error_no_leak(md_connector.list_sellers, md_path)
        self._assert_user_error_no_leak(md_connector.test_connection, md_path)
        self._assert_user_error_no_leak(mdx_connector.list_sellers, mdx_path)
        self._assert_user_error_no_leak(mdx_connector.test_connection, mdx_path)
        self.assertFalse(os.path.exists(md_sentinel))
        self.assertFalse(os.path.exists(mdx_sentinel))

    def test_readme_sh_raises_user_error_not_executed(self):
        """3.5 Absolute README.sh MUST UserError, not execute, no leak."""
        path, sentinel = self._write_executable("README.sh")
        connector = self._make_sqlite_connector(path, name="SQLite README.sh")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)
        self.assertFalse(os.path.exists(sentinel))

    def test_relative_path_raises_user_error_no_leak(self):
        """3.6 Relative path MUST UserError, never sqlite3.connect, no leak."""
        self.assertTrue(self._sqlite_path_is_rejected("sellers.db"))
        self.assertTrue(self._sqlite_path_is_rejected("./sellers.db"))
        connector = self._make_sqlite_connector("sellers.db", name="SQLite relative")
        self._assert_not_connected(connector.list_sellers, "sellers.db")
        self._assert_not_connected(connector.test_connection, "sellers.db")
        other = self._make_sqlite_connector("./sellers.db", name="SQLite dot relative")
        self._assert_not_connected(other.list_sellers, "./sellers.db")

    def test_path_query_mode_rw_raises_user_error_no_leak(self):
        """3.7 path?mode=rw MUST UserError, never sqlite3.connect, no leak."""
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        abs_path = os.path.join(folder, "sellers.db")
        injected = f"{abs_path}?mode=rw"
        self.assertTrue(self._sqlite_path_is_rejected(injected))
        connector = self._make_sqlite_connector(injected, name="SQLite URI injection")
        self._assert_not_connected(connector.list_sellers, injected, abs_path)
        self._assert_not_connected(connector.test_connection, injected, abs_path)

    def test_path_hash_raises_user_error_no_leak(self):
        """3.8 Fragment # MUST be rejected before sqlite3.connect."""
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        abs_path = os.path.join(folder, "sellers.db")
        injected = f"{abs_path}#frag"
        self.assertTrue(self._sqlite_path_is_rejected(injected))
        connector = self._make_sqlite_connector(injected, name="SQLite hash")
        self._assert_not_connected(connector.list_sellers, injected, abs_path)
        self._assert_not_connected(connector.test_connection, injected, abs_path)

    def test_path_nul_raises_user_error_no_leak(self):
        """3.8 NUL MUST be rejected before sqlite3.connect."""
        self.assertTrue(self._sqlite_path_is_rejected("/abs/sellers.db\x00rw"))
        self.assertTrue(self._sqlite_path_is_rejected("/abs/sellers.db\0mode=rw"))
        self.assertFalse(self._sqlite_path_is_rejected("/abs/sellers.db"))

    def test_missing_file_raises_user_error_no_path_sql(self):
        """3.9 Missing file MUST UserError with no path or SQL."""
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "missing.sqlite")
        self.assertFalse(os.path.exists(path))
        connector = self._make_sqlite_connector(path, name="SQLite missing")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)

    def test_unreadable_file_raises_user_error_no_path_sql(self):
        """3.10 Unreadable file MUST UserError with no path or SQL."""
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "unreadable.sqlite")
        with open(path, "wb") as handle:
            handle.write(b"not-a-database")
        os.chmod(path, 0)

        def _restore():
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

        self.addCleanup(_restore)
        connector = self._make_sqlite_connector(path, name="SQLite unreadable")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)

    def test_invalid_schema_raises_user_error_no_path_sql(self):
        """3.11 Invalid schema MUST UserError with no path or SQL."""
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "invalid.sqlite")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE other (id TEXT PRIMARY KEY)")
        conn.commit()
        conn.close()
        connector = self._make_sqlite_connector(path, name="SQLite invalid schema")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)

    def _write_sellers_db_without_commission(self, rows):
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "sellers.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.executemany(
            "INSERT INTO sellers (id, name, mobile, active) VALUES (?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
        return path

    def test_missing_commission_percent_column_raises_user_error_no_path_sql(self):
        """Missing commission_percent MUST UserError with no path or SQL."""
        path = self._write_sellers_db_without_commission((("s1", "Ana", "549111", 1),))
        with open(path, "rb") as handle:
            before = handle.read()
        connector = self._make_sqlite_connector(path, name="SQLite missing commission")
        self._assert_user_error_no_leak(connector.list_sellers, path)
        self._assert_user_error_no_leak(connector.test_connection, path)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def _write_sellers_db(self, rows):
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "sellers.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                commission_percent REAL NOT NULL DEFAULT 0
                    CHECK (commission_percent >= 0 AND commission_percent <= 100)
            )
            """
        )
        conn.executemany(
            "INSERT INTO sellers "
            "(id, name, mobile, active, commission_percent) "
            "VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        conn.close()
        return path

    def test_sqlite_success_list_and_connection_test_does_not_write(self):
        """3.13 Success lists active sellers, tests connection, and does not write."""
        path = self._write_sellers_db(
            (
                ("s1", "Ana", "549111", 1, 0.0),
                ("s2", "Beto", "549112", 1, 0.0),
                ("s3", "Cora", None, 0, 0.0),
            )
        )
        with open(path, "rb") as handle:
            before = handle.read()
        connector = self._make_sqlite_connector(path, name="SQLite success")
        result = connector.list_sellers()
        self.assertEqual(
            [row["external_seller_id"] for row in result["sellers"]],
            ["s1", "s2"],
        )
        self.assertEqual(result["sellers"][0]["name"], "Ana")
        self.assertEqual(result["source"]["connector_type"], "sqlite")
        self.assertEqual(result["source"]["connector_id"], connector.id)
        self._assert_connection_ok(connector)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)

    def test_sqlite_selection_add_and_path_field(self):
        """3.14 selection_add sqlite + sqlite_path; ondelete cascade."""
        field = self.env["collection.connector"]._fields["type"]
        keys = {value for value, _label in field._description_selection(self.env)}
        self.assertIn("sqlite", keys)
        self.assertEqual(field.ondelete.get("sqlite"), "cascade")
        self.assertIn("sqlite_path", self.env["collection.connector"]._fields)
        manifest = load_manifest("collection_connector_sqlite")
        self.assertIn("collection", manifest["depends"])

    def test_sqlite_form_view_has_path_and_test_button(self):
        """3.14 Form inherit exposes sqlite_path and admin connection-test."""
        view = self.env.ref(
            "collection_connector_sqlite.view_collection_connector_form_sqlite"
        )
        arch = view.arch
        self.assertIn("sqlite_path", arch)
        self.assertIn("sqlite_file", arch)
        self.assertIn("test_connection", arch)

    def test_install_materializes_sqlite_connector_for_ui(self):
        """Install seeds sqlite file, xmlid connector, download, and company M2O."""
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        self.assertEqual(connector.type, "sqlite")
        self.assertFalse(sqlite_path_is_rejected(connector.sqlite_path))
        self.assertTrue(os.path.isfile(connector.sqlite_path))
        self.assertTrue(os.access(connector.sqlite_path, os.R_OK))
        self._assert_connection_ok(connector)
        result = connector.list_sellers()
        self.assertEqual(
            [row["external_seller_id"] for row in result["sellers"]],
            [
                "seller-001",
                "seller-002",
                "seller-003",
                "seller-004",
                "seller-005",
            ],
        )
        self.assertEqual(connector.sqlite_filename, "database.sqlite")
        self.assertTrue(connector.sqlite_file)
        payload = base64.b64decode(connector.sqlite_file)
        self.assertTrue(payload.startswith(b"SQLite format 3"))
        company = self.env.ref("base.main_company")
        company.collection_connector_id = False
        connector._ensure_sample_sqlite_source()
        self.assertEqual(company.collection_connector_id, connector)
        self._assert_connection_ok(connector)

    def test_sample_sqlite_customers_and_invoices_fixture(self):
        """Sample DB has customers/invoices, FKs, volume, and twisted cases."""
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        connector._ensure_sample_sqlite_source()
        conn = sqlite3.connect(connector.sqlite_path)
        try:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertTrue({"sellers", "customers", "invoices"}.issubset(tables))
            customer_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(customers)")
            }
            self.assertTrue(
                {
                    "id",
                    "seller_id",
                    "name",
                    "identification",
                    "customer_code",
                    "active",
                }.issubset(customer_cols)
            )
            invoice_cols = {
                row[1] for row in conn.execute("PRAGMA table_info(invoices)")
            }
            self.assertTrue(
                {
                    "id",
                    "customer_id",
                    "number",
                    "issue_date",
                    "due_date",
                    "amount",
                    "balance",
                    "state",
                }.issubset(invoice_cols)
            )
            customer_fks = conn.execute("PRAGMA foreign_key_list(customers)").fetchall()
            self.assertTrue(
                any(
                    row[2] == "sellers" and row[3] == "seller_id" and row[4] == "id"
                    for row in customer_fks
                )
            )
            invoice_fks = conn.execute("PRAGMA foreign_key_list(invoices)").fetchall()
            self.assertTrue(
                any(
                    row[2] == "customers" and row[3] == "customer_id" and row[4] == "id"
                    for row in invoice_fks
                )
            )
            counts = dict(
                conn.execute(
                    """
                    SELECT seller_id, COUNT(*)
                    FROM customers
                    GROUP BY seller_id
                    """
                ).fetchall()
            )
            for seller_id in (
                "seller-001",
                "seller-002",
                "seller-003",
                "seller-004",
                "seller-005",
            ):
                self.assertGreaterEqual(counts.get(seller_id, 0), 6, seller_id)
            self.assertEqual(counts.get("seller-006", 0), 0)
            codes = [
                row[0] for row in conn.execute("SELECT customer_code FROM customers")
            ]
            self.assertTrue(all(codes))
            self.assertEqual(len(codes), len(set(codes)))
            zero_invoice = conn.execute(
                """
                SELECT c.id
                FROM customers c
                LEFT JOIN invoices i ON i.customer_id = c.id
                WHERE i.id IS NULL AND c.active = 1
                """
            ).fetchall()
            self.assertTrue(zero_invoice)
            inactive_debt = conn.execute(
                """
                SELECT c.id
                FROM customers c
                JOIN invoices i ON i.customer_id = c.id
                WHERE c.active = 0 AND i.balance > 0
                """
            ).fetchall()
            self.assertTrue(inactive_debt)
            partial = conn.execute(
                """
                SELECT id FROM invoices
                WHERE balance > 0 AND balance < amount
                """
            ).fetchall()
            self.assertTrue(partial)
            due_today = conn.execute(
                """
                SELECT id FROM invoices
                WHERE due_date = '2026-08-26' AND state = 'open'
                """
            ).fetchall()
            self.assertTrue(due_today)
            due_yesterday = conn.execute(
                """
                SELECT id FROM invoices
                WHERE due_date = '2026-08-25' AND state = 'overdue'
                """
            ).fetchall()
            self.assertTrue(due_yesterday)
            tiny = conn.execute(
                "SELECT id FROM invoices WHERE amount = 1.0 AND balance > 0"
            ).fetchall()
            self.assertTrue(tiny)
            huge = conn.execute(
                "SELECT id FROM invoices WHERE amount >= 1000000"
            ).fetchall()
            self.assertTrue(huge)
            accented = conn.execute(
                """
                SELECT id FROM customers
                WHERE name LIKE '%O''Higgins%' OR name LIKE '%Peñaloza%'
                """
            ).fetchall()
            self.assertTrue(accented)
            duplicate_trade = conn.execute(
                """
                SELECT name
                FROM customers
                GROUP BY name
                HAVING COUNT(DISTINCT seller_id) >= 2
                """
            ).fetchall()
            self.assertTrue(duplicate_trade)
        finally:
            conn.close()
        result = connector.list_sellers()
        self.assertEqual(
            [row["external_seller_id"] for row in result["sellers"]],
            [
                "seller-001",
                "seller-002",
                "seller-003",
                "seller-004",
                "seller-005",
            ],
        )
        self._assert_connection_ok(connector)

    def test_sample_sqlite_seller_commission_percent_rates(self):
        """Sample sellers MUST report Ana 5.0 … Elena 3.0; Facundo omitted."""
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        connector._ensure_sample_sqlite_source()
        conn = sqlite3.connect(connector.sqlite_path)
        try:
            seller_cols = {row[1] for row in conn.execute("PRAGMA table_info(sellers)")}
            self.assertIn("commission_percent", seller_cols)
            rates = dict(
                conn.execute("SELECT id, commission_percent FROM sellers").fetchall()
            )
            names = dict(conn.execute("SELECT id, name FROM sellers").fetchall())
            actives = dict(conn.execute("SELECT id, active FROM sellers").fetchall())
        finally:
            conn.close()
        self.assertEqual(names["seller-001"], "Ana Pérez")
        self.assertEqual(rates["seller-001"], 5.0)
        self.assertEqual(names["seller-002"], "Bruno Gómez")
        self.assertEqual(rates["seller-002"], 7.5)
        self.assertEqual(names["seller-003"], "Carla Díaz")
        self.assertEqual(rates["seller-003"], 10.0)
        self.assertEqual(names["seller-004"], "Diego Fernández")
        self.assertEqual(rates["seller-004"], 0.0)
        self.assertEqual(names["seller-005"], "Elena Ruiz")
        self.assertEqual(rates["seller-005"], 3.0)
        self.assertEqual(names["seller-006"], "Facundo López")
        self.assertEqual(rates["seller-006"], 5.0)
        self.assertEqual(actives["seller-006"], 0)
        fetched = {
            row["id"]: row
            for row in connector._sqlite_fetch_sellers(connector.sqlite_path)
        }
        self.assertEqual(fetched["seller-001"]["commission_percent"], 5.0)
        self.assertEqual(fetched["seller-002"]["commission_percent"], 7.5)
        self.assertEqual(fetched["seller-003"]["commission_percent"], 10.0)
        self.assertEqual(fetched["seller-004"]["commission_percent"], 0.0)
        self.assertEqual(fetched["seller-005"]["commission_percent"], 3.0)
        self.assertEqual(fetched["seller-006"]["commission_percent"], 5.0)
        result = connector.list_sellers()
        listed_ids = [row["external_seller_id"] for row in result["sellers"]]
        self.assertEqual(
            listed_ids,
            [
                "seller-001",
                "seller-002",
                "seller-003",
                "seller-004",
                "seller-005",
            ],
        )
        self.assertNotIn("seller-006", listed_ids)
        listed_names = {row["name"] for row in result["sellers"]}
        self.assertEqual(
            listed_names,
            {
                "Ana Pérez",
                "Bruno Gómez",
                "Carla Díaz",
                "Diego Fernández",
                "Elena Ruiz",
            },
        )

    def test_rollback_vouchers_sheets_mcp_unchanged(self):
        """3.15 Vouchers, sheets, get_seller_id, and create MCP stay unchanged."""
        seller = create_internal_seller(self.env, "sqlite_rollback_seller")
        ensure_enabled_seller(self.env, seller)
        seller.partner_id.phone = "+54 9 11 5555-9999"
        voucher = self.env["collection.voucher"].create(
            {
                "seller_id": seller.id,
                "customer_identification": "SQLITE-RB-CUST",
                "document_type": "bank_transfer",
                "amount": 10.0,
                "document_id": "SQLITE-ROLLBACK-DOC",
            }
        )
        self.assertTrue(voucher.id)
        self.assertTrue(voucher.name)
        self.assertEqual(voucher.state, "pending")
        self.assertTrue(voucher.sheet_id)
        sheet_id = voucher.sheet_id.id
        tool_model = self.env["muk_mcp.tool"]
        lookup_text, _info = tool_model._call(
            "get_seller_id",
            {"mobile": "5491155559999"},
            self.env,
        )
        lookup = json.loads(lookup_text)
        self.assertEqual(lookup["seller_id"], seller.id)
        create_text, _create_info = tool_model._call(
            "create_collection_vouchers",
            {
                "customer_identification": "SQLITE-RB",
                "seller_id": seller.id,
                "payments": [
                    {
                        "document_id": "SQLITE-RB-DOC-2",
                        "document_type": "bank_transfer",
                        "amount": 25.0,
                        "from_account": "FROM-RB",
                        "to_account": "TO-RB",
                    }
                ],
            },
            self.env,
        )
        created = json.loads(create_text)
        self.assertEqual(created["vouchers"][0]["document_id"], "SQLITE-RB-DOC-2")
        self.assertEqual(created["vouchers"][0]["state"], "pending")
        self.assertEqual(voucher.sheet_id.id, sheet_id)

    def test_company_m2o_set_null_when_sqlite_connector_unlinked(self):
        """3.16 Unlinking a sqlite connector MUST set company M2O to null."""
        path = self._write_sellers_db((("s1", "Ana", "549111", 1, 0.0),))
        connector = self._make_sqlite_connector(path, name="SQLite unlink")
        company = self.env.company
        company.collection_connector_id = connector
        self.assertEqual(company.collection_connector_id, connector)
        connector_id = connector.id
        connector.unlink()
        self.assertFalse(self.env["collection.connector"].browse(connector_id).exists())
        self.assertFalse(company.collection_connector_id)
        company_field = self.env["res.company"]._fields["collection_connector_id"]
        self.assertEqual(company_field.ondelete, "set null")

    def test_import_from_sample_connector_creates_five_users_and_replaces_list(self):
        """Sample SQLite Import MUST enable the five active sellers."""
        extra = create_internal_seller(self.env, "sqlite_import_extra")
        ensure_enabled_seller(self.env, extra)
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        company = self.env.company
        company.collection_connector_id = connector
        self.assertIn(extra, company.enabled_seller_ids)
        company._sync_enabled_sellers_from_connector()
        enabled = company.enabled_seller_ids
        self.assertEqual(len(enabled), 5)
        self.assertNotIn(extra, enabled)
        self.assertEqual(
            set(connector.seller_binding_ids.mapped("external_seller_id")),
            {
                "seller-001",
                "seller-002",
                "seller-003",
                "seller-004",
                "seller-005",
            },
        )

    def _write_source_db(self, sellers, customers):
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "source.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                commission_percent REAL NOT NULL DEFAULT 0
                    CHECK (commission_percent >= 0 AND commission_percent <= 100)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE customers (
                id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL,
                name TEXT NOT NULL,
                identification TEXT NOT NULL,
                customer_code TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.executemany(
            "INSERT INTO sellers "
            "(id, name, mobile, active, commission_percent) "
            "VALUES (?, ?, ?, ?, ?)",
            sellers,
        )
        conn.executemany(
            """
            INSERT INTO customers (
                id, seller_id, name, identification, customer_code, active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            customers,
        )
        conn.commit()
        conn.close()
        return path

    def _enabled_bound_seller(self, connector, external_seller_id, login):
        user = create_internal_seller(self.env, login)
        ensure_enabled_seller(self.env, user)
        self.env["collection.connector.seller.binding"].create(
            {
                "connector_id": connector.id,
                "external_seller_id": external_seller_id,
                "user_id": user.id,
            }
        )
        return user

    def test_sqlite_list_customers_active_only_and_seller_isolation(self):
        """Seller-scoped read MUST return that seller's active customers only."""
        path = self._write_source_db(
            (
                ("s1", "Ana", "549111", 1, 0.0),
                ("s2", "Beto", "549112", 1, 0.0),
            ),
            (
                ("c1", "s1", "Active One", "20-1", "C-1", 1),
                ("c2", "s1", "Inactive One", "20-2", "C-2", 0),
                ("c3", "s2", "Other Seller", "20-3", "C-3", 1),
            ),
        )
        with open(path, "rb") as handle:
            before = handle.read()
        connector = self._make_sqlite_connector(path, name="SQLite customers")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_cust_s1")
        result = connector.list_customers(seller.id)
        self.assertEqual(
            [row["external_customer_id"] for row in result["customers"]],
            ["c1"],
        )
        row = result["customers"][0]
        self.assertEqual(row["name"], "Active One")
        self.assertEqual(row["identification"], "20-1")
        self.assertEqual(row["customer_code"], "C-1")
        self.assertEqual(result["source"]["connector_type"], "sqlite")
        self.assertEqual(result["source"]["connector_id"], connector.id)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self._assert_connection_ok(connector)
        sellers = connector.list_sellers()
        self.assertEqual(
            [row["external_seller_id"] for row in sellers["sellers"]],
            ["s1", "s2"],
        )

    def test_sqlite_list_customers_malformed_schema_raises_user_error(self):
        """Invalid customers schema MUST UserError; sellers listing still works."""
        path = self._write_sellers_db((("s1", "Ana", "549111", 1, 0.0),))
        connector = self._make_sqlite_connector(path, name="SQLite no customers")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_cust_schema")
        self._assert_user_error_no_leak(
            lambda: connector.list_customers(seller.id), path
        )
        result = connector.list_sellers()
        self.assertEqual(
            [row["external_seller_id"] for row in result["sellers"]],
            ["s1"],
        )
        self._assert_connection_ok(connector)

        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bad_path = os.path.join(folder, "bad-customers.sqlite")
        conn = sqlite3.connect(bad_path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                commission_percent REAL NOT NULL DEFAULT 0
                    CHECK (commission_percent >= 0 AND commission_percent <= 100)
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sellers (id, name, mobile, active, commission_percent)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("s1", "Ana", "549111", 1, 0.0),
        )
        conn.execute("CREATE TABLE customers (id TEXT PRIMARY KEY, name TEXT)")
        conn.commit()
        conn.close()
        bad_connector = self._make_sqlite_connector(
            bad_path, name="SQLite bad customers"
        )
        bad_seller = self._enabled_bound_seller(
            bad_connector, "s1", "sqlite_cust_bad_schema"
        )
        self._assert_user_error_no_leak(
            lambda: bad_connector.list_customers(bad_seller.id), bad_path
        )
        self._assert_connection_ok(bad_connector)

    def test_sample_sqlite_list_customers_for_imported_seller(self):
        """Sample DB MUST list seller-001's five active customers after Import."""
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        company = self.env.company
        company.collection_connector_id = connector
        company._sync_enabled_sellers_from_connector()
        binding = connector.seller_binding_ids.filtered(
            lambda rec: rec.external_seller_id == "seller-001"
        )
        self.assertEqual(len(binding), 1)
        result = connector.list_customers(binding.user_id.id)
        ids = [row["external_customer_id"] for row in result["customers"]]
        self.assertEqual(
            ids,
            ["cust-001", "cust-002", "cust-003", "cust-004", "cust-005"],
        )
        self.assertNotIn("cust-006", ids)
        self.assertNotIn("cust-007", ids)

    def _write_debt_db(self, sellers, customers, invoices):
        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        path = os.path.join(folder, "debt.sqlite")
        conn = sqlite3.connect(path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                commission_percent REAL NOT NULL DEFAULT 0
                    CHECK (commission_percent >= 0 AND commission_percent <= 100)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE customers (
                id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL,
                name TEXT NOT NULL,
                identification TEXT NOT NULL,
                customer_code TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE invoices (
                id TEXT PRIMARY KEY,
                customer_id TEXT NOT NULL,
                number TEXT NOT NULL,
                issue_date TEXT NOT NULL,
                due_date TEXT NOT NULL,
                amount REAL NOT NULL,
                balance REAL NOT NULL,
                state TEXT NOT NULL
            )
            """
        )
        conn.executemany(
            "INSERT INTO sellers "
            "(id, name, mobile, active, commission_percent) "
            "VALUES (?, ?, ?, ?, ?)",
            sellers,
        )
        conn.executemany(
            """
            INSERT INTO customers (
                id, seller_id, name, identification, customer_code, active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            customers,
        )
        conn.executemany(
            """
            INSERT INTO invoices (
                id, customer_id, number, issue_date, due_date, amount, balance, state
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            invoices,
        )
        conn.commit()
        conn.close()
        return path

    def test_sqlite_get_customer_debt_outstanding_only_and_does_not_write(self):
        """Seller-scoped debt MUST return outstanding invoices and not write."""
        path = self._write_debt_db(
            (("s1", "Ana", "549111", 1, 0.0), ("s2", "Beto", "549112", 1, 0.0)),
            (
                ("c1", "s1", "Active One", "20-1", "C-1", 1),
                ("c2", "s1", "Inactive One", "20-2", "C-2", 0),
                ("c3", "s2", "Other Seller", "20-3", "C-3", 1),
            ),
            (
                (
                    "i1",
                    "c1",
                    "A-1",
                    "2026-01-10",
                    "2026-03-10",
                    100.0,
                    100.0,
                    "overdue",
                ),
                ("i2", "c1", "A-2", "2026-04-01", "2026-09-01", 50.0, 50.0, "open"),
                ("i3", "c1", "A-3", "2026-02-01", "2026-03-01", 20.0, 0.0, "paid"),
                ("i4", "c1", "A-4", "2026-05-01", "2026-10-01", 30.0, 0.0, "open"),
                ("i5", "c2", "A-5", "2026-01-01", "2026-02-01", 80.0, 80.0, "overdue"),
                ("i6", "c3", "A-6", "2026-06-01", "2026-08-01", 40.0, 40.0, "open"),
            ),
        )
        with open(path, "rb") as handle:
            before = handle.read()
        connector = self._make_sqlite_connector(path, name="SQLite debt")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_debt_s1")
        result = connector.get_customer_debt(seller.id, "20-1")
        self.assertEqual(result["customer"]["external_customer_id"], "c1")
        self.assertEqual(result["customer"]["name"], "Active One")
        self.assertEqual(result["customer"]["identification"], "20-1")
        self.assertEqual(result["customer"]["customer_code"], "C-1")
        self.assertEqual(
            [row["external_invoice_id"] for row in result["invoices"]],
            ["i1", "i2"],
        )
        self.assertEqual(result["invoices"][0]["state"], "overdue")
        self.assertEqual(result["invoices"][1]["state"], "open")
        self.assertEqual(result["summary"]["total_balance"], 150.0)
        self.assertEqual(result["summary"]["overdue_balance"], 100.0)
        self.assertEqual(result["summary"]["open_balance"], 50.0)
        self.assertEqual(result["summary"]["invoice_count"], 2)
        self.assertEqual(result["source"]["connector_type"], "sqlite")
        self.assertEqual(result["source"]["connector_id"], connector.id)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)
        self._assert_connection_ok(connector)
        customers = connector.list_customers(seller.id)
        self.assertEqual(
            [row["external_customer_id"] for row in customers["customers"]],
            ["c1"],
        )

    def test_sqlite_get_customer_debt_zero_debt_succeeds(self):
        """Active customer with no outstanding invoices MUST return zeros."""
        path = self._write_debt_db(
            (("s1", "Ana", "549111", 1, 0.0),),
            (("c1", "s1", "Zero Debt", "20-1", "C-1", 1),),
            (("i1", "c1", "A-1", "2026-01-01", "2026-02-01", 20.0, 0.0, "paid"),),
        )
        with open(path, "rb") as handle:
            before = handle.read()
        connector = self._make_sqlite_connector(path, name="SQLite zero debt")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_debt_zero")
        result = connector.get_customer_debt(seller.id, "20-1")
        self.assertEqual(result["customer"]["external_customer_id"], "c1")
        self.assertEqual(result["invoices"], [])
        self.assertEqual(result["summary"]["total_balance"], 0.0)
        self.assertEqual(result["summary"]["invoice_count"], 0)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), before)

        empty_path = self._write_debt_db(
            (("s1", "Ana", "549111", 1, 0.0),),
            (("c2", "s1", "No Invoices", "20-2", "C-2", 1),),
            (),
        )
        empty_connector = self._make_sqlite_connector(
            empty_path, name="SQLite no invoices"
        )
        empty_seller = self._enabled_bound_seller(
            empty_connector, "s1", "sqlite_debt_empty"
        )
        empty = empty_connector.get_customer_debt(empty_seller.id, "20-2")
        self.assertEqual(empty["invoices"], [])
        self.assertEqual(empty["summary"]["open_balance"], 0.0)
        self.assertEqual(empty["summary"]["overdue_balance"], 0.0)

    def test_sqlite_get_customer_debt_rejects_inactive_and_other_seller(self):
        """Inactive and other-seller identifications MUST fail closed."""
        path = self._write_debt_db(
            (("s1", "Ana", "549111", 1, 0.0), ("s2", "Beto", "549112", 1, 0.0)),
            (
                ("c1", "s1", "Active One", "20-1", "C-1", 1),
                ("c2", "s1", "Inactive One", "20-2", "C-2", 0),
                ("c3", "s2", "Other Seller", "20-3", "C-3", 1),
            ),
            (
                ("i5", "c2", "A-5", "2026-01-01", "2026-02-01", 80.0, 80.0, "overdue"),
                ("i6", "c3", "A-6", "2026-06-01", "2026-08-01", 40.0, 40.0, "open"),
            ),
        )
        connector = self._make_sqlite_connector(path, name="SQLite debt reject")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_debt_reject")
        for identification in ("20-2", "20-3", "99-9"):
            with self.subTest(identification=identification):
                self._assert_user_error_no_leak(
                    lambda ident=identification: connector.get_customer_debt(
                        seller.id, ident
                    ),
                    path,
                )

    def test_sqlite_get_customer_debt_malformed_schema_raises_user_error(self):
        """Invalid invoices schema MUST UserError; sellers/customers still work."""
        path = self._write_source_db(
            (("s1", "Ana", "549111", 1, 0.0),),
            (("c1", "s1", "Active One", "20-1", "C-1", 1),),
        )
        connector = self._make_sqlite_connector(path, name="SQLite no invoices")
        seller = self._enabled_bound_seller(connector, "s1", "sqlite_debt_schema")
        self._assert_user_error_no_leak(
            lambda: connector.get_customer_debt(seller.id, "20-1"), path
        )
        customers = connector.list_customers(seller.id)
        self.assertEqual(
            [row["external_customer_id"] for row in customers["customers"]],
            ["c1"],
        )
        self._assert_connection_ok(connector)

        folder = tempfile.mkdtemp(prefix="col_sqlite_")
        self.addCleanup(shutil.rmtree, folder, ignore_errors=True)
        bad_path = os.path.join(folder, "bad-invoices.sqlite")
        conn = sqlite3.connect(bad_path)
        conn.execute(
            """
            CREATE TABLE sellers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                mobile TEXT,
                active INTEGER NOT NULL DEFAULT 1,
                commission_percent REAL NOT NULL DEFAULT 0
                    CHECK (commission_percent >= 0 AND commission_percent <= 100)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE customers (
                id TEXT PRIMARY KEY,
                seller_id TEXT NOT NULL,
                name TEXT NOT NULL,
                identification TEXT NOT NULL,
                customer_code TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        conn.execute(
            """
            INSERT INTO sellers (id, name, mobile, active, commission_percent)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("s1", "Ana", "549111", 1, 0.0),
        )
        conn.execute(
            """
            INSERT INTO customers (
                id, seller_id, name, identification, customer_code, active
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("c1", "s1", "Active One", "20-1", "C-1", 1),
        )
        conn.execute("CREATE TABLE invoices (id TEXT PRIMARY KEY, number TEXT)")
        conn.commit()
        conn.close()
        bad_connector = self._make_sqlite_connector(
            bad_path, name="SQLite bad invoices"
        )
        bad_seller = self._enabled_bound_seller(
            bad_connector, "s1", "sqlite_debt_bad_schema"
        )
        self._assert_user_error_no_leak(
            lambda: bad_connector.get_customer_debt(bad_seller.id, "20-1"), bad_path
        )
        self._assert_connection_ok(bad_connector)
        bad_customers = bad_connector.list_customers(bad_seller.id)
        self.assertEqual(
            [row["external_customer_id"] for row in bad_customers["customers"]],
            ["c1"],
        )

    def test_sample_sqlite_get_customer_debt_for_imported_seller(self):
        """Sample DB MUST return cust-001 outstanding invoices after Import."""
        connector = self.env.ref("collection_connector_sqlite.connector_sample_sellers")
        company = self.env.company
        company.collection_connector_id = connector
        company._sync_enabled_sellers_from_connector()
        binding = connector.seller_binding_ids.filtered(
            lambda rec: rec.external_seller_id == "seller-001"
        )
        self.assertEqual(len(binding), 1)
        with open(connector.sqlite_path, "rb") as handle:
            before = handle.read()
        result = connector.get_customer_debt(binding.user_id.id, "20-28345678-9")
        self.assertEqual(result["customer"]["external_customer_id"], "cust-001")
        self.assertEqual(result["customer"]["name"], "Martín O'Higgins")
        self.assertEqual(result["customer"]["customer_code"], "C-1001")
        self.assertEqual(
            [row["external_invoice_id"] for row in result["invoices"]],
            ["inv-003", "inv-001", "inv-004"],
        )
        self.assertEqual(result["invoices"][0]["state"], "overdue")
        self.assertEqual(result["summary"]["overdue_balance"], 45000.0)
        self.assertEqual(result["summary"]["open_balance"], 172000.0)
        self.assertEqual(result["summary"]["total_balance"], 217000.0)
        self.assertEqual(result["summary"]["invoice_count"], 3)
        zero = connector.get_customer_debt(binding.user_id.id, "30-71234567-8")
        self.assertEqual(zero["customer"]["external_customer_id"], "cust-002")
        self.assertEqual(zero["invoices"], [])
        self.assertEqual(zero["summary"]["invoice_count"], 0)
        empty = connector.get_customer_debt(binding.user_id.id, "20-33445566-7")
        self.assertEqual(empty["customer"]["external_customer_id"], "cust-004")
        self.assertEqual(empty["invoices"], [])
        self._assert_user_error_no_leak(
            lambda: connector.get_customer_debt(binding.user_id.id, "20-22334455-6"),
            connector.sqlite_path,
        )
        self._assert_user_error_no_leak(
            lambda: connector.get_customer_debt(binding.user_id.id, "20-27889900-1"),
            connector.sqlite_path,
        )
        with open(connector.sqlite_path, "rb") as handle:
            self.assertEqual(handle.read(), before)
