CREATE TABLE IF NOT EXISTS public.categories
(
    id integer NOT NULL DEFAULT nextval('categories_id_seq'::regclass),
    name character varying(50) COLLATE pg_catalog."default" NOT NULL,
    CONSTRAINT categories_pkey PRIMARY KEY (id)
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.categories
    OWNER to postgres;


CREATE TABLE IF NOT EXISTS public.expenses
(
    id integer NOT NULL DEFAULT nextval('expenses_id_seq'::regclass),
    description character varying(255) COLLATE pg_catalog."default" NOT NULL,
    amount numeric NOT NULL,
    date date DEFAULT CURRENT_DATE,
    category_id integer NOT NULL,
    user_id integer NOT NULL,
    CONSTRAINT expenses_pkey PRIMARY KEY (id),
    CONSTRAINT expenses_category_id_fkey FOREIGN KEY (category_id)
        REFERENCES public.categories (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE,
    CONSTRAINT expenses_user_id_fkey FOREIGN KEY (user_id)
        REFERENCES public.users (id) MATCH SIMPLE
        ON UPDATE NO ACTION
        ON DELETE CASCADE
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.expenses
    OWNER to postgres;


CREATE TABLE IF NOT EXISTS public.users
(
    id integer NOT NULL DEFAULT nextval('users_id_seq'::regclass),
    username character varying(100) COLLATE pg_catalog."default" NOT NULL,
    password text COLLATE pg_catalog."default" NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    balance numeric DEFAULT 0,
    last_payday date,
    CONSTRAINT users_pkey PRIMARY KEY (id),
    CONSTRAINT users_username_key UNIQUE (username)
)

TABLESPACE pg_default;

CREATE TABLE IF NOT EXISTS public.tba_sio
(
    key character varying(100) COLLATE pg_catalog."default" NOT NULL,
    value numeric(10,2) NOT NULL
)

TABLESPACE pg_default;

ALTER TABLE IF EXISTS public.tba_sio
    OWNER to postgres;

-- Populate categories safely
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


INSERT INTO public.expenses (id, description, amount, date, category_id, user_id) VALUES
(1, 'September Rent', 1200, '2025-09-01', 1, 80),           -- Rent / Mortgage
(2, 'Electricity Bill', 150, '2025-09-05', 2, 80),          -- Utilities
(3, 'Grocery Shopping', 300, '2025-09-10', 3, 80),          -- Groceries
(4, 'Dinner at Restaurant', 75, '2025-09-12', 4, 80),       -- Dining Out
(5, 'Gas for Car', 60, '2025-09-15', 5, 80),                -- Transportation
(6, 'Car Service', 200, '2025-09-18', 6, 80),               -- Car Maintenance
(7, 'Doctor Visit', 100, '2025-09-20', 7, 80),              -- Health / Medical
(8, 'Car Insurance', 250, '2025-09-21', 8, 80),             -- Insurance
(9, 'Movie Night', 50, '2025-09-21', 9, 80),                -- Entertainment
(10, 'New Clothes', 120, '2025-09-22', 10, 80),             -- Clothing / Apparel
(11, 'Online Course', 80, '2025-09-23', 11, 80),            -- Education / Courses
(12, 'Birthday Gift', 60, '2025-09-24', 12, 80),            -- Gifts / Donations
(13, 'Haircut', 30, '2025-09-24', 13, 80),                  -- Personal Care
(14, 'Weekend Trip', 400, '2025-09-25', 14, 80),            -- Travel / Vacation
(15, 'Internet Bill', 50, '2025-09-26', 15, 80),            -- Internet / Phone
(16, 'Netflix Subscription', 15, '2025-09-26', 16, 80),     -- Subscriptions
(17, 'Cleaning Supplies', 45, '2025-09-27', 17, 80),        -- Household Supplies
(18, 'Kids Toys', 60, '2025-09-28', 18, 80),                -- Childcare / Kids
(19, 'Monthly Savings', 300, '2025-09-29', 19, 80),         -- Savings / Investments
(20, 'Miscellaneous Purchase', 40, '2025-09-30', 20, 80)    -- Miscellaneous
ON CONFLICT (id) DO NOTHING;


