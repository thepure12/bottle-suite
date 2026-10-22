CREATE TABLE invoices (
    id INTEGER PRIMARY KEY,
    customer TEXT NOT NULL,
    amount REAL NOT NULL,
    paid INTEGER NOT NULL DEFAULT 0
);
INSERT INTO invoices (customer, amount, paid) VALUES
    ('Acme', 1200.00, 1),
    ('Acme', 300.00, 0),
    ('Globex', 950.50, 0);
