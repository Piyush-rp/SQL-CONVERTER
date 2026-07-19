-- Sample rows for the demo schema (schema.sql). Edit/extend this file to
-- customize what scripts/seed_demo_data.py generates - it's plain SQL, no
-- code changes needed to add more customers/products/orders.

INSERT INTO customers (id, name, country, signed_up_at) VALUES
    (1, 'Acme Corp', 'US', '2024-01-15'),
    (2, 'Globex', 'UK', '2024-02-03'),
    (3, 'Initech', 'US', '2024-03-22'),
    (4, 'Umbrella Ltd', 'DE', '2024-04-10'),
    (5, 'Soylent Inc', 'CA', '2024-05-30');

INSERT INTO products (id, name, category, price) VALUES
    (1, 'Widget Pro', 'Hardware', 49.99),
    (2, 'Widget Lite', 'Hardware', 19.99),
    (3, 'Analytics Suite', 'Software', 199.00),
    (4, 'Support Plan', 'Services', 99.00);

INSERT INTO orders (id, customer_id, product_id, quantity, ordered_at) VALUES
    (1, 1, 1, 3, '2024-06-01'),
    (2, 1, 3, 1, '2024-06-15'),
    (3, 2, 2, 5, '2024-06-20'),
    (4, 3, 4, 1, '2024-07-02'),
    (5, 4, 1, 2, '2024-07-10'),
    (6, 5, 3, 1, '2024-07-18'),
    (7, 2, 4, 1, '2024-08-01'),
    (8, 1, 2, 10, '2024-08-05');
