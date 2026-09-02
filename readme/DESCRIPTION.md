Read-only SQLite seller, customer, and invoice source for Collections.

Adds connector type `sqlite` with an absolute `sqlite_path`. After rejecting relative
paths and `?` `#` NUL, the addon opens `file:<path>?mode=ro` against
`sellers(id TEXT PRIMARY KEY, name TEXT NOT NULL, mobile TEXT, active INTEGER NOT NULL DEFAULT 1, commission_percent REAL NOT NULL DEFAULT 0 CHECK 0–100)`,
`customers(id TEXT PRIMARY KEY, seller_id TEXT NOT NULL, name TEXT NOT NULL, identification TEXT NOT NULL UNIQUE, customer_code TEXT NOT NULL UNIQUE, active INTEGER NOT NULL DEFAULT 1)`,
and
`invoices(id TEXT PRIMARY KEY, customer_id TEXT NOT NULL, number TEXT NOT NULL UNIQUE, issue_date TEXT NOT NULL, due_date TEXT NOT NULL, amount REAL NOT NULL, balance REAL NOT NULL, state TEXT NOT NULL)`.
Missing, unreadable, or invalid schema raises `UserError` without path or SQL. Success
does not write the file. Depends on `collection`. Admins can run Test Connection on the
connector form. Customer listing and customer debt are seller-scoped and stay in this
addon; `collection` does not import or open SQLite.

Install and upgrade materialize `data/database.sql` as `database.sqlite` under Odoo
`data_dir`, create the **SQLite Sellers** connector, assign it on the main company when
none is set, and expose the file for download on the connector form. Customer debt reads
outstanding `open`/`overdue` invoices with positive balance. Test Connection remains
sellers-only.
