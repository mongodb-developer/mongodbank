import psycopg2
from psycopg2.extras import execute_values
from datetime import datetime, timedelta, timezone
import random
from decimal import Decimal, ROUND_HALF_UP
from passlib.hash import scrypt

# Database connection parameters
DB_PARAMS = {
    "dbname": "mongodbank",
    "user": "michael.lynn",
    "password": "M0ng0DB22!",
    "host": "localhost"
}

def connect_to_db():
    return psycopg2.connect(**DB_PARAMS)

def create_branches():
    branches = []
    cities = [
        ("New York", "NY", 40.7128, -74.0060),
        ("Los Angeles", "CA", 34.0522, -118.2437),
        ("Chicago", "IL", 41.8781, -87.6298),
        ("Houston", "TX", 29.7604, -95.3698),
        ("Phoenix", "AZ", 33.4484, -112.0740),
        ("Philadelphia", "PA", 39.9526, -75.1652),
        ("San Antonio", "TX", 29.4241, -98.4936),
        ("San Diego", "CA", 32.7157, -117.1611),
        ("Dallas", "TX", 32.7767, -96.7970),
        ("San Jose", "CA", 37.3382, -121.8863)
    ]
    
    for i, (city, state, lat, lon) in enumerate(cities):
        branch = (
            f"MongoDBank {city} Branch",
            f"{100+i} Main St",
            city,
            state,
            f"1000{i}",
            "USA",
            f"555-{1000+i:04d}",
            f"branch.{city.lower().replace(' ', '')}@mongodbank.com",
            f"Manager{i+1}",
            lat,
            lon
        )
        branches.append(branch)
    
    return branches

def round_to_penny(amount):
    return Decimal(amount).quantize(Decimal('.01'), ROUND_HALF_UP)

def populate_database():
    conn = connect_to_db()
    cur = conn.cursor()

    try:
        # Clear existing data
        cur.execute("TRUNCATE customers, branches, branch_services, branch_hours, accounts, transactions, fraud_flags, alerts, atms, atm_features RESTART IDENTITY CASCADE;")

        # Create branches
        branches = create_branches()
        branch_ids = []
        for branch in branches:
            cur.execute("""
                INSERT INTO branches (name, street, city, state, zip_code, country, phone_number, email, manager, latitude, longitude)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, branch)
            branch_ids.append(cur.fetchone()[0])

        # Create branch services and hours
        services = ["Loans", "Deposits", "Wealth Management"]
        hours = [("monday", "09:00", "17:00"), ("tuesday", "09:00", "17:00"), ("wednesday", "09:00", "17:00"),
                 ("thursday", "09:00", "17:00"), ("friday", "09:00", "17:00"), ("saturday", "10:00", "14:00")]
        
        for branch_id in branch_ids:
            cur.executemany("INSERT INTO branch_services (branch_id, service) VALUES (%s, %s)", 
                            [(branch_id, service) for service in services])
            cur.executemany("INSERT INTO branch_hours (branch_id, day_of_week, open_time, close_time) VALUES (%s, %s, %s, %s)", 
                            [(branch_id, day, open_time, close_time) for day, open_time, close_time in hours])

        # Create ATMs
        atm_ids = []
        for i, branch_id in enumerate(branch_ids):
            for j in range(2):  # 2 ATMs per branch
                cur.execute("""
                    INSERT INTO atms (branch_id, street, city, state, zip_code, country, latitude, longitude, type, status, accessibility)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id;
                """, (
                    branch_id,
                    f"{200+i*2+j} ATM St",
                    "ATM City",
                    "AT",
                    f"2000{i}",
                    "USA",
                    random.uniform(25, 48),
                    random.uniform(-122, -71),
                    random.choice(["Walk-up", "Drive-through"]),
                    "Operational",
                    random.choice([True, False])
                ))
                atm_ids.append(cur.fetchone()[0])

        # Create ATM features
        features = ["Cash Withdrawal", "Deposit", "Check Cashing"]
        for atm_id in atm_ids:
            cur.executemany("INSERT INTO atm_features (atm_id, feature) VALUES (%s, %s)",
                            [(atm_id, feature) for feature in features])

        # Create johndoe user
        cur.execute("""
            INSERT INTO customers (username, password, email, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
        """, ('johndoe', scrypt.hash('password123'), 'johndoe@example.com', datetime.now(timezone.utc)))
        johndoe_id = cur.fetchone()[0]

        # Create accounts for johndoe
        cur.execute("""
            INSERT INTO accounts (customer_id, branch_id, account_type, balance, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (johndoe_id, random.choice(branch_ids), 'Checking', 5000.00, datetime.now(timezone.utc)))
        checking_id = cur.fetchone()[0]

        cur.execute("""
            INSERT INTO accounts (customer_id, branch_id, account_type, balance, created_at)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id;
        """, (johndoe_id, random.choice(branch_ids), 'Savings', 10000.00, datetime.now(timezone.utc)))
        savings_id = cur.fetchone()[0]

        # Generate sample transactions
        current_date = datetime.now(timezone.utc) - timedelta(days=30)
        account_balances = {checking_id: Decimal('5000.00'), savings_id: Decimal('10000.00')}

        for _ in range(100):  # Generate 100 transactions over the last 30 days
            transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
            amount = round_to_penny(random.uniform(10, 1000))
            
            from_account = random.choice([checking_id, savings_id])
            to_account = checking_id if from_account == savings_id else savings_id

            # Ensure withdrawal and transfers don't result in negative balance
            if transaction_type in ['withdrawal', 'transfer']:
                max_amount = account_balances[from_account]
                amount = min(amount, max_amount)

            cur.execute("""
                INSERT INTO transactions (account_id, type, amount, timestamp, from_account_id, to_account_id)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id;
            """, (from_account if transaction_type != 'transfer' else None, 
                  transaction_type, 
                  float(amount), 
                  current_date, 
                  from_account if transaction_type in ['withdrawal', 'transfer'] else None,
                  to_account if transaction_type == 'transfer' else None))
            
            transaction_id = cur.fetchone()[0]

            if transaction_type == 'transfer':
                account_balances[from_account] -= amount
                account_balances[to_account] += amount
            elif transaction_type == 'deposit':
                account_balances[from_account] += amount
            else:  # withdrawal
                account_balances[from_account] -= amount

            # Randomly add fraud flags
            if random.random() < 0.1:  # 10% chance of fraud flag
                fraud_type = random.choice(['velocity', 'location'])
                cur.execute("INSERT INTO fraud_flags (transaction_id, flag) VALUES (%s, %s)", 
                            (transaction_id, fraud_type))
                
                # Create an alert for this transaction
                cur.execute("""
                    INSERT INTO alerts (customer_id, account_id, transaction_id, type, message, timestamp, resolved)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (johndoe_id, 
                      from_account if transaction_type != 'transfer' else None,
                      transaction_id,
                      'Potential Fraud',
                      f"Suspicious activity detected: {fraud_type}",
                      current_date,
                      False))

            current_date += timedelta(minutes=random.randint(30, 720))  # 0.5 to 12 hours between transactions

        # Update final account balances
        cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (float(account_balances[checking_id]), checking_id))
        cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (float(account_balances[savings_id]), savings_id))

        conn.commit()
        print("Data population completed successfully.")

    except Exception as e:
        conn.rollback()
        print(f"An error occurred: {e}")

    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    populate_database()