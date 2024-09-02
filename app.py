import inspect
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, make_response, jsonify, session, request
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from io import BytesIO
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from passlib.hash import scrypt
from config import Config
import datetime
from bson import ObjectId
import traceback
from decimal import Decimal, ROUND_HALF_UP
import random
import json
from bson import json_util
import time
import psycopg2
from psycopg2.extras import execute_values
from passlib.hash import scrypt
from psycopg2.extras import RealDictCursor
from urllib.parse import urlparse
from flask import jsonify
from flask_cors import CORS
import pymongo 

from pymongo import MongoClient, WriteConcern, ReadPreference, errors
from pymongo.read_concern import ReadConcern
import math
from datetime import datetime, timedelta, timezone

import logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)
app.config.from_object(Config)
CORS(app)

# Parse the MongoDB URI
parsed_uri = urlparse(app.config['MONGO_URI'])

# Extract the database name
db_name = parsed_uri.path.lstrip('/')

# Remove any query parameters from the database name
db_name = db_name.split('?')[0]

# Update the MONGO_URI in the app config to use the correct database name
app.config['MONGO_URI'] = f"{parsed_uri.scheme}://{parsed_uri.netloc}/{db_name}"

mongo = PyMongo(app)
client = MongoClient(app.config['MONGO_URI'])
db = client[db_name]

print(f"Connected to database: {db_name}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    password = request.form['password']
    
    user = mongo.db.customers.find_one({'username': username})
    if user:
        stored_password = user['password']
        if scrypt.verify(password, stored_password):
            session['user_id'] = str(user['_id'])
            return redirect(url_for('dashboard'))
    
    return 'Invalid username or password', 401

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']

    try:
        # Calculate total balance
        total_balance_cursor = db.accounts.aggregate([
            {"$match": {"customer_id": ObjectId(user_id)}},
            {"$group": {"_id": None, "total_balance": {"$sum": "$balance"}}}
        ])

        total_balance_result = list(total_balance_cursor)
        total_balance = total_balance_result[0]["total_balance"] if total_balance_result else 0

        # Calculate recent transactions
        recent_transaction_count = db.transactions.count_documents({
            "customer_id": ObjectId(user_id),
            "timestamp": {"$gte": datetime.now() - timedelta(days=7)}
        })

        # Calculate pending reviews
        pending_review_count = db.transactions.count_documents({
            "customer_id": ObjectId(user_id),
            "review_status": {"$exists": False},
            "fraud_flags": {"$exists": True, "$ne": []}
        })

        # Calculate alerts
        alert_count = db.alerts.count_documents({"customer_id": ObjectId(user_id)})

        user = db.customers.find_one({"_id": ObjectId(user_id)})
        accounts = list(db.accounts.find({"customer_id": ObjectId(user_id)}))

        return render_template('dashboard.html', user=user, accounts=accounts,
                               total_balance=total_balance,
                               recent_transaction_count=recent_transaction_count,
                               pending_review_count=pending_review_count,
                               alert_count=alert_count)

    except Exception as e:
        logging.error(f"Error fetching dashboard metrics: {e}")
        return jsonify({'error': 'An error occurred while fetching dashboard metrics.'}), 500



@app.route('/api/accounts/<account_id>', methods=['GET'])
def get_account(account_id):
    account = db.accounts.find_one({"_id": ObjectId(account_id)})
    if account:
        account['_id'] = str(account['_id'])
        return jsonify({
            'account_type': account.get('account_type'),
            'balance': account.get('balance')
        })
    else:
        return jsonify({'error': 'Account not found'}), 404
    
@app.route('/api/transaction/<transaction_id>', methods=['GET'])
def get_transaction(transaction_id):
    transaction = db.transactions.find_one({"_id": ObjectId(transaction_id)})
    if transaction:
        transaction['_id'] = str(transaction['_id'])
        return jsonify({
            'account_type': transaction.get('type'),
            'amount': transaction.get('amount'),
            'from_account': transaction.get('from_account'),
            'to_account': transaction.get('to_account'),
            'amount': transaction.get('amount'),
            'fraud': transaction.get('fraud_flags', [])
        })
    else:
        return jsonify({'error': 'Account not found'}), 404

from bson import ObjectId
from bson.json_util import dumps
import json

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        account_id = request.args.get('account_id')
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 6))
        skip = (page - 1) * limit

        user_id = ObjectId(session['user_id'])

        # If no account_id is provided, fetch transactions for all user's accounts
        if not account_id:
            user_accounts = list(mongo.db.accounts.find({'customer_id': user_id}))
            account_ids = [account['_id'] for account in user_accounts]
            query = {'account_id': {'$in': account_ids}}
        else:
            account_object_id = ObjectId(account_id)
            query = {'account_id': account_object_id}

        app.logger.info(f"Fetching transactions with query: {query}")
        transactions = list(mongo.db.transactions.find(query)
                            .sort('timestamp', pymongo.DESCENDING)
                            .skip(skip)
                            .limit(limit))

        app.logger.info(f"Found {len(transactions)} transactions")

        serialized_transactions = []
        for transaction in transactions:
            serialized_transaction = {
                '_id': str(transaction['_id']),
                'account_id': str(transaction['account_id']),
                'type': transaction['type'],
                'amount': transaction['amount'],
                'timestamp': transaction['timestamp'].isoformat() if isinstance(transaction['timestamp'], datetime) else transaction['timestamp'],
                'fraud_flags': transaction.get('fraud_flags', [])

            }
            if 'from_account' in transaction:
                serialized_transaction['from_account'] = str(transaction['from_account'])
                from_account = mongo.db.accounts.find_one({"_id": ObjectId(transaction['from_account'])})
                if from_account:
                    serialized_transaction['from_account_name'] = from_account['account_type']
            if 'to_account' in transaction:
                serialized_transaction['to_account'] = str(transaction['to_account'])
                to_account = mongo.db.accounts.find_one({"_id": ObjectId(transaction['to_account'])})
                if to_account:
                    serialized_transaction['to_account_name'] = to_account['account_type']
            serialized_transactions.append(serialized_transaction)

        total_transactions = mongo.db.transactions.count_documents(query)
        total_pages = (total_transactions + limit - 1) // limit

        response_data = {
            'transactions': serialized_transactions,
            'page': page,
            'total_pages': total_pages
        }
        app.logger.info(f"Returning response: {response_data}")
        return jsonify(response_data)

    except Exception as e:
        app.logger.error(f"Error in get_transactions: {str(e)}")
        app.logger.error(traceback.format_exc())
        return jsonify({'error': 'An error occurred while retrieving transactions'}), 500


@app.route('/api/transaction', methods=['POST'])
def create_transaction():
    # Ensure the session is being accessed correctly
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    account_id = data.get('account_id')
    amount = data.get('amount')
    fraud_check = data.get('fraud_check')
    location = data.get('location')
    
    account = db.accounts.find_one({'_id': ObjectId(account_id), 'customer_id': ObjectId(session['user_id'])})
    if not account:
        return jsonify({'error': 'Account not found'}), 404
    
    amount = float(data['amount'])
    if data['type'] == 'withdrawal' and account['balance'] < amount:
        return jsonify({'error': 'Insufficient funds'}), 400
    
    new_balance = account['balance'] + amount if data['type'] == 'deposit' else account['balance'] - amount
    timestamp = datetime.now(timezone.utc)  # Correctly getting the current UTC time
    
    # Initialize fraud flags
    fraud_flags = []

    # Velocity Check
    if fraud_check == 'velocity':
        velocity_count = db.transactions.count_documents({
            'account_id': ObjectId(account_id),
            'timestamp': {'$gte': timestamp - timedelta(hours=1)}
        })
        if velocity_count > 10:  # Example threshold
            fraud_flags.append('velocity')
            # Insert an alert for velocity check
            alert = {
                "customer_id": ObjectId(session['user_id']),
                "account_id": ObjectId(account_id),
                "alert_type": "velocity_check",
                "message": f"Velocity check triggered: {velocity_count} transactions in the last hour.",
                "timestamp": datetime.now(timezone.utc),
                "resolved": False
            }
            db.alerts.insert_one(alert)

    # Location Check
    if fraud_check == 'location' and location:
        previous_transaction = db.transactions.find_one(
            {'account_id': ObjectId(account_id)},
            sort=[('timestamp', -1)]
        )
        if previous_transaction and previous_transaction.get('location'):
            prev_location = previous_transaction['location']
            if calculate_distance(location, prev_location) > 1000:  # Example threshold in km
                fraud_flags.append('location')
                # Insert an alert for location check
                alert = {
                    "customer_id": ObjectId(session['user_id']),
                    "account_id": ObjectId(account_id),
                    "alert_type": "location_check",
                    "message": f"Location check triggered: Distance from last transaction is over 1000 km.",
                    "timestamp": datetime.now(timezone.utc),
                    "resolved": False
                }
                db.alerts.insert_one(alert)

    # Create the transaction document
    transaction = {
        'account_id': ObjectId(account_id),
        'amount': amount,
        'type': data['type'],
        'timestamp': timestamp.isoformat(),
        'location': location,
        'fraud_flags': fraud_flags,
    }
    
    db.transactions.insert_one(transaction)
    db.accounts.update_one({'_id': ObjectId(account_id)}, {'$set': {'balance': new_balance}})
    
    return jsonify({'success': True, 'new_balance': new_balance, 'fraud_flags': fraud_flags})


@app.route('/fraud_simulation_dashboard')
def fraud_simulation_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))

    user_id = session['user_id']
    accounts = list(mongo.db.accounts.find({'customer_id': ObjectId(user_id)}))

    # Debugging
    print("Accounts:", accounts)  # Check what is being passed to the template
    
    return render_template('fraud_simulation_dashboard.html', accounts=accounts)


@app.route('/get_code/<endpoint>', methods=['GET'])
def get_code(endpoint):
    code_snippets = {
        'login': {
            'title': 'Login Route',
            'code': inspect.getsource(login),
            'description': 'This route handles user authentication. It checks the provided username and password against the stored values in the database and creates a session upon successful login.',
            'docs_link': 'https://docs.mongodb.com/manual/reference/method/db.collection.findOne/'  # Example link
        },
        'get_transactions': {
            'title': 'Get Transactions Route',
            'code': inspect.getsource(get_transactions),
            'description': 'This route retrieves the latest transactions for a specific account. It uses MongoDB’s `find` method to query transactions and sort them by timestamp.',
            'docs_link': 'https://docs.mongodb.com/manual/reference/method/db.collection.find/'  # Example link
        },
        'create_transaction': {
            'title': 'Create Transaction Route',
            'code': inspect.getsource(create_transaction),
            'description': 'This route creates a new transaction and updates the account balance. It performs a deposit or withdrawal based on the request type and ensures atomicity using MongoDB’s ACID transaction capabilities.',
            'docs_link': 'https://docs.mongodb.com/manual/core/transactions/'  # Example link
        },
        'branch_locator': {
            'title': 'Branch & ATM Locator Logic',
            'code': inspect.getsource(get_branches),  # assuming branch_locator is a defined function
            'description': 'This code powers the branch and ATM locator functionality, retrieving nearby branches and ATMs based on user location.',
            'docs_link': 'https://docs.mongodb.com/'  # Replace with relevant documentation
        },
        'transfer': {
            'title': 'Transfer Route',
            'code': inspect.getsource(transfer),
            'description': 'This route handles transferring funds between accounts. It ensures both the debit from the source account and the credit to the destination account are performed atomically using a MongoDB transaction.',
            'docs_link': 'https://docs.mongodb.com/manual/core/transactions/'  # Example link
        },
        'data_model': {
            'title': 'Data Model',
            'code': '''
# Customer Document
{
    "_id": ObjectId("..."),
    "username": "johndoe",
    "password": "hashed_password",
    "email": "johndoe@example.com",
    "created_at": ISODate("2023-08-28T12:00:00Z")
}

# Account Document
{
    "_id": ObjectId("..."),
    "customer_id": ObjectId("..."),
    "account_type": "Checking",
    "balance": 1000.00,
    "created_at": ISODate("2023-08-28T12:00:00Z"),
    "branch_id": ObjectId("...")
}

# Transaction Document
{
    "_id": ObjectId("..."),
    "account_id": ObjectId("..."),
    "type": "deposit",
    "amount": 500.00,
    "timestamp": ISODate("2023-08-28T12:00:00Z"),
    "from_account": ObjectId("..."),  # Optional, for transfers
    "to_account": ObjectId("..."),    # Optional, for transfers
    "fraud_flags": ["velocity", "location"]  # Optional
}

# Branch Document
{
    "_id": ObjectId("..."),
    "name": "Downtown Branch",
    "address": {
        "street": "123 Main St",
        "city": "Anytown",
        "state": "ST",
        "zip_code": "12345",
        "country": "USA"
    },
    "phone_number": "555-1234",
    "email": "downtown@bank.com",
    "manager": "Jane Doe",
    "services": ["Loans", "Deposits", "Wealth Management"],
    "hours": {
        "monday": {"open": "09:00", "close": "17:00"},
        "tuesday": {"open": "09:00", "close": "17:00"},
        # ... other days ...
    },
    "location": {
        "type": "Point",
        "coordinates": [-73.98, 40.73]  # [longitude, latitude]
    }
}

# ATM Document
{
    "_id": ObjectId("..."),
    "branch_id": ObjectId("..."),
    "location": {
        "type": "Point",
        "coordinates": [-73.98, 40.73]  # [longitude, latitude]
    },
    "address": {
        "street": "456 Side St",
        "city": "Anytown",
        "state": "ST",
        "zip_code": "12345",
        "country": "USA"
    },
    "type": "Walk-up",
    "features": ["Cash Withdrawal", "Deposit", "Check Cashing"],
    "accessibility": true,
    "status": "Operational"
}

# Alert Document
{
    "_id": ObjectId("..."),
    "customer_id": ObjectId("..."),
    "account_id": ObjectId("..."),
    "transaction_id": ObjectId("..."),
    "type": "Potential Fraud",
    "message": "Suspicious activity detected: velocity check triggered",
    "timestamp": ISODate("2023-08-28T12:00:00Z"),
    "resolved": false
}
''',
            'description': 'This represents the comprehensive data model for the application, defining the structure of customer, account, transaction, branch, ATM, and alert documents.',
            'docs_link': 'https://www.mongodb.com/docs/manual/data-modeling/'
        },
        'velocity_check': {
            'title': 'Velocity Check Logic',
            'code': '''
# Velocity Check Logic

velocity_count = db.transactions.count_documents({
    'account_id': ObjectId(account_id),
    'timestamp': {'$gte': timestamp - datetime.timedelta(hours=1)}
})
if velocity_count > 10:  # Example threshold
    fraud_flags.append('velocity')
''',
            'description': 'This logic checks the number of transactions within the past hour. If the count exceeds a predefined threshold, the transaction is flagged as potentially fraudulent.',
            'docs_link': 'https://www.mongodb.com/docs/manual/reference/method/db.collection.countDocuments/'
        },
        'location_check': {
            'title': 'Location Check Logic',
            'code': '''
# Location Check Logic

previous_transaction = db.transactions.find_one(
    {'account_id': ObjectId(account_id)},
    sort=[('timestamp', -1)]
)
if previous_transaction and location:
    prev_location = previous_transaction.get('location')
    if prev_location and calculate_distance(location, prev_location) > 1000:  # Example threshold in km
        fraud_flags.append('location')
''',
            'description': 'This logic compares the current transaction location with the previous transaction location. If the distance exceeds a certain threshold, the transaction is flagged as potentially fraudulent.',
            'docs_link': 'https://www.mongodb.com/docs/manual/reference/method/db.collection.findOne/'
        }
    }
    
    if endpoint in code_snippets:
        return jsonify(code_snippets[endpoint])
    else:
        return jsonify({'title': 'Not Found', 'code': 'Code not available'}), 404

@app.route('/transfer', methods=['POST'])
def transfer():
    source_account_id = request.json['source_account_id']
    destination_account_id = request.json['destination_account_id']
    amount = float(request.json['amount'])
    simulate_failure = request.json.get('simulate_failure', False)  # Get the simulate failure flag

    logging.info(f"Starting transfer from {source_account_id} to {destination_account_id} amount: {amount}")

    try:
        with client.start_session() as session:
            with session.start_transaction():
                # Simulate a failure if the checkbox was checked
                if simulate_failure:
                    raise Exception("Simulated failure for demonstration purposes")

                # Step 1: Debit from source account
                logging.info("Attempting to debit source account")
                source_account = db.accounts.find_one_and_update(
                    {"_id": ObjectId(source_account_id), "balance": {"$gte": amount}},
                    {"$inc": {"balance": -amount}},
                    session=session,
                    return_document=True
                )
                if not source_account:
                    logging.error("Insufficient funds in source account")
                    raise errors.OperationFailure("Insufficient funds in source account")

                # Step 2: Credit to destination account
                logging.info("Attempting to credit destination account")
                destination_account = db.accounts.find_one_and_update(
                    {"_id": ObjectId(destination_account_id)},
                    {"$inc": {"balance": amount}},
                    session=session,
                    return_document=True
                )

                if not destination_account:
                    logging.error("Destination account not found")
                    raise errors.OperationFailure("Destination account not found")

                # Step 3: Record transaction in the source account
                logging.info("Recording transaction in the source account")
                source_transaction = {
                    "account_id": ObjectId(source_account_id),
                    "amount": -amount,
                    "type": "transfer_out",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "from_account": ObjectId(source_account_id),
                    "to_account": ObjectId(destination_account_id)
                }
                db.transactions.insert_one(source_transaction, session=session)

                # Step 4: Record transaction in the destination account
                logging.info("Recording transaction in the destination account")
                destination_transaction = {
                    "account_id": ObjectId(destination_account_id),
                    "amount": amount,
                    "type": "transfer_in",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "from_account": ObjectId(source_account_id),
                    "to_account": ObjectId(destination_account_id)
                }
                db.transactions.insert_one(destination_transaction, session=session)

        logging.info("Transfer successful")
        return jsonify({"status": "Transfer successful"}), 200
    except errors.OperationFailure as e:
        logging.error(f"OperationFailure: {e}")
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        logging.error(f"General Exception: {e}")
        return jsonify({"error": "An error occurred during the transaction"}), 500

def calculate_distance(location1, location2):
    """
    Calculate the great-circle distance between two points 
    on the Earth's surface specified by their latitude and longitude.
    
    Parameters:
    location1 (dict): Dictionary containing 'latitude' and 'longitude' for the first location.
    location2 (dict): Dictionary containing 'latitude' and 'longitude' for the second location.
    
    Returns:
    float: Distance between the two points in kilometers.
    """
    
    # Convert latitude and longitude from degrees to radians
    lat1, lon1 = math.radians(location1['latitude']), math.radians(location1['longitude'])
    lat2, lon2 = math.radians(location2['latitude']), math.radians(location2['longitude'])
    
    # Haversine formula
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = math.sin(dlat / 2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    # Radius of the Earth in kilometers (mean radius)
    R = 6371.01
    
    # Calculate the distance
    distance = R * c
    return distance

from bson import ObjectId
from bson.json_util import dumps
import json

from bson import ObjectId
from bson.json_util import dumps
import json
from datetime import datetime, timezone, timedelta

@app.route('/api/statement', methods=['GET'])
def generate_statement():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    account_id = request.args.get('account_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    # Convert start and end dates to UTC timezone-aware datetimes
    start_datetime = datetime.fromisoformat(f"{start_date}T00:00:00").replace(tzinfo=timezone.utc)
    end_datetime = datetime.fromisoformat(f"{end_date}T23:59:59").replace(tzinfo=timezone.utc)
 
    try:
        account_object_id = ObjectId(account_id)
        account = mongo.db.accounts.find_one({'_id': account_object_id, 'customer_id': ObjectId(session['user_id'])})
        if not account:
            logging.error(f"Account not found for account_id: {account_id}")
            return jsonify({'error': 'Account not found'}), 404

        logging.info(f"Fetching transactions for account_id: {account_id} from {start_datetime} to {end_datetime}")

        # More flexible date query
        query = {
            'account_id': account_object_id,
            '$or': [
                {'timestamp': {'$gte': start_datetime, '$lte': end_datetime}},
                {'timestamp': {'$gte': start_datetime.isoformat(), '$lte': end_datetime.isoformat()}},
            ]
        }

        transactions = list(mongo.db.transactions.find(query).sort('timestamp', pymongo.DESCENDING))
     
        logging.info(f"Found {len(transactions)} transactions")
        
        # Log a sample transaction if available
        if transactions:
            logging.info(f"Sample transaction: {transactions[0]}")
        else:
            logging.info("No transactions found. Checking for any transactions in the collection.")
            sample_transaction = mongo.db.transactions.find_one()
            if sample_transaction:
                logging.info(f"Sample transaction from collection: {sample_transaction}")
            else:
                logging.info("No transactions found in the collection at all.")

        # Prepare the statement data
        statement = {
            'account_type': account.get('account_type'),
            'balance': account.get('balance'),
            'transactions': transactions,
            'start_date': start_date,
            'end_date': end_date,
        }

        # Use json_util to handle MongoDB-specific types
        json_statement = json.loads(dumps(statement))

        # Further process the transactions if needed
        for transaction in json_statement['transactions']:
            if 'timestamp' in transaction:
                if isinstance(transaction['timestamp'], dict) and '$date' in transaction['timestamp']:
                    transaction['timestamp'] = datetime.fromisoformat(transaction['timestamp']['$date']).isoformat()
                elif isinstance(transaction['timestamp'], str):
                    # If it's already a string, we'll assume it's in ISO format
                    pass
                else:
                    logging.warning(f"Unexpected timestamp format: {transaction['timestamp']}")

        return jsonify(json_statement), 200
 
    except Exception as e:
        logging.error(f"Error generating statement: {e}")
        return jsonify({'error': 'An error occurred while generating the statement'}), 500
    
@app.route('/api/generate_pdf_statement', methods=['GET'])
def generate_pdf_statement():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    account_id = request.args.get('account_id')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    try:
        account_object_id = ObjectId(account_id)
        account = mongo.db.accounts.find_one({'_id': account_object_id, 'customer_id': ObjectId(session['user_id'])})
        if not account:
            return jsonify({'error': 'Account not found'}), 404

        transactions = list(mongo.db.transactions.find({
            'account_id': account_object_id,
            'timestamp': {
                '$gte': start_date,
                '$lte': end_date
            }
        }).sort('timestamp', pymongo.DESCENDING))

        # Create a PDF
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter)
        elements = []

        # Add title
        styles = getSampleStyleSheet()
        elements.append(Paragraph(f"Account Statement", styles['Title']))
        elements.append(Paragraph(f"Account Type: {account['account_type']}", styles['Normal']))
        elements.append(Paragraph(f"Balance: ${account['balance']:.2f}", styles['Normal']))
        elements.append(Paragraph(f"From: {start_date} To: {end_date}", styles['Normal']))

        # Add transactions table
        data = [['Date', 'Type', 'Amount']]
        for transaction in transactions:
            # Parse the timestamp string into a datetime object
            timestamp = datetime.fromisoformat(transaction['timestamp'].replace('Z', '+00:00'))
            data.append([
                timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                transaction['type'],
                f"${transaction['amount']:.2f}",
                transaction.get('from_account_name', '-'),
                transaction.get('to_account_name', '-')
            ])

        table = Table(data)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 14),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 12),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 1, colors.black)
        ]))

        elements.append(table)

        # Generate PDF
        doc.build(elements)

        # Prepare response
        pdf = buffer.getvalue()
        buffer.close()
        response = make_response(pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'attachment; filename=statement_{start_date}_to_{end_date}.pdf'

        return response

    except Exception as e:
        app.logger.error(f"Error generating PDF statement: {str(e)}")
        app.logger.error(traceback.format_exc())  # This will log the full stack trace
        return jsonify({'error': 'An error occurred while generating the PDF statement'}), 500
    
@app.route('/api/review_transactions', methods=['GET'])
def get_review_transactions():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    transactions = list(mongo.db.transactions.find({
        'fraud_flags': {'$exists': True, '$ne': []},
        'reviewed': False
    }))
    
    for transaction in transactions:
        transaction['_id'] = str(transaction['_id'])
        transaction['account_id'] = str(transaction['account_id'])
        transaction['timestamp'] = transaction['timestamp'].isoformat()
    
    return jsonify(transactions), 200

@app.route('/api/review_transaction', methods=['POST'])
def review_transaction():
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    transaction_id = data.get('transaction_id')
    review_status = data.get('review_status')  # "legitimate" or "fraudulent"
    
    if not transaction_id or review_status not in ['legitimate', 'fraudulent']:
        return jsonify({'error': 'Invalid input'}), 400

    update_data = {
        'reviewed': True,
        'review_status': review_status
    }

    # If the transaction is reviewed as legitimate, clear the fraud flags
    if review_status == 'legitimate':
        update_data['fraud_flags'] = []  # Clear the fraud flags

    mongo.db.transactions.update_one(
        {'_id': ObjectId(transaction_id)},
        {'$set': update_data}
    )
    
    return jsonify({'success': True}), 200

@app.route('/api/dashboard_metrics', methods=['GET'])
def get_dashboard_metrics():
    try:
        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'error': 'Unauthorized'}), 401

        # Fetch total balance
        total_balance_cursor = db.accounts.aggregate([
            {'$match': {'customer_id': ObjectId(user_id)}},
            {'$group': {'_id': None, 'total_balance': {'$sum': '$balance'}}}
        ])

        total_balance_result = list(total_balance_cursor)
        total_balance = total_balance_result[0]["total_balance"] if total_balance_result else 0

        # Calculate recent transactions
        recent_transaction_count = db.transactions.count_documents({
            "account_id": {'$in': [account['_id'] for account in db.accounts.find({'customer_id': ObjectId(user_id)})]},
            "timestamp": {"$gte": datetime.now() - timedelta(days=7)}
        })

        # Calculate pending reviews
        pending_review_count = db.transactions.count_documents({
            "account_id": {'$in': [account['_id'] for account in db.accounts.find({'customer_id': ObjectId(user_id)})]},
            "review_status": {"$exists": False},
            "fraud_flags": {"$exists": True, "$ne": []}
        })

        # Calculate alerts
        alert_count = db.alerts.count_documents({
            "account_id": {'$in': [account['_id'] for account in db.accounts.find({'customer_id': ObjectId(user_id)})]}
        })

        return jsonify({
            'total_balance': total_balance,
            'recent_transaction_count': recent_transaction_count,
            'pending_review_count': pending_review_count,
            'alert_count': alert_count
        }), 200

    except Exception as e:
        logging.error(f"Error fetching dashboard metrics: {e}")
        return jsonify({'error': 'An error occurred'}), 500

def create_admin_user(username, password):
    hashed_password = scrypt.hash(password)
    admin_user = {
        "username": username,
        "password": hashed_password,
        "is_admin": True
    }
    mongo.db.customers.insert_one(admin_user)
    
@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        user = mongo.db.customers.find_one({'username': username, 'is_admin': True})
        if user and scrypt.verify(password, user['password']):
            session['admin_id'] = str(user['_id'])
            return redirect(url_for('admin_dashboard'))
        
        return 'Invalid username or password', 401
    
    return render_template('admin_login.html')

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'admin_id' not in session:
        return redirect(url_for('admin_login'))
    
    # Add admin dashboard logic here
    return render_template('admin_dashboard.html')

def serialize_mongo_doc(doc):
    """Helper function to serialize MongoDB document"""
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            doc[key] = str(value)
        elif isinstance(value, datetime):
            doc[key] = value.isoformat()
    return doc

@app.route('/admin/api/dashboard_metrics')
def admin_dashboard_metrics():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    total_users = mongo.db.customers.count_documents({})
    total_transactions = mongo.db.transactions.count_documents({})
    total_accounts = mongo.db.accounts.count_documents({})

    recent_transactions = list(mongo.db.transactions.find().sort('timestamp', -1).limit(5))
    recent_transactions = [serialize_mongo_doc(transaction) for transaction in recent_transactions]

    fraud_alerts = list(mongo.db.transactions.find({'fraud_flags': {'$exists': True, '$ne': []}}).sort('timestamp', -1).limit(5))
    fraud_alerts = [serialize_mongo_doc(alert) for alert in fraud_alerts]

    return jsonify({
        'total_users': total_users,
        'total_transactions': total_transactions,
        'total_accounts': total_accounts,
        'recent_transactions': recent_transactions,
        'fraud_alerts': fraud_alerts
    })

@app.route('/admin/api/transaction_volume')
def transaction_volume():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    pipeline = [
        {
            '$addFields': {
                'date': {
                    '$dateFromString': {
                        'dateString': '$timestamp',
                        'onError': '$timestamp'  # If parsing fails, use the original value
                    }
                }
            }
        },
        {
            '$group': {
                '_id': {
                    '$dateToString': {
                        'format': '%Y-%m-%d',
                        'date': '$date'
                    }
                },
                'count': {'$sum': 1},
                'total_amount': {'$sum': '$amount'}
            }
        },
        {'$sort': {'_id': 1}},
        {'$limit': 30}
    ]

    try:
        result = list(mongo.db.transactions.aggregate(pipeline))
        return jsonify(result)
    except Exception as e:
        app.logger.error(f"Error in transaction_volume: {str(e)}")
        return jsonify({'error': 'An error occurred while fetching transaction volume data'}), 500

import random
from datetime import datetime, timedelta
from bson import ObjectId

import random
from datetime import datetime, timedelta, timezone
from bson import ObjectId

@app.route('/admin/reset_data', methods=['POST'])
def reset_data():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    db_type = request.form.get('db_type')
    postgres_uri = request.form.get('postgres_uri') or os.getenv('POSTGRES_URI')

    try:
        # Clear existing data
        if db_type == 'mongodb':

            mongo.db.customers.delete_many({})
            mongo.db.accounts.delete_many({})
            mongo.db.transactions.delete_many({})
            mongo.db.alerts.delete_many({})
            mongo.db.branches.delete_many({})
            mongo.db.atms.delete_many({})

            # Create branches
            branches = create_branches()
            branch_ids = [branch['_id'] for branch in branches]
            mongo.db.branches.insert_many(branches)

            # Create ATMs
            atms = create_atms(branch_ids)
            mongo.db.atms.insert_many(atms)

            # Create johndoe user
            johndoe_id = ObjectId()
            mongo.db.customers.insert_one({
                '_id': johndoe_id,
                'username': 'johndoe',
                'password': scrypt.hash('password123'),
                'email': 'johndoe@example.com',
                'created_at': datetime.now(timezone.utc)
            })

            # Create accounts for johndoe
            checking_id = ObjectId()
            savings_id = ObjectId()
            accounts = [
                {
                    '_id': checking_id,
                    'customer_id': johndoe_id,
                    'account_type': 'Checking',
                    'balance': float('5000.00'),
                    'created_at': datetime.now(timezone.utc),
                    'branch_id': random.choice(branch_ids)  # Link account to a random branch
                },
                {
                    '_id': savings_id,
                    'customer_id': johndoe_id,
                    'account_type': 'Savings',
                    'balance': float('10000.00'),
                    'created_at': datetime.now(timezone.utc),
                    'branch_id': random.choice(branch_ids)  # Link account to a random branch
                }
            ]
            mongo.db.accounts.insert_many(accounts)

            # Generate sample transactions (unchanged)
            transactions = []
            alerts = []
            current_date = datetime.now(timezone.utc) - timedelta(days=30)
            account_balances = {str(checking_id): Decimal('5000.00'), str(savings_id): Decimal('10000.00')}

            for _ in range(100):  # Generate 100 transactions over the last 30 days
                transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
                amount = round_to_penny(random.uniform(10, 1000))
                
                from_account = random.choice([checking_id, savings_id])
                to_account = checking_id if from_account == savings_id else savings_id

                # Ensure withdrawal and transfers don't result in negative balance
                if transaction_type in ['withdrawal', 'transfer']:
                    max_amount = account_balances[str(from_account)]
                    amount = min(amount, max_amount)

                transaction = {
                    '_id': ObjectId(),
                    'customer_id': johndoe_id,
                    'account_id': from_account if transaction_type != 'transfer' else None,
                    'type': transaction_type,
                    'amount': float(amount),
                    'timestamp': current_date,
                }

                if transaction_type == 'transfer':
                    transaction['from_account'] = from_account
                    transaction['to_account'] = to_account
                    account_balances[str(from_account)] -= amount
                    account_balances[str(to_account)] += amount
                elif transaction_type == 'deposit':
                    account_balances[str(from_account)] += amount
                else:  # withdrawal
                    account_balances[str(from_account)] -= amount

                # Randomly add fraud flags
                if random.random() < 0.1:  # 10% chance of fraud flag
                    fraud_type = random.choice(['velocity', 'location'])
                    transaction['fraud_flags'] = [fraud_type]
                    
                    # Create an alert for this transaction
                    alert = {
                        'customer_id': johndoe_id,
                        'account_id': transaction['account_id'] or transaction['from_account'],
                        'transaction_id': transaction['_id'],
                        'type': 'Potential Fraud',
                        'message': f"Suspicious activity detected: {fraud_type}",
                        'timestamp': current_date,
                        'resolved': False
                    }
                    alerts.append(alert)

                transactions.append(transaction)
                current_date += timedelta(minutes=random.randint(30, 720))  # 0.5 to 12 hours between transactions

            mongo.db.transactions.insert_many(transactions)
            if alerts:
                mongo.db.alerts.insert_many(alerts)

            # Update final account balances
            mongo.db.accounts.update_one({'_id': checking_id}, {'$set': {'balance': float(account_balances[str(checking_id)])}})
            mongo.db.accounts.update_one({'_id': savings_id}, {'$set': {'balance': float(account_balances[str(savings_id)])}})
            message = "MongoDB data reset successful. Sample data generated for johndoe user, branches, and ATMs."

        elif db_type == 'postgres':
            conn = psycopg2.connect(postgres_uri)
            cur = conn.cursor()

            # Call the populate_database function from the create_data script
            message = populate_postgres_database()
        else:
            return jsonify({'error': 'Invalid database type'}), 400

        return jsonify({'message': message}), 200

    except Exception as e:
        app.logger.error(f"Error resetting data: {str(e)}")
        return jsonify({'error': 'An error occurred while resetting data'}), 500

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
        branch = {
            '_id': ObjectId(),
            'name': f"MongoDBank {city} Branch",
            'address': {
                'street': f"{100+i} Main St",
                'city': city,
                'state': state,
                'zipCode': f"1000{i}",
                'country': "USA"
            },
            'phoneNumber': f"555-{1000+i:04d}",
            'email': f"branch.{city.lower().replace(' ', '')}@mongodbank.com",
            'manager': f"Manager{i+1}",
            'services': ["Loans", "Deposits", "Wealth Management"],
            'hours': {
                'monday': {'open': "09:00", 'close': "17:00"},
                'tuesday': {'open': "09:00", 'close': "17:00"},
                'wednesday': {'open': "09:00", 'close': "17:00"},
                'thursday': {'open': "09:00", 'close': "17:00"},
                'friday': {'open': "09:00", 'close': "17:00"},
                'saturday': {'open': "10:00", 'close': "14:00"},
                'sunday': {'open': "Closed", 'close': "Closed"}
            },
            'location': {
                'type': "Point",
                'coordinates': [lon, lat]
            }
        }
        branches.append(branch)
    
    return branches

def create_atms(branch_ids):
    atms = []
    for i, branch_id in enumerate(branch_ids):
        # Create 2 ATMs for each branch
        for j in range(12):
            atm = {
                '_id': ObjectId(),
                'location': {
                    'type': "Point",
                    'coordinates': [random.uniform(-122, -71), random.uniform(25, 48)]  # Random US coordinates
                },
                'address': {
                    'street': f"{200+i*2+j} ATM St",
                    'city': "ATM City",
                    'state': "AT",
                    'zipCode': f"2000{i}",
                    'country': "USA"
                },
                'type': random.choice(["Walk-up", "Drive-through"]),
                'features': ["Cash Withdrawal", "Deposit", "Check Cashing"],
                'accessibility': random.choice([True, False]),
                'branchId': branch_id,
                'status': "Operational"
            }
            atms.append(atm)
    
    return atms

@app.route('/api/branches', methods=['GET'])
def get_branches():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius', 10))  # Default 10 km

    branches = mongo.db.branches.find({
        'location': {
            '$near': {
                '$geometry': {
                    'type': "Point",
                    'coordinates': [lon, lat]
                },
                '$maxDistance': radius * 100000  # Convert km to meters
            }
        }
    })

    return json.loads(json_util.dumps(list(branches)))

@app.route('/api/atms', methods=['GET'])
def get_atms():
    lat = float(request.args.get('lat'))
    lon = float(request.args.get('lon'))
    radius = float(request.args.get('radius', 5))  # Default 5 km

    atms = mongo.db.atms.find({
        'location': {
            '$near': {
                '$geometry': {
                    'type': "Point",
                    'coordinates': [lon, lat]
                },
                '$maxDistance': radius * 100000  # Convert km to meters
            }
        }
    })

    return json.loads(json_util.dumps(list(atms)))
@app.route('/branch-locator')
def branch_locator():
    return render_template('branch_locator.html', GOOGLE_MAPS_API_KEY=app.config['GOOGLE_MAPS_API_KEY'])

@app.route('/performance_comparison')
def performance_comparison():
    return render_template('performance_comparison.html')

@app.route('/api/run_performance_comparison', methods=['POST'])
def run_performance_comparison():
    query_type = request.json['query_type']
    
    # PostgreSQL query
    postgres_start = time.time()
    postgres_results = []
    
    try:
        with psycopg2.connect(app.config['POSTGRES_URI']) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if query_type == 'account_details':
                    cur.execute("""
                        WITH random_account AS (
                            SELECT id FROM accounts ORDER BY RANDOM() LIMIT 1
                        ),
                        account_transactions AS (
                            SELECT a.id, a.account_type, a.balance, 
                                   t.id as transaction_id, t.type, t.amount, t.timestamp,
                                   ROW_NUMBER() OVER (PARTITION BY a.id ORDER BY t.timestamp DESC) as rn
                            FROM accounts a
                            LEFT JOIN transactions t ON a.id = t.account_id
                            WHERE a.id = (SELECT id FROM random_account)
                        ),
                        transaction_stats AS (
                            SELECT account_id,
                                   AVG(amount) as avg_transaction_amount,
                                   MAX(amount) as max_transaction_amount,
                                   MIN(amount) as min_transaction_amount,
                                   COUNT(*) as total_transactions
                            FROM transactions
                            WHERE account_id = (SELECT id FROM random_account)
                            GROUP BY account_id
                        )
                        SELECT at.id, at.account_type, at.balance,
                               json_agg(json_build_object(
                                   'id', at.transaction_id,
                                   'type', at.type,
                                   'amount', at.amount,
                                   'timestamp', at.timestamp
                               )) FILTER (WHERE at.rn <= 10) as recent_transactions,
                               ts.avg_transaction_amount,
                               ts.max_transaction_amount,
                               ts.min_transaction_amount,
                               ts.total_transactions
                        FROM account_transactions at
                        LEFT JOIN transaction_stats ts ON at.id = ts.account_id
                        GROUP BY at.id, at.account_type, at.balance,
                                 ts.avg_transaction_amount, ts.max_transaction_amount,
                                 ts.min_transaction_amount, ts.total_transactions
                    """)
                elif query_type == 'customer_summary':
                    cur.execute("""
                        WITH random_customer AS (
                            SELECT id FROM customers ORDER BY RANDOM() LIMIT 1
                        ),
                        customer_accounts AS (
                            SELECT c.id as customer_id, c.username, c.email,
                                   a.id as account_id, a.account_type, a.balance,
                                   (SELECT COUNT(*) FROM transactions WHERE account_id = a.id) as transaction_count
                            FROM customers c
                            JOIN accounts a ON c.id = a.customer_id
                            WHERE c.id = (SELECT id FROM random_customer)
                        ),
                        account_stats AS (
                            SELECT ca.account_id,
                                   AVG(t.amount) as avg_transaction_amount,
                                   SUM(CASE WHEN t.type = 'deposit' THEN t.amount ELSE 0 END) as total_deposits,
                                   SUM(CASE WHEN t.type = 'withdrawal' THEN t.amount ELSE 0 END) as total_withdrawals
                            FROM customer_accounts ca
                            LEFT JOIN transactions t ON ca.account_id = t.account_id
                            GROUP BY ca.account_id
                        )
                        SELECT ca.customer_id, ca.username, ca.email,
                               json_agg(json_build_object(
                                   'account_id', ca.account_id,
                                   'account_type', ca.account_type,
                                   'balance', ca.balance,
                                   'transaction_count', ca.transaction_count,
                                   'avg_transaction_amount', ast.avg_transaction_amount,
                                   'total_deposits', ast.total_deposits,
                                   'total_withdrawals', ast.total_withdrawals
                               )) as accounts,
                               SUM(ca.balance) as total_balance,
                               COUNT(DISTINCT ca.account_id) as account_count
                        FROM customer_accounts ca
                        LEFT JOIN account_stats ast ON ca.account_id = ast.account_id
                        GROUP BY ca.customer_id, ca.username, ca.email
                    """)
                elif query_type == 'fraud_analysis':
                    thirty_days_ago = datetime.now() - timedelta(days=30)
                    cur.execute("""
                        WITH fraudulent_transactions AS (
                            SELECT t.id, t.account_id, t.type, t.amount, t.timestamp, t.fraud_flags,
                                   a.account_type,
                                   c.username as customer_name,
                                   ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.timestamp DESC) as rn
                            FROM transactions t
                            JOIN accounts a ON t.account_id = a.id
                            JOIN customers c ON a.customer_id = c.id
                            WHERE t.timestamp >= %s
                              AND t.fraud_flags IS NOT NULL
                              AND t.fraud_flags != '{}'
                        ),
                        fraud_stats AS (
                            SELECT account_id,
                                   COUNT(*) as fraud_count,
                                   AVG(amount) as avg_fraud_amount,
                                   SUM(amount) as total_fraud_amount
                            FROM fraudulent_transactions
                            GROUP BY account_id
                        )
                        SELECT ft.id as transaction_id, ft.type, ft.amount, ft.timestamp,
                               ft.fraud_flags, ft.account_type, ft.customer_name,
                               fs.fraud_count, fs.avg_fraud_amount, fs.total_fraud_amount,
                               (SELECT COUNT(*) FROM transactions 
                                WHERE account_id = ft.account_id AND timestamp >= %s) as total_transactions
                        FROM fraudulent_transactions ft
                        JOIN fraud_stats fs ON ft.account_id = fs.account_id
                        WHERE ft.rn <= 10
                        ORDER BY ft.timestamp DESC
                    """, (thirty_days_ago, thirty_days_ago))
                
                postgres_results = cur.fetchall()

        postgres_end = time.time()
        postgres_time = postgres_end - postgres_start

    except psycopg2.Error as e:
        app.logger.error(f"PostgreSQL Error: {e}")
        postgres_time = 0

    # MongoDB query
    mongo_start = time.time()
    if query_type == 'account_details':
        mongo_results = list(mongo.db.accounts.aggregate([
            { "$sample": { "size": 1 } },
            { "$lookup": {
                "from": "transactions",
                "localField": "_id",
                "foreignField": "account_id",
                "as": "transactions"
              }
            },
            { "$project": {
                "account_type": 1,
                "balance": 1,
                "recent_transactions": { 
                    "$slice": [
                        { "$sortArray": { 
                            "input": "$transactions", 
                            "sortBy": { "timestamp": -1 } 
                        }}, 
                        10
                    ]
                },
                "avg_transaction_amount": { "$avg": "$transactions.amount" },
                "max_transaction_amount": { "$max": "$transactions.amount" },
                "min_transaction_amount": { "$min": "$transactions.amount" },
                "total_transactions": { "$size": "$transactions" }
              }
            }
        ]))
    elif query_type == 'customer_summary':
        mongo_results = list(mongo.db.customers.aggregate([
            { "$sample": { "size": 1 } },
            { "$lookup": {
                "from": "accounts",
                "localField": "_id",
                "foreignField": "customer_id",
                "as": "accounts"
              }
            },
            { "$unwind": "$accounts" },
            { "$lookup": {
                "from": "transactions",
                "localField": "accounts._id",
                "foreignField": "account_id",
                "as": "accounts.transactions"
              }
            },
            { "$group": {
                "_id": "$_id",
                "username": { "$first": "$username" },
                "email": { "$first": "$email" },
                "accounts": {
                    "$push": {
                        "account_id": "$accounts._id",
                        "account_type": "$accounts.account_type",
                        "balance": "$accounts.balance",
                        "transaction_count": { "$size": "$accounts.transactions" },
                        "avg_transaction_amount": { "$avg": "$accounts.transactions.amount" },
                        "total_deposits": {
                            "$sum": {
                                "$filter": {
                                    "input": "$accounts.transactions",
                                    "as": "t",
                                    "cond": { "$eq": ["$$t.type", "deposit"] }
                                }
                            }
                        },
                        "total_withdrawals": {
                            "$sum": {
                                "$filter": {
                                    "input": "$accounts.transactions",
                                    "as": "t",
                                    "cond": { "$eq": ["$$t.type", "withdrawal"] }
                                }
                            }
                        }
                    }
                },
                "total_balance": { "$sum": "$accounts.balance" },
                "account_count": { "$sum": 1 }
              }
            }
        ]))
    elif query_type == 'fraud_analysis':
        thirty_days_ago = datetime.now() - timedelta(days=30)
        mongo_results = list(mongo.db.transactions.aggregate([
            { "$match": {
                "timestamp": { "$gte": thirty_days_ago },
                "fraud_flags": { "$exists": True, "$ne": [] }
              }
            },
            { "$lookup": {
                "from": "accounts",
                "localField": "account_id",
                "foreignField": "_id",
                "as": "account"
              }
            },
            { "$unwind": "$account" },
            { "$lookup": {
                "from": "customers",
                "localField": "account.customer_id",
                "foreignField": "_id",
                "as": "customer"
              }
            },
            { "$unwind": "$customer" },
            { "$group": {
                "_id": "$account_id",
                "fraud_transactions": { "$push": "$$ROOT" },
                "fraud_count": { "$sum": 1 },
                "avg_fraud_amount": { "$avg": "$amount" },
                "total_fraud_amount": { "$sum": "$amount" }
              }
            },
            { "$project": {
                "fraud_transactions": { "$slice": ["$fraud_transactions", 10] },
                "fraud_count": 1,
                "avg_fraud_amount": 1,
                "total_fraud_amount": 1
              }
            },
            { "$unwind": "$fraud_transactions" },
            { "$project": {
                "transaction_id": "$fraud_transactions._id",
                "type": "$fraud_transactions.type",
                "amount": "$fraud_transactions.amount",
                "timestamp": "$fraud_transactions.timestamp",
                "fraud_flags": "$fraud_transactions.fraud_flags",
                "account_type": "$fraud_transactions.account.account_type",
                "customer_name": "$fraud_transactions.customer.username",
                "fraud_count": 1,
                "avg_fraud_amount": 1,
                "total_fraud_amount": 1
              }
            },
            { "$sort": { "timestamp": -1 } },
            { "$limit": 100 }
        ]))
    mongo_end = time.time()
    mongo_time = mongo_end - mongo_start
    
    performance_gain = postgres_time / mongo_time if mongo_time > 0 and postgres_time > 0 else 0
    
    return jsonify({
        'postgres_time': round(postgres_time * 1000, 2),
        'mongo_time': round(mongo_time * 1000, 2),
        'performance_gain': round(performance_gain, 2),
        'postgres_results': len(postgres_results),
        'mongo_results': len(mongo_results)
    })
def connect_to_postgres():
    return psycopg2.connect(os.getenv('POSTGRES_URI'))

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

def populate_postgres_database(conn, cur):
    try:
        # Clear existing data
        cur.execute("""
            TRUNCATE customers, branches, branch_services, branch_hours, accounts, 
                     transactions, fraud_flags, alerts, atms, atm_features CASCADE;
        """)

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
        return "Data population completed successfully."

    except Exception as e:
        conn.rollback()
        return f"An error occurred: {e}"

    finally:
        cur.close()
        conn.close()
        
def round_to_penny(amount):
                return Decimal(amount).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

@app.route('/admin/deploy_data', methods=['POST'])
def deploy_data():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    db_type = request.json.get('db_type')
    uri = request.json.get(f'{db_type}_uri')

    if not uri:
        return jsonify({'error': f'No {db_type.upper()} URI provided'}), 400

    try:
        if db_type == 'mongodb':
            # MongoDB deployment
            client = MongoClient(uri)
            db = client.get_database()

            # Clear existing data
            db.customers.delete_many({})
            db.accounts.delete_many({})
            db.transactions.delete_many({})
            db.alerts.delete_many({})
            db.branches.delete_many({})
            db.atms.delete_many({})

            # Create branches
            branches = create_branches()
            branch_ids = [branch['_id'] for branch in branches]
            db.branches.insert_many(branches)

            # Create ATMs
            atms = create_atms(branch_ids)
            db.atms.insert_many(atms)

            # Create johndoe user
            johndoe_id = ObjectId()
            db.customers.insert_one({
                '_id': johndoe_id,
                'username': 'johndoe',
                'password': scrypt.hash('password123'),
                'email': 'johndoe@example.com',
                'created_at': datetime.now(timezone.utc)
            })

            # Create accounts for johndoe
            checking_id = ObjectId()
            savings_id = ObjectId()
            accounts = [
                {
                    '_id': checking_id,
                    'customer_id': johndoe_id,
                    'account_type': 'Checking',
                    'balance': float('5000.00'),
                    'created_at': datetime.now(timezone.utc),
                    'branch_id': random.choice(branch_ids)
                },
                {
                    '_id': savings_id,
                    'customer_id': johndoe_id,
                    'account_type': 'Savings',
                    'balance': float('10000.00'),
                    'created_at': datetime.now(timezone.utc),
                    'branch_id': random.choice(branch_ids)
                }
            ]
            db.accounts.insert_many(accounts)

            # Generate sample transactions
            transactions = []
            alerts = []
            current_date = datetime.now(timezone.utc) - timedelta(days=30)
            account_balances = {str(checking_id): Decimal('5000.00'), str(savings_id): Decimal('10000.00')}

            for _ in range(100):
                transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
                amount = round_to_penny(random.uniform(10, 1000))
                
                from_account = random.choice([checking_id, savings_id])
                to_account = checking_id if from_account == savings_id else savings_id

                if transaction_type in ['withdrawal', 'transfer']:
                    max_amount = account_balances[str(from_account)]
                    amount = min(amount, max_amount)

                transaction = {
                    '_id': ObjectId(),
                    'customer_id': johndoe_id,
                    'account_id': from_account if transaction_type != 'transfer' else None,
                    'type': transaction_type,
                    'amount': float(amount),
                    'timestamp': current_date,
                }

                if transaction_type == 'transfer':
                    transaction['from_account'] = from_account
                    transaction['to_account'] = to_account
                    account_balances[str(from_account)] -= amount
                    account_balances[str(to_account)] += amount
                elif transaction_type == 'deposit':
                    account_balances[str(from_account)] += amount
                else:  # withdrawal
                    account_balances[str(from_account)] -= amount

                if random.random() < 0.1:
                    fraud_type = random.choice(['velocity', 'location'])
                    transaction['fraud_flags'] = [fraud_type]
                    
                    alert = {
                        'customer_id': johndoe_id,
                        'account_id': transaction['account_id'] or transaction['from_account'],
                        'transaction_id': transaction['_id'],
                        'type': 'Potential Fraud',
                        'message': f"Suspicious activity detected: {fraud_type}",
                        'timestamp': current_date,
                        'resolved': False
                    }
                    alerts.append(alert)

                transactions.append(transaction)
                current_date += timedelta(minutes=random.randint(30, 720))

            db.transactions.insert_many(transactions)
            if alerts:
                db.alerts.insert_many(alerts)

            db.accounts.update_one({'_id': checking_id}, {'$set': {'balance': float(account_balances[str(checking_id)])}})
            db.accounts.update_one({'_id': savings_id}, {'$set': {'balance': float(account_balances[str(savings_id)])}})

            message = "MongoDB data deployed successfully"

        elif db_type == 'postgres':
            # PostgreSQL deployment
            conn = psycopg2.connect(uri)
            cur = conn.cursor()

            # Clear existing data
            cur.execute("""
                        TRUNCATE customers, branches, branch_services, branch_hours, accounts, 
                                transactions, fraud_flags, alerts, atms, atm_features CASCADE;
                    """)
                
                    # Reset sequences
            tables = ['customers', 'branches', 'accounts', 'transactions', 'alerts', 'atms']
            # for table in tables:
            #     cur.execute(f"ALTER SEQUENCE {table}_id_seq RESTART WITH 1;")
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

            # Create ATMs and features
            for i, branch_id in enumerate(branch_ids):
                for j in range(2):
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
                    atm_id = cur.fetchone()[0]
                    features = ["Cash Withdrawal", "Deposit", "Check Cashing"]
                    cur.executemany("INSERT INTO atm_features (atm_id, feature) VALUES (%s, %s)",
                                    [(atm_id, feature) for feature in features])

            # Create johndoe user and accounts
            cur.execute("""
                INSERT INTO customers (username, password, email, created_at)
                VALUES (%s, %s, %s, %s)
                RETURNING id;
            """, ('johndoe', scrypt.hash('password123'), 'johndoe@example.com', datetime.now(timezone.utc)))
            johndoe_id = cur.fetchone()[0]

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

            for _ in range(100):
                transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
                amount = round_to_penny(random.uniform(10, 1000))
                
                from_account = random.choice([checking_id, savings_id])
                to_account = checking_id if from_account == savings_id else savings_id

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

                if random.random() < 0.1:
                    fraud_type = random.choice(['velocity', 'location'])
                    cur.execute("INSERT INTO fraud_flags (transaction_id, flag) VALUES (%s, %s)", 
                                (transaction_id, fraud_type))
                    
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

                current_date += timedelta(minutes=random.randint(30, 720))

            # Update final account balances
            cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (float(account_balances[checking_id]), checking_id))
            cur.execute("UPDATE accounts SET balance = %s WHERE id = %s", (float(account_balances[savings_id]), savings_id))

            conn.commit()
            cur.close()
            conn.close()

            message = "PostgreSQL data deployed successfully"

        else:
            return jsonify({'error': 'Invalid database type'}), 400

        return jsonify({'message': message}), 200

    except Exception as e:
        app.logger.error(f"Error deploying data: {str(e)}")
        return jsonify({'error': 'An error occurred while deploying data'}), 500

if __name__ == '__main__':
    app.run(debug=True)
