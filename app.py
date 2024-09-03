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

from urllib.parse import urlparse, urlunsplit
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

# Setup for original MongoDB
parsed_uri = urlparse(app.config['MONGO_URI'])
db_name = parsed_uri.path.lstrip('/').split('?')[0] or 'mongodbank'

# Reconstruct the URI with the correct database name
normalized_uri = urlunsplit((
    parsed_uri.scheme,
    parsed_uri.netloc,
    f'/{db_name}',
    parsed_uri.query,
    parsed_uri.fragment
))

app.config['MONGO_URI'] = normalized_uri

mongo = PyMongo(app)
client = MongoClient(app.config['MONGO_URI'])
db = client[db_name]

# Setup for normalized MongoDB
normalized_parsed_uri = urlparse(app.config['MONGO_NORMALIZED_URI'])
normalized_db_name = normalized_parsed_uri.path.lstrip('/').split('?')[0] or 'mongodbank_normalized'
app.config['MONGO_NORMALIZED_URI'] = f"{normalized_parsed_uri.scheme}://{normalized_parsed_uri.netloc}/{normalized_db_name}"

normalized_client = MongoClient(app.config['MONGO_NORMALIZED_URI'])
normalized_db = normalized_client[normalized_db_name]

print(f"Connected to original database: {db_name}")
print(f"Connected to normalized database: {normalized_db_name}")

def round_to_penny(amount):
    return Decimal(amount).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

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

    # Clear data from both MongoDB databases
    for collection in db.list_collection_names():
        db[collection].delete_many({})
    
    for collection in normalized_db.list_collection_names():
        normalized_db[collection].delete_many({})

def create_branches():
    branches = []
    for i in range(5):
        branches.append((
            f'Branch {i+1}',
            f'{100+i} Main St',
            'Anytown',
            'ST',
            f'1000{i}',
            'USA',
            f'555-000-000{i}',
            f'branch{i+1}@mongodbank.com',
            f'Manager {i+1}',
            random.uniform(25, 48),
            random.uniform(-122, -71)
        ))
    return branches

def deploy_database(uri):
    conn = None
    try:
        conn = psycopg2.connect(uri)
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cur = conn.cursor()

        print("Creating tables...")

        # Create customers table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
        """)

        # Create branches table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS branches (
                id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                street VARCHAR(255) NOT NULL,
                city VARCHAR(100) NOT NULL,
                state VARCHAR(50) NOT NULL,
                zip_code VARCHAR(20) NOT NULL,
                country VARCHAR(50) NOT NULL,
                phone_number VARCHAR(20) NOT NULL,
                email VARCHAR(100) NOT NULL,
                manager VARCHAR(100) NOT NULL,
                latitude DECIMAL(10, 8) NOT NULL,
                longitude DECIMAL(11, 8) NOT NULL
            )
        """)

        # Create accounts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                branch_id INTEGER REFERENCES branches(id),
                account_type VARCHAR(50) NOT NULL,
                balance NUMERIC(10, 2) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL
            )
        """)

        # Create transactions table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                account_id INTEGER REFERENCES accounts(id),
                type VARCHAR(50) NOT NULL,
                amount NUMERIC(10, 2) NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                from_account_id INTEGER REFERENCES accounts(id),
                to_account_id INTEGER REFERENCES accounts(id)
            )
        """)

        # Create alerts table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id SERIAL PRIMARY KEY,
                customer_id INTEGER REFERENCES customers(id),
                account_id INTEGER REFERENCES accounts(id),
                transaction_id INTEGER REFERENCES transactions(id),
                type VARCHAR(50) NOT NULL,
                message TEXT NOT NULL,
                timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
                resolved BOOLEAN NOT NULL
            )
        """)

        # Create ATMs table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atms (
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
            )
        """)

        # Create branch_services table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS branch_services (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES branches(id),
                service VARCHAR(100) NOT NULL
            )
        """)

        # Create branch_hours table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS branch_hours (
                id SERIAL PRIMARY KEY,
                branch_id INTEGER REFERENCES branches(id),
                day_of_week VARCHAR(10) NOT NULL,
                open_time TIME NOT NULL,
                close_time TIME NOT NULL
            )
        """)

        # Create atm_features table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atm_features (
                id SERIAL PRIMARY KEY,
                atm_id INTEGER REFERENCES atms(id),
                feature VARCHAR(100) NOT NULL
            )
        """)

        # Create fraud_flags table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS fraud_flags (
                id SERIAL PRIMARY KEY,
                transaction_id INTEGER REFERENCES transactions(id),
                flag VARCHAR(50) NOT NULL
            )
        """)

        print("Tables created successfully")

        print("Inserting sample data...")

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

        print("Sample data inserted successfully")
        print("Database deployment process completed")
        return "Database deployment process completed"

    except Exception as e:
        print(f"Unexpected error: {e}")
        return f"Unexpected error: {e}"
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()

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
    
    # Original MongoDB query
    original_start = time.time()
    original_results = perform_query(db, query_type)
    original_end = time.time()
    original_time = original_end - original_start

    # Normalized MongoDB query
    normalized_start = time.time()
    normalized_results = perform_query(normalized_db, query_type)
    normalized_end = time.time()
    normalized_time = normalized_end - normalized_start
    
    performance_gain = original_time / normalized_time if normalized_time > 0 and original_time > 0 else 0
    
    return jsonify({
        'original_time': round(original_time * 1000, 2),
        'normalized_time': round(normalized_time * 1000, 2),
        'performance_gain': round(performance_gain, 2),
        'original_results': len(original_results),
        'normalized_results': len(normalized_results)
    })

def perform_query(db, query_type):
    if query_type == 'account_details':
        return list(db.accounts.aggregate([
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
        return list(db.customers.aggregate([
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
        return list(db.transactions.aggregate([
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
    else:
        return []
    
def reset_data():
    try:
        # Clear data from both MongoDB databases
        for collection in db.list_collection_names():
            db[collection].delete_many({})
        
        for collection in normalized_db.list_collection_names():
            normalized_db[collection].delete_many({})
        
        return "Data reset completed successfully for both databases."
    except Exception as e:
        app.logger.error(f"Error in reset_data: {str(e)}")
        return f"An error occurred during data reset: {str(e)}"

def deploy_data():
    try:
        # Create branches
        branches = create_branches()
        branch_ids = []
        for branch in branches:
            branch_doc = {
                "name": branch[0],
                "street": branch[1],
                "city": branch[2],
                "state": branch[3],
                "zip_code": branch[4],
                "country": branch[5],
                "phone_number": branch[6],
                "email": branch[7],
                "manager": branch[8],
                "latitude": branch[9],
                "longitude": branch[10]
            }
            result = normalized_db.branches.insert_one(branch_doc)
            branch_id = result.inserted_id
            branch_ids.append(branch_id)
            
            # Create branch services
            services = ["Loans", "Deposits", "Wealth Management"]
            for service in services:
                normalized_db.branch_services.insert_one({
                    "branch_id": branch_id,
                    "service": service
                })
            
            # Create branch hours
            hours = [
                ("monday", "09:00", "17:00"),
                ("tuesday", "09:00", "17:00"),
                ("wednesday", "09:00", "17:00"),
                ("thursday", "09:00", "17:00"),
                ("friday", "09:00", "17:00"),
                ("saturday", "10:00", "14:00")
            ]
            for day, open_time, close_time in hours:
                normalized_db.branch_hours.insert_one({
                    "branch_id": branch_id,
                    "day_of_week": day,
                    "open_time": open_time,
                    "close_time": close_time
                })

        # Create ATMs
        for i, branch_id in enumerate(branch_ids):
            for j in range(2):  # 2 ATMs per branch
                atm_doc = {
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
                    "accessibility": random.choice([True, False])
                }
                atm_result = normalized_db.atms.insert_one(atm_doc)
                atm_id = atm_result.inserted_id
                
                # Create ATM features
                features = ["Cash Withdrawal", "Deposit", "Check Cashing"]
                for feature in features:
                    normalized_db.atm_features.insert_one({
                        "atm_id": atm_id,
                        "feature": feature
                    })

        # Create johndoe user
        johndoe_doc = {
            "username": "johndoe",
            "password": scrypt.hash("password123"),
            "email": "johndoe@example.com",
            "created_at": datetime.now(timezone.utc),
            "is_admin": False
        }
        johndoe_id = normalized_db.customers.insert_one(johndoe_doc).inserted_id

        # Create accounts for johndoe
        accounts = [
            {
                "customer_id": johndoe_id,
                "branch_id": random.choice(branch_ids),
                "account_type": "Checking",
                "balance": 5000.00,
                "created_at": datetime.now(timezone.utc)
            },
            {
                "customer_id": johndoe_id,
                "branch_id": random.choice(branch_ids),
                "account_type": "Savings",
                "balance": 10000.00,
                "created_at": datetime.now(timezone.utc)
            }
        ]
        
        account_ids = []
        for account in accounts:
            result = normalized_db.accounts.insert_one(account)
            account_ids.append(result.inserted_id)

        # Generate sample transactions
        current_date = datetime.now(timezone.utc) - timedelta(days=30)
        for _ in range(100):  # Generate 100 transactions over the last 30 days
            transaction_type = random.choice(['deposit', 'withdrawal', 'transfer'])
            amount = round_to_penny(random.uniform(10, 1000))
            
            from_account = random.choice(account_ids)
            to_account = account_ids[0] if from_account == account_ids[1] else account_ids[1]

            transaction_doc = {
                "account_id": from_account if transaction_type != 'transfer' else None,
                "type": transaction_type,
                "amount": float(amount),
                "timestamp": current_date,
                "from_account_id": from_account if transaction_type in ['withdrawal', 'transfer'] else None,
                "to_account_id": to_account if transaction_type == 'transfer' else None,
                "location_latitude": random.uniform(25, 48),
                "location_longitude": random.uniform(-122, -71)
            }

            result = normalized_db.transactions.insert_one(transaction_doc)

            # Randomly add fraud flags
            if random.random() < 0.1:  # 10% chance of fraud flag
                fraud_type = random.choice(['velocity', 'location'])
                normalized_db.fraud_flags.insert_one({
                    "transaction_id": result.inserted_id,
                    "flag": fraud_type
                })
                
                # Create an alert for this transaction
                alert_doc = {
                    "customer_id": johndoe_id,
                    "account_id": from_account if transaction_type != 'transfer' else None,
                    "transaction_id": result.inserted_id,
                    "type": 'Potential Fraud',
                    "message": f"Suspicious activity detected: {fraud_type}",
                    "timestamp": current_date,
                    "resolved": False
                }
                normalized_db.alerts.insert_one(alert_doc)

            current_date += timedelta(minutes=random.randint(30, 720))  # 0.5 to 12 hours between transactions

        return "Data deployment completed successfully for the normalized database."
    except Exception as e:
        app.logger.error(f"Error in deploy_data: {str(e)}")
        return f"An error occurred during data deployment: {str(e)}"

@app.route('/admin/deploy_data', methods=['POST'])
def admin_deploy_data():
    try:
        result = deploy_data()
        return jsonify({"message": result}), 200
    except Exception as e:
        app.logger.error(f"Error in admin_deploy_data: {str(e)}")
        return jsonify({"error": str(e)}), 500

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

if __name__ == '__main__':
    app.run(debug=True)
