#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv
from pymongo import MongoClient
from passlib.hash import scrypt
from bson.objectid import ObjectId
import datetime
import random

# Load environment variables
load_dotenv()

def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    mongo_uri = os.getenv('MONGO_URI')
    if not mongo_uri:
        raise ValueError("MONGO_URI environment variable not set")
    
    client = MongoClient(mongo_uri)
    # Test the connection
    client.admin.command('ping')
    
    # Extract database name from URI
    db_name = mongo_uri.split('/')[-1].split('?')[0]
    if not db_name:
        db_name = 'ai4t'
    
    return client, db_name

def create_demo_users():
    """Create realistic demo users with different profiles"""
    users = [
        {
            "username": "johndoe",
            "password": scrypt.hash('password123'),
            "email": "john.doe@email.com",
            "full_name": "John Doe",
            "profile": "Business Owner",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": False
        },
        {
            "username": "sarahsmith",
            "password": scrypt.hash('password123'),
            "email": "sarah.smith@email.com",
            "full_name": "Sarah Smith",
            "profile": "Software Engineer",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": False
        },
        {
            "username": "mikejohnson",
            "password": scrypt.hash('password123'),
            "email": "mike.johnson@email.com",
            "full_name": "Mike Johnson",
            "profile": "Retiree",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": False
        },
        {
            "username": "admin",
            "password": scrypt.hash('mongodb123'),
            "email": "admin@mongodbank.com",
            "full_name": "Bank Administrator",
            "profile": "Bank Manager",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": True
        }
    ]
    return users

def create_realistic_accounts(user_id, profile):
    """Create accounts based on user profile"""
    accounts = []
    
    if profile == "Business Owner":
        # Business owner has checking, savings, and business account
        accounts = [
            {
                "customer_id": user_id,
                "account_type": "Business Checking",
                "account_number": f"BC{random.randint(100000, 999999)}",
                "balance": round(random.uniform(15000, 50000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=365)
            },
            {
                "customer_id": user_id,
                "account_type": "Business Savings",
                "account_number": f"BS{random.randint(100000, 999999)}",
                "balance": round(random.uniform(50000, 150000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=300)
            },
            {
                "customer_id": user_id,
                "account_type": "Personal Checking",
                "account_number": f"PC{random.randint(100000, 999999)}",
                "balance": round(random.uniform(5000, 15000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=200)
            }
        ]
    elif profile == "Software Engineer":
        # Software engineer has checking, savings, and investment
        accounts = [
            {
                "customer_id": user_id,
                "account_type": "Checking",
                "account_number": f"CH{random.randint(100000, 999999)}",
                "balance": round(random.uniform(8000, 25000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=400)
            },
            {
                "customer_id": user_id,
                "account_type": "Savings",
                "account_number": f"SV{random.randint(100000, 999999)}",
                "balance": round(random.uniform(20000, 80000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=350)
            },
            {
                "customer_id": user_id,
                "account_type": "Investment",
                "account_number": f"IN{random.randint(100000, 999999)}",
                "balance": round(random.uniform(30000, 120000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=300)
            }
        ]
    elif profile == "Retiree":
        # Retiree has checking, savings, and retirement account
        accounts = [
            {
                "customer_id": user_id,
                "account_type": "Checking",
                "account_number": f"CH{random.randint(100000, 999999)}",
                "balance": round(random.uniform(3000, 12000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=500)
            },
            {
                "customer_id": user_id,
                "account_type": "Savings",
                "account_number": f"SV{random.randint(100000, 999999)}",
                "balance": round(random.uniform(50000, 200000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=450)
            },
            {
                "customer_id": user_id,
                "account_type": "Retirement",
                "account_number": f"RT{random.randint(100000, 999999)}",
                "balance": round(random.uniform(200000, 800000), 2),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=400)
            }
        ]
    else:  # Admin or default
        accounts = [
            {
                "customer_id": user_id,
                "account_type": "Admin Account",
                "account_number": f"AD{random.randint(100000, 999999)}",
                "balance": 0.00,
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            }
        ]
    
    return accounts

def generate_realistic_transactions(account_id, profile, account_type, start_balance, days_back=90):
    """Generate realistic transactions based on user profile and account type"""
    transactions = []
    current_balance = start_balance
    current_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days_back)
    
    # Transaction patterns based on profile and account type
    if profile == "Business Owner":
        if account_type == "Business Checking":
            # High volume, large amounts
            transaction_count = random.randint(80, 150)
            amount_range = (100, 5000)
            common_merchants = ["Office Depot", "Staples", "Amazon Business", "FedEx", "UPS", "Square", "PayPal", "QuickBooks", "Business Insurance", "Software License", "Marketing Agency", "Legal Services", "Accounting Firm", "Bank Fees", "Wire Transfer"]
        elif account_type == "Business Savings":
            # Occasional large deposits/withdrawals
            transaction_count = random.randint(10, 25)
            amount_range = (1000, 25000)
            common_merchants = ["Business Transfer", "Investment", "Loan Payment", "Tax Payment", "CD Maturity", "Interest Payment", "Equipment Purchase", "Real Estate Investment"]
        else:  # Personal Checking
            transaction_count = random.randint(40, 80)
            amount_range = (50, 2000)
            common_merchants = ["Grocery Store", "Gas Station", "Restaurant", "Online Shopping", "ATM Withdrawal", "Mortgage Payment", "Car Payment", "Insurance Payment", "Utilities", "Phone Bill"]
    
    elif profile == "Software Engineer":
        if account_type == "Checking":
            # Regular salary deposits, tech purchases
            transaction_count = random.randint(60, 100)
            amount_range = (25, 3000)
            common_merchants = ["Salary Deposit", "Amazon", "Best Buy", "Apple Store", "Starbucks", "Uber", "Netflix", "Spotify", "GitHub Pro", "Adobe Creative", "Microsoft Office", "Google Cloud", "AWS", "Rent Payment", "Student Loan", "401k Contribution"]
        elif account_type == "Savings":
            # Regular transfers from checking
            transaction_count = random.randint(20, 40)
            amount_range = (500, 5000)
            common_merchants = ["Transfer from Checking", "Interest Payment", "Tax Refund", "Emergency Fund", "Vacation Savings", "Home Down Payment"]
        else:  # Investment
            transaction_count = random.randint(15, 30)
            amount_range = (1000, 10000)
            common_merchants = ["Investment Transfer", "Dividend Payment", "Stock Purchase", "Bond Purchase", "ETF Investment", "Mutual Fund", "Roth IRA Contribution", "401k Rollover"]
    
    elif profile == "Retiree":
        if account_type == "Checking":
            # Social security, pension, regular expenses
            transaction_count = random.randint(30, 60)
            amount_range = (20, 500)
            common_merchants = ["Social Security", "Pension Payment", "Pharmacy", "Grocery Store", "Doctor", "Utilities", "Medicare Premium", "Prescription Drugs", "Hair Salon", "Dentist", "Optometrist", "Hearing Aid", "Physical Therapy", "Home Maintenance", "Garden Center"]
        elif account_type == "Savings":
            # Occasional transfers
            transaction_count = random.randint(10, 20)
            amount_range = (200, 2000)
            common_merchants = ["Transfer from Checking", "Interest Payment", "CD Maturity", "Emergency Fund", "Travel Savings", "Gift Money", "Charitable Donation"]
        else:  # Retirement
            transaction_count = random.randint(5, 15)
            amount_range = (2000, 15000)
            common_merchants = ["Required Distribution", "Investment Transfer", "Dividend Reinvestment", "RMD Withdrawal", "Annuity Payment", "Bond Maturity", "Mutual Fund Distribution"]
    
    else:  # Admin - minimal transactions
        transaction_count = random.randint(5, 15)
        amount_range = (0, 100)
        common_merchants = ["System Transaction", "Admin Transfer"]
    
    # Generate transactions
    for i in range(transaction_count):
        # Determine transaction type based on account and profile
        if account_type in ["Savings", "Investment", "Retirement"]:
            transaction_types = ["deposit", "transfer_in", "interest"]
        else:
            transaction_types = ["deposit", "withdrawal", "transfer_in", "transfer_out", "purchase"]
        
        # Add some realistic patterns
        transaction_type = None
        amount = None
        
        if profile == "Software Engineer" and account_type == "Checking":
            # Bi-weekly salary deposits
            if i % 14 == 0 and random.random() < 0.8:
                transaction_type = "deposit"
                amount = round(random.uniform(3000, 8000), 2)  # Salary range
            # Monthly recurring payments
            elif i % 30 == 0 and random.random() < 0.6:
                transaction_type = "withdrawal"
                amount = round(random.uniform(100, 500), 2)  # Recurring bills
        elif profile == "Retiree" and account_type == "Checking":
            # Monthly social security/pension
            if i % 30 == 0 and random.random() < 0.9:
                transaction_type = "deposit"
                amount = round(random.uniform(1200, 3000), 2)  # Social security range
        elif profile == "Business Owner" and account_type == "Business Checking":
            # Weekly client payments
            if i % 7 == 0 and random.random() < 0.7:
                transaction_type = "deposit"
                amount = round(random.uniform(1000, 5000), 2)  # Client payment range
        
        if transaction_type is None or transaction_type not in transaction_types:
            transaction_type = random.choice(transaction_types)
        
        # Generate realistic amounts
        if amount is None:
            if transaction_type == "deposit":
                amount = round(random.uniform(amount_range[0], amount_range[1]), 2)
                current_balance += amount
            elif transaction_type == "withdrawal":
                amount = round(random.uniform(amount_range[0], min(amount_range[1], current_balance * 0.8)), 2)
                current_balance -= amount
            elif transaction_type in ["transfer_in", "interest"]:
                amount = round(random.uniform(amount_range[0], amount_range[1]), 2)
                current_balance += amount
            elif transaction_type in ["transfer_out", "purchase"]:
                amount = round(random.uniform(amount_range[0], min(amount_range[1], current_balance * 0.9)), 2)
                current_balance -= amount
        else:
            # Amount was already set by pattern matching
            if transaction_type in ["deposit", "transfer_in", "interest"]:
                current_balance += amount
            else:
                current_balance -= amount
        
        # Ensure balance doesn't go negative
        if current_balance < 0:
            current_balance = 0
        
        # Generate merchant/description
        if transaction_type == "deposit":
            if profile == "Business Owner" and account_type == "Business Checking":
                merchant = random.choice(["Client Payment", "Invoice Payment", "Direct Deposit", "Wire Transfer", "Check Deposit", "Cash Deposit"])
            elif profile == "Software Engineer":
                merchant = random.choice(["Salary Deposit", "Bonus Payment", "Freelance Payment", "Stock Option Exercise", "Tax Refund"])
            elif profile == "Retiree":
                merchant = random.choice(["Social Security", "Pension Payment", "Medicare Reimbursement", "Tax Refund", "CD Maturity"])
            else:
                merchant = random.choice(["Direct Deposit", "Transfer from External", "Cash Deposit", "Check Deposit"])
        elif transaction_type == "interest":
            merchant = "Interest Payment"
        elif transaction_type in ["transfer_in", "transfer_out"]:
            merchant = "Account Transfer"
        else:
            merchant = random.choice(common_merchants)
        
        transaction = {
            "account_id": account_id,
            "type": transaction_type,
            "amount": amount,
            "description": f"{merchant} - {transaction_type.title()}",
            "merchant": merchant,
            "timestamp": current_date,
            "balance_after": round(current_balance, 2)
        }
        
        transactions.append(transaction)
        
        # Move to next transaction time
        if profile == "Business Owner":
            # More frequent transactions
            current_date += datetime.timedelta(hours=random.randint(2, 48))
        elif profile == "Software Engineer":
            # Regular pattern
            current_date += datetime.timedelta(hours=random.randint(6, 72))
        elif profile == "Retiree":
            # Less frequent
            current_date += datetime.timedelta(hours=random.randint(12, 120))
        else:
            current_date += datetime.timedelta(hours=random.randint(24, 168))
    
    return transactions, current_balance

def main():
    """Main function to populate MongoDB with demo users and realistic data"""
    try:
        client, db_name = connect_to_mongodb()
        db = client[db_name]
        
        print(f"Connected to MongoDB Atlas database: {db_name}")
        
        # Clear existing data
        print("Clearing existing data...")
        collections_to_clear = ['customers', 'accounts', 'transactions', 'fraud_flags', 'alerts']
        for collection_name in collections_to_clear:
            db[collection_name].delete_many({})
            print(f"Cleared {collection_name} collection")
        
        # Create demo users
        print("Creating demo users...")
        users = create_demo_users()
        user_results = db.customers.insert_many(users)
        user_ids = user_results.inserted_ids
        print(f"Created {len(user_ids)} demo users")
        
        # Create accounts and transactions for each user
        all_transactions = []
        account_updates = []
        
        for i, user in enumerate(users):
            user_id = user_ids[i]
            profile = user['profile']
            username = user['username']
            
            print(f"\nCreating accounts for {username} ({profile})...")
            accounts = create_realistic_accounts(user_id, profile)
            account_results = db.accounts.insert_many(accounts)
            account_ids = account_results.inserted_ids
            
            print(f"Created {len(account_ids)} accounts for {username}")
            
            # Generate transactions for each account
            for j, account in enumerate(accounts):
                account_id = account_ids[j]
                account_type = account['account_type']
                start_balance = account['balance']
                
                print(f"  Generating transactions for {account_type}...")
                transactions, final_balance = generate_realistic_transactions(
                    account_id, profile, account_type, start_balance
                )
                
                all_transactions.extend(transactions)
                account_updates.append({
                    "account_id": account_id,
                    "final_balance": final_balance
                })
                
                print(f"    Generated {len(transactions)} transactions, final balance: ${final_balance:.2f}")
        
        # Insert all transactions
        print(f"\nInserting {len(all_transactions)} transactions...")
        if all_transactions:
            transaction_results = db.transactions.insert_many(all_transactions)
            print(f"Created {len(transaction_results.inserted_ids)} transactions")
        
        # Update account balances
        print("Updating account balances...")
        for update in account_updates:
            db.accounts.update_one(
                {"_id": update["account_id"]}, 
                {"$set": {"balance": update["final_balance"]}}
            )
        
        # Create some fraud flags for demonstration
        print("Creating fraud flags...")
        fraud_flags = []
        for i in range(random.randint(5, 15)):
            fraud_flag = {
                "transaction_id": random.choice(transaction_results.inserted_ids) if all_transactions else None,
                "flag_type": random.choice(["velocity", "location", "amount", "pattern"]),
                "description": f"Fraud flag {i+1} - {random.choice(['Unusual spending pattern', 'High velocity transaction', 'Suspicious location', 'Large amount alert'])}",
                "severity": random.choice(["low", "medium", "high"]),
                "status": random.choice(["active", "investigating", "resolved"]),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(1, 30))
            }
            fraud_flags.append(fraud_flag)
        
        if fraud_flags:
            db.fraud_flags.insert_many(fraud_flags)
            print(f"Created {len(fraud_flags)} fraud flags")
        
        # Create some alerts
        print("Creating alerts...")
        alerts = []
        for i in range(random.randint(3, 8)):
            alert = {
                "type": random.choice(["transaction", "balance", "security", "maintenance"]),
                "title": f"Alert {i+1}",
                "message": f"Important notification: {random.choice(['Account balance low', 'New transaction detected', 'Security update required', 'Scheduled maintenance'])}",
                "priority": random.choice(["low", "medium", "high"]),
                "is_read": random.choice([True, False]),
                "created_at": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=random.randint(1, 7))
            }
            alerts.append(alert)
        
        if alerts:
            db.alerts.insert_many(alerts)
            print(f"Created {len(alerts)} alerts")
        
        print(f"\n✅ Demo data creation completed!")
        print(f"📊 Summary:")
        print(f"   - {len(user_ids)} demo users")
        print(f"   - {sum(len(create_realistic_accounts(user_ids[i], users[i]['profile'])) for i in range(len(users)))} accounts")
        print(f"   - {len(all_transactions)} transactions")
        print(f"   - {len(fraud_flags)} fraud flags")
        print(f"   - {len(alerts)} alerts")
        print(f"\n🔐 Demo Login Credentials:")
        for user in users:
            print(f"   - {user['username']} / password123 ({user['profile']})")
        print(f"   - admin / mongodb123 (Bank Manager)")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
    finally:
        if 'client' in locals():
            client.close()

if __name__ == "__main__":
    main()
