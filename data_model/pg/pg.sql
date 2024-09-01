-- Create customers table
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    username VARCHAR(50) UNIQUE NOT NULL,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_admin BOOLEAN DEFAULT FALSE
);

-- Create branches table
CREATE TABLE branches (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    street VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50) NOT NULL,
    zip_code VARCHAR(20) NOT NULL,
    country VARCHAR(50) NOT NULL,
    phone_number VARCHAR(20),
    email VARCHAR(100),
    manager VARCHAR(100),
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL
);

-- Create branch_services table
CREATE TABLE branch_services (
    branch_id INTEGER REFERENCES branches(id),
    service VARCHAR(100) NOT NULL,
    PRIMARY KEY (branch_id, service)
);

-- Create branch_hours table
CREATE TABLE branch_hours (
    branch_id INTEGER REFERENCES branches(id),
    day_of_week VARCHAR(10) NOT NULL,
    open_time TIME,
    close_time TIME,
    PRIMARY KEY (branch_id, day_of_week)
);

-- Create accounts table
CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    branch_id INTEGER REFERENCES branches(id),
    account_type VARCHAR(50) NOT NULL,
    balance DECIMAL(12, 2) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create transactions table
CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    account_id INTEGER REFERENCES accounts(id),
    type VARCHAR(50) NOT NULL,
    amount DECIMAL(12, 2) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    from_account_id INTEGER REFERENCES accounts(id),
    to_account_id INTEGER REFERENCES accounts(id),
    location_latitude DECIMAL(10, 8),
    location_longitude DECIMAL(11, 8)
);

-- Create fraud_flags table
CREATE TABLE fraud_flags (
    transaction_id INTEGER REFERENCES transactions(id),
    flag VARCHAR(50) NOT NULL,
    PRIMARY KEY (transaction_id, flag)
);

-- Create alerts table
CREATE TABLE alerts (
    id SERIAL PRIMARY KEY,
    customer_id INTEGER REFERENCES customers(id),
    account_id INTEGER REFERENCES accounts(id),
    transaction_id INTEGER REFERENCES transactions(id),
    type VARCHAR(50) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    resolved BOOLEAN DEFAULT FALSE
);

-- Create atms table
CREATE TABLE atms (
    id SERIAL PRIMARY KEY,
    branch_id INTEGER REFERENCES branches(id),
    street VARCHAR(255) NOT NULL,
    city VARCHAR(100) NOT NULL,
    state VARCHAR(50) NOT NULL,
    zip_code VARCHAR(20) NOT NULL,
    country VARCHAR(50) NOT NULL,
    latitude DECIMAL(10, 8) NOT NULL,
    longitude DECIMAL(11, 8) NOT NULL,
    type VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL,
    accessibility BOOLEAN NOT NULL
);

-- Create atm_features table
CREATE TABLE atm_features (
    atm_id INTEGER REFERENCES atms(id),
    feature VARCHAR(100) NOT NULL,
    PRIMARY KEY (atm_id, feature)
);