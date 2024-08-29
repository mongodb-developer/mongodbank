from pymongo import MongoClient
from passlib.hash import scrypt
from bson.objectid import ObjectId
from config import Config
from urllib.parse import urlparse

# Initialize Config
config = Config()

# Parse the MongoDB URI
parsed_uri = urlparse(config.MONGO_URI)

# Extract the database name
db_name = parsed_uri.path.lstrip('/')

# Remove any query parameters from the database name
db_name = db_name.split('?')[0]

# Connect to MongoDB using the URI from Config
client = MongoClient(config.MONGO_URI)

# Use the extracted database name
db = client[db_name]

print(f"Connected to database: {db_name}")

# Clear existing data
db.customers.delete_many({})
db.accounts.delete_many({})
db.transactions.delete_many({})

# Create a sample customer
customer = {
    'username': 'johndoe',
    'password': scrypt.hash('password123')
}
customer_id = db.customers.insert_one(customer).inserted_id

# ... rest of your init_db.py code ...

print("Sample data initialized successfully!")

# Create sample accounts
accounts = [
    {
        'customer_id': customer_id,
        'account_type': 'Checking',
        'balance': 1000.00
    },
    {
        'customer_id': customer_id,
        'account_type': 'Savings',
        'balance': 5000.00
    }
]
account_ids = db.accounts.insert_many(accounts).inserted_ids

# Create sample transactions
transactions = [
    {
        'account_id': account_ids[0],
        'amount': 500.00,
        'type': 'deposit',
        'timestamp': '2023-01-01T12:00:00'
    },
    {
        'account_id': account_ids[1],
        'amount': 1000.00,
        'type': 'deposit',
        'timestamp': '2023-01-02T14:30:00'
    }
]
db.transactions.insert_many(transactions)

print("Sample data initialized successfully!")