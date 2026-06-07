CREATE DATABASE IF NOT EXISTS marketing_db;
USE marketing_db;

SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS campaign_responses;
DROP TABLE IF EXISTS customer_engagement;
DROP TABLE IF EXISTS customer_spending;
DROP TABLE IF EXISTS customers;
SET FOREIGN_KEY_CHECKS = 1;

CREATE TABLE customers (
    customer_id INT PRIMARY KEY,
    year_birth INT NOT NULL,
    age INT GENERATED ALWAYS AS (2024 - year_birth) STORED,
    education ENUM('Basic', '2n Cycle', 'Graduation', 'Master', 'PhD') NOT NULL,
    marital_status ENUM(
        'Single', 'Together', 'Married', 'Divorced', 'Widow', 'Alone', 'Absurd', 'YOLO'
    ) NOT NULL,
    marital_clean VARCHAR(20) GENERATED ALWAYS AS (
        CASE
            WHEN marital_status IN ('Alone', 'Absurd', 'YOLO') THEN 'Single'
            WHEN marital_status = 'Together' THEN 'Married'
            ELSE marital_status
        END
    ) STORED,
    income DECIMAL(12, 2) NOT NULL,
    kidhome INT NOT NULL DEFAULT 0,
    teenhome INT NOT NULL DEFAULT 0,
    total_children INT GENERATED ALWAYS AS (kidhome + teenhome) STORED,
    dt_customer DATE NOT NULL,
    complain TINYINT(1) NOT NULL DEFAULT 0,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK (year_birth BETWEEN 1890 AND 2024),
    CHECK (income >= 0),
    CHECK (kidhome >= 0),
    CHECK (teenhome >= 0),
    CHECK (complain IN (0, 1))
);

CREATE TABLE customer_spending (
    spending_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    mnt_wines INT NOT NULL DEFAULT 0,
    mnt_fruits INT NOT NULL DEFAULT 0,
    mnt_meat_products INT NOT NULL DEFAULT 0,
    mnt_fish_products INT NOT NULL DEFAULT 0,
    mnt_sweet_products INT NOT NULL DEFAULT 0,
    mnt_gold_prods INT NOT NULL DEFAULT 0,
    total_spend INT GENERATED ALWAYS AS (
        mnt_wines + mnt_fruits + mnt_meat_products +
        mnt_fish_products + mnt_sweet_products + mnt_gold_prods
    ) STORED,
    num_deals_purchases INT NOT NULL DEFAULT 0,
    num_web_purchases INT NOT NULL DEFAULT 0,
    num_catalog_purchases INT NOT NULL DEFAULT 0,
    num_store_purchases INT NOT NULL DEFAULT 0,
    total_purchases INT GENERATED ALWAYS AS (
        num_deals_purchases + num_web_purchases +
        num_catalog_purchases + num_store_purchases
    ) STORED,
    CONSTRAINT uq_customer_spending_customer UNIQUE (customer_id),
    CONSTRAINT fk_customer_spending_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (mnt_wines >= 0),
    CHECK (mnt_fruits >= 0),
    CHECK (mnt_meat_products >= 0),
    CHECK (mnt_fish_products >= 0),
    CHECK (mnt_sweet_products >= 0),
    CHECK (mnt_gold_prods >= 0),
    CHECK (num_deals_purchases >= 0),
    CHECK (num_web_purchases >= 0),
    CHECK (num_catalog_purchases >= 0),
    CHECK (num_store_purchases >= 0)
);

CREATE TABLE customer_engagement (
    engagement_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    recency INT NOT NULL COMMENT 'Days since last purchase',
    num_web_visits_month INT NOT NULL DEFAULT 0,
    CONSTRAINT uq_customer_engagement_customer UNIQUE (customer_id),
    CONSTRAINT fk_customer_engagement_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (recency >= 0),
    CHECK (num_web_visits_month >= 0)
);

CREATE TABLE campaign_responses (
    response_id INT AUTO_INCREMENT PRIMARY KEY,
    customer_id INT NOT NULL,
    campaign_1 TINYINT(1) NOT NULL DEFAULT 0,
    campaign_2 TINYINT(1) NOT NULL DEFAULT 0,
    campaign_3 TINYINT(1) NOT NULL DEFAULT 0,
    campaign_4 TINYINT(1) NOT NULL DEFAULT 0,
    campaign_5 TINYINT(1) NOT NULL DEFAULT 0,
    response TINYINT(1) NOT NULL DEFAULT 0 COMMENT 'Accepted last campaign',
    total_campaigns_accepted INT GENERATED ALWAYS AS (
        campaign_1 + campaign_2 + campaign_3 + campaign_4 + campaign_5
    ) STORED,
    z_cost_contact INT NOT NULL DEFAULT 3,
    z_revenue INT NOT NULL DEFAULT 11,
    revenue_generated INT GENERATED ALWAYS AS (response * z_revenue) STORED,
    cost_incurred INT GENERATED ALWAYS AS (z_cost_contact) STORED,
    net_value INT GENERATED ALWAYS AS ((response * z_revenue) - z_cost_contact) STORED,
    CONSTRAINT uq_campaign_responses_customer UNIQUE (customer_id),
    CONSTRAINT fk_campaign_responses_customer
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    CHECK (campaign_1 IN (0, 1)),
    CHECK (campaign_2 IN (0, 1)),
    CHECK (campaign_3 IN (0, 1)),
    CHECK (campaign_4 IN (0, 1)),
    CHECK (campaign_5 IN (0, 1)),
    CHECK (response IN (0, 1)),
    CHECK (z_cost_contact >= 0),
    CHECK (z_revenue >= 0)
);

CREATE INDEX idx_customers_education ON customers(education);
CREATE INDEX idx_customers_marital_clean ON customers(marital_clean);
CREATE INDEX idx_customers_income ON customers(income);
CREATE INDEX idx_customer_engagement_recency ON customer_engagement(recency);
CREATE INDEX idx_campaign_responses_response ON campaign_responses(response);
