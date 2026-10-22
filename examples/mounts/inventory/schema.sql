CREATE TABLE products (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 0
);
INSERT INTO products (name, quantity) VALUES
    ('Widget', 40),
    ('Gadget', 3),
    ('Sprocket', 0);
