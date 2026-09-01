-- Sample SQLite source for collection_connector_sqlite.
-- Install/upgrade materializes this script as database.sqlite under Odoo data_dir
-- and points the SQLite Sellers connector at that file.
--
-- Today for due-date fixtures: 2026-08-26.
-- paid: balance = 0. open/overdue: balance > 0 (partial: 0 < balance < amount).
-- open due in the future (or today). overdue due in the past.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS sellers (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    mobile TEXT,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    id TEXT PRIMARY KEY,
    seller_id TEXT NOT NULL REFERENCES sellers(id),
    name TEXT NOT NULL,
    identification TEXT NOT NULL UNIQUE,
    customer_code TEXT NOT NULL UNIQUE,
    active INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0, 1))
);

CREATE TABLE IF NOT EXISTS invoices (
    id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(id),
    number TEXT NOT NULL UNIQUE,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount > 0),
    balance REAL NOT NULL CHECK (balance >= 0 AND balance <= amount),
    state TEXT NOT NULL CHECK (state IN ('open', 'paid', 'overdue'))
);

CREATE INDEX IF NOT EXISTS idx_customers_seller_id ON customers(seller_id);
CREATE INDEX IF NOT EXISTS idx_invoices_customer_id ON invoices(customer_id);

INSERT INTO sellers (id, name, mobile, active) VALUES
    ('seller-001', 'Ana Pérez', '5491155510001', 1),
    ('seller-002', 'Bruno Gómez', '5491155510002', 1),
    ('seller-003', 'Carla Díaz', '5491155510003', 1),
    ('seller-004', 'Diego Fernández', '5491155510004', 1),
    ('seller-005', 'Elena Ruiz', '5491166677788', 1),
    ('seller-006', 'Facundo López', NULL, 0);

-- ---------------------------------------------------------------------------
-- seller-001 Ana Pérez (6 customers). CUIT mix 20-/30-. Apostrophe + Ñ names.
-- ---------------------------------------------------------------------------

-- mix portfolio: open / paid / overdue; apostrophe name
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-001', 'seller-001', 'Martín O''Higgins', '20-28345678-9', 'C-1001', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-001', 'cust-001', 'A-0001-00001001', '2026-06-01', '2026-09-15', 150000.0, 150000.0, 'open'),
    ('inv-002', 'cust-001', 'A-0001-00001002', '2026-04-10', '2026-06-10', 80000.0, 0.0, 'paid'),
    ('inv-003', 'cust-001', 'A-0001-00001003', '2026-03-01', '2026-05-01', 45000.0, 45000.0, 'overdue'),
    ('inv-004', 'cust-001', 'A-0001-00001004', '2026-07-01', '2026-10-01', 22000.0, 22000.0, 'open');

-- nothing to collect: only paid
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-002', 'seller-001', 'Distribuidora Sur S.A.', '30-71234567-8', 'C-1002', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-005', 'cust-002', 'A-0001-00001005', '2026-01-15', '2026-02-15', 220000.0, 0.0, 'paid'),
    ('inv-006', 'cust-002', 'A-0001-00001006', '2026-03-20', '2026-04-20', 110000.0, 0.0, 'paid');

-- hot collect: only overdue; Ñ name
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-003', 'seller-001', 'Lucía Peñaloza', '20-30111222-3', 'C-1003', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-007', 'cust-003', 'A-0001-00001007', '2026-02-01', '2026-04-01', 67500.0, 67500.0, 'overdue'),
    ('inv-008', 'cust-003', 'A-0001-00001008', '2026-05-10', '2026-07-10', 32000.0, 32000.0, 'overdue');

-- new account: active, zero invoices
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-004', 'seller-001', 'Nuevo Cliente Ana', '20-33445566-7', 'C-1004', 1);

-- partial: 0 < balance < amount, still open
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-005', 'seller-001', 'Comercial Andina S.R.L.', '30-69887766-5', 'C-1005', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-009', 'cust-005', 'A-0001-00001009', '2026-07-01', '2026-09-01', 100000.0, 40000.0, 'open'),
    ('inv-010', 'cust-005', 'A-0001-00001010', '2026-05-01', '2026-06-01', 15000.0, 0.0, 'paid');

-- inactive, clean: active=0, only paid; name collision Pérez
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-006', 'seller-001', 'Baja Limpia Pérez', '20-22334455-6', 'C-1006', 0);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-011', 'cust-006', 'A-0001-00001011', '2025-11-01', '2025-12-01', 18000.0, 0.0, 'paid');

-- ---------------------------------------------------------------------------
-- seller-002 Bruno Gómez (6 customers). Name collision Gómez. Due today.
-- ---------------------------------------------------------------------------

-- mix portfolio
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-007', 'seller-002', 'Sofía Álvarez', '20-27889900-1', 'C-1007', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-012', 'cust-007', 'A-0001-00002001', '2026-06-15', '2026-10-15', 95000.0, 95000.0, 'open'),
    ('inv-013', 'cust-007', 'A-0001-00002002', '2026-02-01', '2026-03-01', 41000.0, 0.0, 'paid'),
    ('inv-014', 'cust-007', 'A-0001-00002003', '2026-01-10', '2026-03-10', 28000.0, 28000.0, 'overdue');

-- nothing to collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-008', 'seller-002', 'Transportes Norte S.A.', '30-55667788-9', 'C-1008', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-015', 'cust-008', 'A-0001-00002004', '2026-04-01', '2026-05-01', 75000.0, 0.0, 'paid'),
    ('inv-016', 'cust-008', 'A-0001-00002005', '2026-06-01', '2026-07-01', 43000.0, 0.0, 'paid');

-- hot collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-009', 'seller-002', 'Pablo Herrera', '20-31222333-4', 'C-1009', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-017', 'cust-009', 'A-0001-00002006', '2026-03-15', '2026-05-15', 54000.0, 54000.0, 'overdue'),
    ('inv-018', 'cust-009', 'A-0001-00002007', '2026-04-20', '2026-06-20', 19000.0, 19000.0, 'overdue');

-- new account
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-010', 'seller-002', 'Cuenta Nueva Bruno', '20-34556677-8', 'C-1010', 1);

-- partial + due today (2026-08-26), still open
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-011', 'seller-002', 'Gómez Hnos. Logística', '30-60112233-4', 'C-1011', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-019', 'cust-011', 'A-0001-00002008', '2026-07-26', '2026-08-26', 88000.0, 33000.0, 'open');

-- inactive, still owes
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-012', 'seller-002', 'Baja Con Deuda', '20-25667788-9', 'C-1012', 0);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-020', 'cust-012', 'A-0001-00002009', '2026-01-05', '2026-03-05', 62000.0, 62000.0, 'overdue'),
    ('inv-021', 'cust-012', 'A-0001-00002010', '2025-12-01', '2026-01-15', 12000.0, 0.0, 'paid');

-- ---------------------------------------------------------------------------
-- seller-003 Carla Díaz (6 customers). Same issue_date pair, due yesterday,
-- same-day invoice, tiny amount.
-- ---------------------------------------------------------------------------

-- mix + two invoices, same issue_date
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-013', 'seller-003', 'Roberto Castillo', '20-26778899-0', 'C-1013', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-022', 'cust-013', 'A-0001-00003001', '2026-06-10', '2026-09-10', 120000.0, 120000.0, 'open'),
    ('inv-023', 'cust-013', 'A-0001-00003002', '2026-06-10', '2026-08-10', 45000.0, 0.0, 'paid'),
    ('inv-024', 'cust-013', 'A-0001-00003003', '2026-02-01', '2026-04-01', 33000.0, 33000.0, 'overdue'),
    ('inv-025', 'cust-013', 'A-0001-00003004', '2026-07-01', '2026-10-01', 18000.0, 18000.0, 'open');

-- nothing to collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-014', 'seller-003', 'Servicios Pampeanos S.A.', '30-77889900-1', 'C-1014', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-026', 'cust-014', 'A-0001-00003005', '2026-05-01', '2026-06-01', 210000.0, 0.0, 'paid'),
    ('inv-027', 'cust-014', 'A-0001-00003006', '2026-06-01', '2026-07-01', 90000.0, 0.0, 'paid');

-- hot collect + due yesterday (2026-08-25)
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-015', 'seller-003', 'Valentina Moreno', '20-32334455-6', 'C-1015', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-028', 'cust-015', 'A-0001-00003007', '2026-07-25', '2026-08-25', 41000.0, 41000.0, 'overdue'),
    ('inv-029', 'cust-015', 'A-0001-00003008', '2026-04-01', '2026-06-01', 15500.0, 15500.0, 'overdue');

-- new account
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-016', 'seller-003', 'Alta Reciente Carla', '20-35667788-9', 'C-1016', 1);

-- partial + same-day invoice (issue_date = due_date)
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-017', 'seller-003', 'Molinos del Litoral S.R.L.', '30-64556677-8', 'C-1017', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-030', 'cust-017', 'A-0001-00003009', '2026-08-01', '2026-08-01', 77000.0, 25000.0, 'open'),
    ('inv-031', 'cust-017', 'A-0001-00003010', '2026-06-15', '2026-07-15', 9000.0, 0.0, 'paid');

-- tiny unpaid
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-018', 'seller-003', 'Microcargo Express', '20-28990011-2', 'C-1018', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-032', 'cust-018', 'A-0001-00003011', '2026-08-10', '2026-09-10', 1.0, 1.0, 'open');

-- ---------------------------------------------------------------------------
-- seller-004 Diego Fernández (10 customers, extra volume). Huge, high volume,
-- ancient overdue, long legal name, duplicate trade name.
-- ---------------------------------------------------------------------------

-- mix portfolio
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-019', 'seller-004', 'Javier Medina', '20-29001122-3', 'C-1019', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-033', 'cust-019', 'A-0001-00004001', '2026-05-20', '2026-09-20', 135000.0, 135000.0, 'open'),
    ('inv-034', 'cust-019', 'A-0001-00004002', '2026-03-01', '2026-04-01', 56000.0, 0.0, 'paid'),
    ('inv-035', 'cust-019', 'A-0001-00004003', '2026-01-15', '2026-03-15', 24000.0, 24000.0, 'overdue');

-- nothing to collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-020', 'seller-004', 'Frigorífico Atlántico S.A.', '30-80991122-3', 'C-1020', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-036', 'cust-020', 'A-0001-00004004', '2026-02-01', '2026-03-01', 310000.0, 0.0, 'paid'),
    ('inv-037', 'cust-020', 'A-0001-00004005', '2026-04-01', '2026-05-01', 185000.0, 0.0, 'paid');

-- hot collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-021', 'seller-004', 'Camila Vargas', '20-33446677-8', 'C-1021', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-038', 'cust-021', 'A-0001-00004006', '2026-02-10', '2026-04-10', 71000.0, 71000.0, 'overdue'),
    ('inv-039', 'cust-021', 'A-0001-00004007', '2026-03-22', '2026-05-22', 26500.0, 26500.0, 'overdue'),
    ('inv-040', 'cust-021', 'A-0001-00004008', '2026-05-01', '2026-07-01', 14800.0, 14800.0, 'overdue');

-- new account
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-022', 'seller-004', 'Prospecto Diego', '20-36778899-0', 'C-1022', 1);

-- partial overdue leftover
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-023', 'seller-004', 'Química Austral S.A.', '30-66778899-0', 'C-1023', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-041', 'cust-023', 'A-0001-00004009', '2026-03-01', '2026-05-01', 200000.0, 75000.0, 'overdue'),
    ('inv-042', 'cust-023', 'A-0001-00004010', '2026-06-01', '2026-09-01', 48000.0, 48000.0, 'open');

-- huge: millions of ARS, mixed paid / overdue / partial
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-024', 'seller-004', 'Energía del Plata S.A.', '30-71239876-5', 'C-1024', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-043', 'cust-024', 'A-0001-00004011', '2026-01-10', '2026-02-10', 5000000.0, 0.0, 'paid'),
    ('inv-044', 'cust-024', 'A-0001-00004012', '2025-11-01', '2026-01-01', 3500000.0, 3500000.0, 'overdue'),
    ('inv-045', 'cust-024', 'A-0001-00004013', '2026-06-01', '2026-10-01', 1200000.0, 400000.0, 'open');

-- high volume: 10 invoices
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-025', 'seller-004', 'Mayorista Cuyo S.A.', '30-82334455-6', 'C-1025', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-046', 'cust-025', 'A-0001-00004014', '2026-01-05', '2026-02-05', 12000.0, 0.0, 'paid'),
    ('inv-047', 'cust-025', 'A-0001-00004015', '2026-02-05', '2026-03-05', 15000.0, 0.0, 'paid'),
    ('inv-048', 'cust-025', 'A-0001-00004016', '2026-03-05', '2026-04-05', 18000.0, 0.0, 'paid'),
    ('inv-049', 'cust-025', 'A-0001-00004017', '2026-04-05', '2026-05-05', 21000.0, 21000.0, 'overdue'),
    ('inv-050', 'cust-025', 'A-0001-00004018', '2026-05-05', '2026-06-05', 24000.0, 24000.0, 'overdue'),
    ('inv-051', 'cust-025', 'A-0001-00004019', '2026-06-05', '2026-07-05', 27000.0, 9000.0, 'overdue'),
    ('inv-052', 'cust-025', 'A-0001-00004020', '2026-07-05', '2026-09-05', 30000.0, 30000.0, 'open'),
    ('inv-053', 'cust-025', 'A-0001-00004021', '2026-07-20', '2026-09-20', 33000.0, 33000.0, 'open'),
    ('inv-054', 'cust-025', 'A-0001-00004022', '2026-08-01', '2026-10-01', 36000.0, 36000.0, 'open'),
    ('inv-055', 'cust-025', 'A-0001-00004023', '2026-08-10', '2026-10-10', 39000.0, 0.0, 'paid');

-- ancient overdue: due_date in 2024, large balance
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-026', 'seller-004', 'Deuda Antigua S.R.L.', '30-53445566-7', 'C-1026', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-056', 'cust-026', 'A-0001-00004024', '2024-02-15', '2024-03-15', 890000.0, 890000.0, 'overdue');

-- same trade name, seller-004 (pair with cust-034)
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-027', 'seller-004', 'Almacén El Sol', '30-55660011-2', 'C-1027', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-057', 'cust-027', 'A-0001-00004025', '2026-05-15', '2026-09-15', 64000.0, 64000.0, 'open'),
    ('inv-058', 'cust-027', 'A-0001-00004026', '2026-02-01', '2026-04-01', 21000.0, 0.0, 'paid');

-- long legal name
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    (
        'cust-028',
        'seller-004',
        'Sociedad Anónima Importadora y Exportadora de Productos Agropecuarios del Litoral Argentino S.R.L.',
        '30-90112233-4',
        'C-1028',
        1
    );
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-059', 'cust-028', 'A-0001-00004027', '2026-04-12', '2026-09-12', 175000.0, 175000.0, 'open'),
    ('inv-060', 'cust-028', 'A-0001-00004028', '2026-01-20', '2026-03-20', 88000.0, 0.0, 'paid'),
    ('inv-061', 'cust-028', 'A-0001-00004029', '2025-12-01', '2026-02-01', 46000.0, 46000.0, 'overdue');

-- ---------------------------------------------------------------------------
-- seller-005 Elena Ruiz (6 customers). Duplicate trade name pair.
-- ---------------------------------------------------------------------------

-- mix portfolio
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-029', 'seller-005', 'Natalia Romero', '20-24556677-8', 'C-1029', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-062', 'cust-029', 'A-0001-00005001', '2026-06-20', '2026-09-20', 82000.0, 82000.0, 'open'),
    ('inv-063', 'cust-029', 'A-0001-00005002', '2026-03-10', '2026-04-10', 37000.0, 0.0, 'paid'),
    ('inv-064', 'cust-029', 'A-0001-00005003', '2026-01-08', '2026-03-08', 19500.0, 19500.0, 'overdue');

-- nothing to collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-030', 'seller-005', 'Cooperativa Agropecuaria del Valle S.A.', '30-84556677-8', 'C-1030', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-065', 'cust-030', 'A-0001-00005004', '2026-02-14', '2026-03-14', 142000.0, 0.0, 'paid'),
    ('inv-066', 'cust-030', 'A-0001-00005005', '2026-05-14', '2026-06-14', 68000.0, 0.0, 'paid');

-- hot collect
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-031', 'seller-005', 'Esteban Quiroga', '20-37889900-1', 'C-1031', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-067', 'cust-031', 'A-0001-00005006', '2026-03-03', '2026-05-03', 52000.0, 52000.0, 'overdue'),
    ('inv-068', 'cust-031', 'A-0001-00005007', '2026-04-18', '2026-06-18', 17400.0, 17400.0, 'overdue');

-- new account
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-032', 'seller-005', 'Cuenta Nueva Elena', '20-38990011-2', 'C-1032', 1);

-- partial
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-033', 'seller-005', 'Textil Paraná S.A.', '30-68990011-2', 'C-1033', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-069', 'cust-033', 'A-0001-00005008', '2026-07-10', '2026-09-10', 91000.0, 27000.0, 'open'),
    ('inv-070', 'cust-033', 'A-0001-00005009', '2026-04-10', '2026-05-10', 13000.0, 0.0, 'paid');

-- same trade name, seller-005 (pair with cust-027)
INSERT INTO customers (id, seller_id, name, identification, customer_code, active) VALUES
    ('cust-034', 'seller-005', 'Almacén El Sol', '30-66770022-3', 'C-1034', 1);
INSERT INTO invoices (id, customer_id, number, issue_date, due_date, amount, balance, state) VALUES
    ('inv-071', 'cust-034', 'A-0001-00005010', '2026-06-01', '2026-09-01', 45000.0, 45000.0, 'open'),
    ('inv-072', 'cust-034', 'A-0001-00005011', '2026-01-12', '2026-03-12', 28000.0, 28000.0, 'overdue');
