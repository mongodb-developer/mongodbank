import os
from dotenv import load_dotenv
from passlib.hash import scrypt
from pymongo import MongoClient
from bson.objectid import ObjectId
import datetime

# Load environment variables from .env file
load_dotenv()

# Get MongoDB URI from environment variable
mongo_uri = os.getenv('MONGO_URI')

# Connect to MongoDB
client = MongoClient(mongo_uri)

# Extract database name from the MongoDB URI
db_name = mongo_uri.split('/')[-1].split('?')[0]
db = client[db_name]

# Admin user details
username = "admin"
password = "mongodb123"

# Hash the password
hashed_password = scrypt.hash(password)

# Create admin user document
admin_user = {
    "_id": ObjectId(),  # MongoDB will generate a unique ObjectId
    "username": username,
    "password": hashed_password,
    "is_admin": True,
    "created_at": datetime.datetime.utcnow()
}

# Insert the admin user into the customers collection
result = db.customers.insert_one(admin_user)

print(f"Admin user created with id: {result.inserted_id}")

# Close the MongoDB connection
client.close()