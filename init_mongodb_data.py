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

def create_branches():
    """Create sample branches"""
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
        branch = {
            "name": f"MongoDBank {city} Branch",
            "street": f"{100+i} Main St",
            "city": city,
            "state": state,
            "zip_code": f"1000{i}",
            "country": "USA",
            "phone_number": f"555-{1000+i:04d}",
            "email": f"branch.{city.lower().replace(' ', '')}@mongodbank.com",
            "manager": f"Manager{i+1}",
            "latitude": lat,
            "longitude": lon,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        branches.append(branch)
    
    return branches

def create_atms(branch_ids):
    """Create ATMs for branches"""
    atms = []
    for i, branch_id in enumerate(branch_ids):
        for j in range(2):  # 2 ATMs per branch
            atm = {
                "branch_id": branch_id,
                "street": f"{200+i*2+j} ATM St",
                "city": "ATM City",
                "state": "AT",
                "zip_code": f"2000{i}",
                "country": "USA",
                "latitude": random.uniform(25, 48),
                "longitude": random.uniform(-122, -71),
                "type": random.choice(["Walk-up", "Drive-through"]),
                "status": "Operational",
                "accessibility": random.choice([True, False]),
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            }
            atms.append(atm)
    return atms

def populate_mongodb():
    """Populate MongoDB with sample data"""
    try:
        client, db_name = connect_to_mongodb()
        db = client[db_name]
        
        print(f"Connected to MongoDB Atlas database: {db_name}")
        
        # Clear existing data
        print("Clearing existing data...")
        collections_to_clear = ['customers', 'branches', 'accounts', 'transactions', 'atms', 'fraud_flags', 'alerts']
        for collection_name in collections_to_clear:
            db[collection_name].delete_many({})
            print(f"Cleared {collection_name} collection")
        
        # Create branches
        print("Creating branches...")
        branches = create_branches()
        branch_results = db.branches.insert_many(branches)
        branch_ids = branch_results.inserted_ids
        print(f"Created {len(branch_ids)} branches")
        
        # Create ATMs
        print("Creating ATMs...")
        atms = create_atms(branch_ids)
        atm_results = db.atms.insert_many(atms)
        atm_ids = atm_results.inserted_ids
        print(f"Created {len(atm_ids)} ATMs")
        
        # Create admin user
        print("Creating admin user...")
        admin_hashed_password = scrypt.hash('mongodb123')
        admin_user = {
            "username": "admin",
            "password": admin_hashed_password,
            "is_admin": True,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        admin_result = db.customers.insert_one(admin_user)
        print(f"Admin user created with ID: {admin_result.inserted_id}")
        
        # Create johndoe user
        print("Creating johndoe user...")
        johndoe_hashed_password = scrypt.hash('password123')
        johndoe_user = {
            "username": "johndoe",
            "password": johndoe_hashed_password,
            "email": "johndoe@example.com",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": False
        }
        johndoe_result = db.customers.insert_one(johndoe_user)
        johndoe_id = johndoe_result.inserted_id
        print(f"Johndoe user created with ID: {johndoe_id}")
        
        # Create accounts for johndoe
        print("Creating accounts for johndoe...")
        checking_account = {
            "customer_id": johndoe_id,
            "branch_id": random.choice(branch_ids),
            "account_type": "Checking",
            "balance": 5000.00,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        savings_account = {
            "customer_id": johndoe_id,
            "branch_id": random.choice(branch_ids),
            "account_type": "Savings", 
            "balance": 10000.00,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        account_results = db.accounts.insert_many([checking_account, savings_account])
        account_ids = account_results.inserted_ids
        print(f"Created {len(account_ids)} accounts for johndoe")
        
        # Create sample transactions
        print("Creating sample transactions...")
        transactions = []
        current_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
        account_balances = {account_ids[0]: 5000.00, account_ids[1]: 10000.00}
        
        for i in range(50):  # Generate 50 transactions over the last 30 days
            transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
            amount = round(random.uniform(10, 1000), 2)
            
            from_account = random.choice(account_ids)
            to_account = account_ids[1] if from_account == account_ids[0] else account_ids[0]
            
            # Ensure withdrawal and transfers don't result in negative balance
            if transaction_type in ['withdrawal', 'transfer']:
                max_amount = account_balances[from_account]
                amount = min(amount, max_amount)
            
            transaction = {
                "account_id": from_account,
                "type": transaction_type,
                "amount": amount,
                "timestamp": current_date,
                "description": f"Sample {transaction_type} transaction",
                "created_at": datetime.datetime.now(datetime.timezone.utc)
            }
            
            if transaction_type == 'transfer':
                transaction["to_account_id"] = to_account
                account_balances[from_account] -= amount
                account_balances[to_account] += amount
            elif transaction_type == 'deposit':
                account_balances[from_account] += amount
            else:  # withdrawal
                account_balances[from_account] -= amount
            
            transactions.append(transaction)
            
            # Randomly add fraud flags
            if random.random() < 0.1:  # 10% chance of fraud flag
                fraud_flag = {
                    "transaction_id": None,  # Will be updated after transaction is inserted
                    "flag": random.choice(['velocity', 'location']),
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                transactions.append(('fraud_flag', fraud_flag))
            
            current_date += datetime.timedelta(minutes=random.randint(30, 720))  # 0.5 to 12 hours between transactions
        
        # Insert transactions
        transaction_docs = [t for t in transactions if not isinstance(t, tuple)]
        transaction_results = db.transactions.insert_many(transaction_docs)
        transaction_ids = transaction_results.inserted_ids
        print(f"Created {len(transaction_ids)} transactions")
        
        # Update account balances
        print("Updating account balances...")
        db.accounts.update_one({"_id": account_ids[0]}, {"$set": {"balance": account_balances[account_ids[0]]}})
        db.accounts.update_one({"_id": account_ids[1]}, {"$set": {"balance": account_balances[account_ids[1]]}})
        
        # Create some fraud flags and alerts
        print("Creating fraud flags and alerts...")
        fraud_flags = []
        alerts = []
        
        for i, transaction_id in enumerate(transaction_ids):
            if random.random() < 0.1:  # 10% chance of fraud flag
                fraud_flag = {
                    "transaction_id": transaction_id,
                    "flag": random.choice(['velocity', 'location']),
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                fraud_flags.append(fraud_flag)
                
                # Create an alert for this transaction
                alert = {
                    "customer_id": johndoe_id,
                    "account_id": transaction_docs[i]["account_id"],
                    "transaction_id": transaction_id,
                    "type": "Potential Fraud",
                    "message": f"Suspicious activity detected: {fraud_flag['flag']}",
                    "timestamp": transaction_docs[i]["timestamp"],
                    "resolved": False,
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                alerts.append(alert)
        
        if fraud_flags:
            db.fraud_flags.insert_many(fraud_flags)
            print(f"Created {len(fraud_flags)} fraud flags")
        
        if alerts:
            db.alerts.insert_many(alerts)
            print(f"Created {len(alerts)} alerts")
        
        print("\n✅ MongoDB data population completed successfully!")
        print(f"📊 Summary:")
        print(f"   - {len(branch_ids)} branches")
        print(f"   - {len(atm_ids)} ATMs")
        print(f"   - 2 customers (admin, johndoe)")
        print(f"   - 2 accounts for johndoe")
        print(f"   - {len(transaction_ids)} transactions")
        print(f"   - {len(fraud_flags)} fraud flags")
        print(f"   - {len(alerts)} alerts")
        print(f"\n🔐 Login credentials:")
        print(f"   - Admin: admin / mongodb123")
        print(f"   - User: johndoe / password123")
        
        client.close()
        
    except Exception as e:
        print(f"❌ Error populating MongoDB: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting MongoDB data population...")
    success = populate_mongodb()
    if success:
        print("\n🎉 Data population completed successfully!")
        print("You can now start the Flask app and test the authentication.")
    else:
        print("\n💥 Data population failed. Please check the error messages above.")
