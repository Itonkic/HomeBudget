-- =========================
-- Users table first
-- =========================
CREATE TABLE IF NOT EXISTS public.users
(
    id SERIAL PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    balance NUMERIC DEFAULT 0,
    last_payday DATE,
    salary numeric(10,2)
);

-- =========================
-- Categories table
-- =========================
CREATE TABLE IF NOT EXISTS public.categories
(
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL
);

-- =========================
-- Expenses table (after users & categories)
-- =========================
CREATE TABLE IF NOT EXISTS public.expenses
(
    id SERIAL PRIMARY KEY,
    description VARCHAR(255) NOT NULL,
    amount NUMERIC NOT NULL,
    date DATE DEFAULT CURRENT_DATE,
    category_id INTEGER NOT NULL REFERENCES public.categories(id) ON DELETE CASCADE,
    user_id INTEGER NOT NULL REFERENCES public.users(id) ON DELETE CASCADE
);

-- =========================
-- TBA_SIO table
-- =========================
CREATE TABLE IF NOT EXISTS public.tba_sio
(
    key VARCHAR(100) NOT NULL UNIQUE,
    value NUMERIC(10,2) NOT NULL
);

-- =========================
-- Populate sample categories
-- =========================
INSERT INTO public.categories (id, name) VALUES
(1, 'Rent / Mortgage'),
(2, 'Utilities'),
(3, 'Groceries'),
(4, 'Dining Out'),
(5, 'Transportation'),
(6, 'Car Maintenance'),
(7, 'Health / Medical'),
(8, 'Insurance'),
(9, 'Entertainment'),
(10, 'Clothing / Apparel'),
(11, 'Education / Courses'),
(12, 'Gifts / Donations'),
(13, 'Personal Care'),
(14, 'Travel / Vacation'),
(15, 'Internet / Phone'),
(16, 'Subscriptions'),
(17, 'Household Supplies'),
(18, 'Childcare / Kids'),
(19, 'Savings / Investments'),
(20, 'Miscellaneous')
ON CONFLICT (id) DO NOTHING;




-- =========================
-- Populate default Reference table
-- =========================
INSERT INTO TBA_SIO (key, value) VALUES
('Rent', 600.00)
ON CONFLICT (key) DO NOTHING;