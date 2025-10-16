#!/usr/bin/env python3

import os
from dotenv import load_dotenv
from pymongo import MongoClient
from passlib.hash import scrypt
from bson.objectid import ObjectId
import datetime

# Load environment variables
load_dotenv()

# Get MongoDB URI from environment variable
mongo_uri = os.getenv('MONGO_URI')

if not mongo_uri:
    print("Error: MONGO_URI environment variable not set")
    exit(1)

try:
    # Connect to MongoDB
    client = MongoClient(mongo_uri)
    
    # Extract database name from the MongoDB URI
    db_name = mongo_uri.split('/')[-1].split('?')[0]
    if not db_name:
        db_name = 'mongodbank'
    
    db = client[db_name]
    print(f"Connected to database: {db_name}")
    
    # Check if johndoe user already exists
    existing_user = db.customers.find_one({'username': 'johndoe'})
    
    if existing_user:
        print("User 'johndoe' already exists!")
        print(f"User ID: {existing_user['_id']}")
    else:
        # Create johndoe user
        hashed_password = scrypt.hash('password123')
        
        johndoe_user = {
            "username": "johndoe",
            "password": hashed_password,
            "email": "johndoe@example.com",
            "created_at": datetime.datetime.now(datetime.timezone.utc),
            "is_admin": False
        }
        
        result = db.customers.insert_one(johndoe_user)
        print(f"User 'johndoe' created successfully with ID: {result.inserted_id}")
        
        # Create accounts for johndoe
        checking_account = {
            "customer_id": result.inserted_id,
            "account_type": "Checking",
            "balance": 5000.00,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        savings_account = {
            "customer_id": result.inserted_id,
            "account_type": "Savings", 
            "balance": 10000.00,
            "created_at": datetime.datetime.now(datetime.timezone.utc)
        }
        
        account_results = db.accounts.insert_many([checking_account, savings_account])
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
        
        transaction_results = db.transactions.insert_many(transactions)
        print(f"Created {len(transaction_results.inserted_ids)} sample transactions")
    
    # Close the MongoDB connection
    client.close()
    print("Database operations completed successfully!")
    
except Exception as e:
    print(f"Error: {e}")
    exit(1)
