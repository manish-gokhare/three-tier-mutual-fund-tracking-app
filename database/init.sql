-- This script is executed by the official PostgreSQL image only when its
-- data directory is first created. Remove the postgres_data volume to rerun it.

CREATE TABLE IF NOT EXISTS users (
    id BIGSERIAL PRIMARY KEY,
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS mutual_funds (
    id BIGSERIAL PRIMARY KEY,
    fund_name VARCHAR(200) NOT NULL,
    category VARCHAR(20) NOT NULL CHECK (category IN ('Small Cap', 'Mid Cap', 'Large Cap', 'Multi Cap', 'Flexi Cap')),
    ticker_symbol VARCHAR(20) NOT NULL UNIQUE,
    amfi_scheme_code VARCHAR(20) UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS fund_nav (
    id BIGSERIAL PRIMARY KEY,
    fund_id BIGINT NOT NULL REFERENCES mutual_funds(id) ON DELETE CASCADE,
    nav_date DATE NOT NULL,
    nav NUMERIC(12, 4) NOT NULL CHECK (nav > 0),
    nav_source VARCHAR(20) NOT NULL DEFAULT 'seed' CHECK (nav_source IN ('seed', 'amfi')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_fund_nav_date UNIQUE (fund_id, nav_date)
);

CREATE TABLE IF NOT EXISTS nav_sync_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    matched_funds INTEGER NOT NULL DEFAULT 0,
    fetched_records INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

-- These keep existing Docker volumes compatible when the application is upgraded.
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);
ALTER TABLE mutual_funds ADD COLUMN IF NOT EXISTS amfi_scheme_code VARCHAR(20);
ALTER TABLE fund_nav ADD COLUMN IF NOT EXISTS nav_source VARCHAR(20) NOT NULL DEFAULT 'seed';
CREATE UNIQUE INDEX IF NOT EXISTS uq_mutual_funds_amfi_scheme_code
    ON mutual_funds (amfi_scheme_code) WHERE amfi_scheme_code IS NOT NULL;

CREATE TABLE IF NOT EXISTS user_holdings (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fund_id BIGINT NOT NULL REFERENCES mutual_funds(id) ON DELETE CASCADE,
    units NUMERIC(16, 4) NOT NULL CHECK (units > 0),
    average_purchase_nav NUMERIC(12, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_user_fund_holding UNIQUE (user_id, fund_id)
);

CREATE INDEX IF NOT EXISTS idx_fund_nav_fund_date ON fund_nav (fund_id, nav_date DESC);
CREATE INDEX IF NOT EXISTS idx_user_holdings_user ON user_holdings (user_id);

INSERT INTO users (full_name, email, password_hash)
VALUES ('Demo Investor', 'demo@mftracker.local', 'pbkdf2_sha256$600000$Swm2_mffPgtNNnZAkpMVNQ==$v6xRO-FaApTjvJnGMdAbEDNwY3t-Z-IIqfq0ndMJn8E=')
ON CONFLICT (email) DO NOTHING;

UPDATE users
SET password_hash = 'pbkdf2_sha256$600000$Swm2_mffPgtNNnZAkpMVNQ==$v6xRO-FaApTjvJnGMdAbEDNwY3t-Z-IIqfq0ndMJn8E='
WHERE email = 'demo@mftracker.local' AND password_hash IS NULL;

INSERT INTO mutual_funds (fund_name, category, ticker_symbol) VALUES
    ('Axis Bluechip Fund', 'Large Cap', 'AXISBLUE'),
    ('HDFC Top 100 Fund', 'Large Cap', 'HDFCTOP100'),
    ('ICICI Prudential Bluechip Fund', 'Large Cap', 'ICICIBLUE'),
    ('SBI Bluechip Fund', 'Large Cap', 'SBIBLUE'),
    ('Kotak Bluechip Fund', 'Large Cap', 'KOTAKBLUE'),
    ('Nippon India Large Cap Fund', 'Large Cap', 'NIPLARGECAP'),
    ('Canara Robeco Bluechip Equity Fund', 'Large Cap', 'CRBLUECHIP'),
    ('Mirae Asset Large Cap Fund', 'Large Cap', 'MIRAELARGE'),
    ('Bandhan Large Cap Fund', 'Large Cap', 'BANDLARGE'),
    ('UTI Large Cap Fund', 'Large Cap', 'UTILARGECAP'),
    ('HDFC Mid-Cap Opportunities Fund', 'Mid Cap', 'HDFCMIDCAP'),
    ('Kotak Emerging Equity Fund', 'Mid Cap', 'KOTAKEMERG'),
    ('PGIM India Midcap Opportunities Fund', 'Mid Cap', 'PGIMMIDCAP'),
    ('Motilal Oswal Midcap Fund', 'Mid Cap', 'MOMIDCAP'),
    ('Edelweiss Mid Cap Fund', 'Mid Cap', 'EDELMIDCAP'),
    ('Axis Midcap Fund', 'Mid Cap', 'AXISMIDCAP'),
    ('SBI Magnum Midcap Fund', 'Mid Cap', 'SBIMIDCAP'),
    ('Tata Mid Cap Growth Fund', 'Mid Cap', 'TATAMIDCAP'),
    ('Quant Mid Cap Fund', 'Mid Cap', 'QUANTMIDCAP'),
    ('Nippon India Growth Fund', 'Mid Cap', 'NIPGROWTH'),
    ('Nippon India Small Cap Fund', 'Small Cap', 'NIPSMALLCAP'),
    ('SBI Small Cap Fund', 'Small Cap', 'SBISMALLCAP'),
    ('HDFC Small Cap Fund', 'Small Cap', 'HDFCSMALL'),
    ('Kotak Small Cap Fund', 'Small Cap', 'KOTAKSMALL'),
    ('Axis Small Cap Fund', 'Small Cap', 'AXISSMALL'),
    ('Tata Small Cap Fund', 'Small Cap', 'TATASMALL'),
    ('Quant Small Cap Fund', 'Small Cap', 'QUANTSMALL'),
    ('Canara Robeco Small Cap Fund', 'Small Cap', 'CRSMALLCAP'),
    ('Bank of India Small Cap Fund', 'Small Cap', 'BOISMALLCAP'),
    ('HSBC Small Cap Fund', 'Small Cap', 'HSBCSMALL'),
    ('Parag Parikh Flexi Cap Fund', 'Flexi Cap', 'PPFASFLEXI'),
    ('HDFC Flexi Cap Fund', 'Flexi Cap', 'HDFCFLEXI'),
    ('UTI Flexi Cap Fund', 'Flexi Cap', 'UTIFLEXI'),
    ('Franklin India Flexi Cap Fund', 'Flexi Cap', 'FRANKFLEXI'),
    ('Kotak Flexicap Fund', 'Flexi Cap', 'KOTAKFLEXI'),
    ('Aditya Birla Sun Life Flexi Cap Fund', 'Flexi Cap', 'ABSLFLEXI'),
    ('JM Flexicap Fund', 'Flexi Cap', 'JMFLEXICAP'),
    ('PGIM India Flexi Cap Fund', 'Flexi Cap', 'PGIMFLEXI'),
    ('DSP Flexi Cap Fund', 'Flexi Cap', 'DSPFLEXI'),
    ('Union Flexi Cap Fund', 'Flexi Cap', 'UNIONFLEXI'),
    ('Nippon India Multi Cap Fund', 'Multi Cap', 'NIPMULTICAP'),
    ('Kotak Multicap Fund', 'Multi Cap', 'KOTAKMULTI'),
    ('Mahindra Manulife Multi Cap Fund', 'Multi Cap', 'MMMULTICAP'),
    ('Sundaram Multi Cap Fund', 'Multi Cap', 'SUNDARMULTI'),
    ('ICICI Prudential Multicap Fund', 'Multi Cap', 'ICICIMULTI'),
    ('HDFC Multi Cap Fund', 'Multi Cap', 'HDFCMULTI'),
    ('Baroda BNP Paribas Multi Cap Fund', 'Multi Cap', 'BNPMULTICAP'),
    ('Invesco India Multicap Fund', 'Multi Cap', 'INVESCOMULT'),
    ('Tata Multicap Fund', 'Multi Cap', 'TATAMULTI'),
    ('Quant Active Fund', 'Flexi Cap', 'QUANTACTIVE')
ON CONFLICT (ticker_symbol) DO UPDATE
SET fund_name = EXCLUDED.fund_name, category = EXCLUDED.category;

-- Deterministic sample daily NAVs for the most recent 60 days. In production,
-- replace this seed with a scheduled NAV ingestion job from your market-data source.
INSERT INTO fund_nav (fund_id, nav_date, nav, nav_source)
SELECT
    mf.id,
    CURRENT_DATE - offset_days,
    ROUND((80 + mf.id * 7.13 + SIN((mf.id + offset_days) / 4.0) * 3.25)::NUMERIC, 4),
    'seed'
FROM mutual_funds AS mf
CROSS JOIN generate_series(0, 59) AS offset_days
ON CONFLICT (fund_id, nav_date) DO NOTHING;
