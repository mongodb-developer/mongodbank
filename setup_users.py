#!/usr/bin/env python3

import os
import sys
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import the Flask app and its components
from app import app, mongo, db
from passlib.hash import scrypt
import datetime

def setup_users():
    """Create admin and johndoe users"""
    
    with app.app_context():
        try:
            # Create admin user if it doesn't exist
            admin_user = mongo.db.customers.find_one({'username': 'admin', 'is_admin': True})
            
            if not admin_user:
                admin_hashed_password = scrypt.hash('mongodb123')
                admin_user_doc = {
                    "username": "admin",
                    "password": admin_hashed_password,
                    "is_admin": True,
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                admin_result = mongo.db.customers.insert_one(admin_user_doc)
                print(f"Admin user created with ID: {admin_result.inserted_id}")
            else:
                print("Admin user already exists")
            
            # Create johndoe user if it doesn't exist
            johndoe_user = mongo.db.customers.find_one({'username': 'johndoe'})
            
            if not johndoe_user:
                johndoe_hashed_password = scrypt.hash('password123')
                johndoe_user_doc = {
                    "username": "johndoe",
                    "password": johndoe_hashed_password,
                    "email": "johndoe@example.com",
                    "created_at": datetime.datetime.now(datetime.timezone.utc),
                    "is_admin": False
                }
                johndoe_result = mongo.db.customers.insert_one(johndoe_user_doc)
                print(f"Johndoe user created with ID: {johndoe_result.inserted_id}")
                
                # Create accounts for johndoe
                checking_account = {
                    "customer_id": johndoe_result.inserted_id,
                    "account_type": "Checking",
                    "balance": 5000.00,
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                
                savings_account = {
                    "customer_id": johndoe_result.inserted_id,
                    "account_type": "Savings", 
                    "balance": 10000.00,
                    "created_at": datetime.datetime.now(datetime.timezone.utc)
                }
                
                account_results = mongo.db.accounts.insert_many([checking_account, savings_account])
                print(f"Created {len(account_results.inserted_ids)} accounts for johndoe")
                
                # Create some sample transactions
                transactions = [
                    {
                        "account_id": account_results.inserted_ids[0],  # Checking account
                        "amount": 500.00,
                        "type": "deposit",
                        "description": "Initial deposit",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=7)
                    },
                    {
                        "account_id": account_results.inserted_ids[1],  # Savings account
                        "amount": 1000.00,
                        "type": "deposit", 
                        "description": "Initial deposit",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=5)
                    }
                ]
                
                transaction_results = mongo.db.transactions.insert_many(transactions)
                print(f"Created {len(transaction_results.inserted_ids)} sample transactions")
                
            else:
                print("Johndoe user already exists")
                
            print("User setup completed successfully!")
            
        except Exception as e:
            print(f"Error setting up users: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    setup_users()
