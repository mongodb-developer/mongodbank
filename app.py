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
    "password": "hashed_password"
}

# Account Document
{
    "_id": ObjectId("..."),
    "customer_id": ObjectId("..."),
    "account_type": "Checking",
    "balance": 1000.00
}

# Transaction Document
{
    "_id": ObjectId("..."),
    "account_id": ObjectId("..."),
    "amount": 500.00,
    "type": "deposit",
    "timestamp": ISODate("2023-08-28T12:00:00Z")
}
''',
            'description': 'This represents the data model for the application, defining the structure of customer, account, and transaction documents.',
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

    try:
        # Clear existing data
        mongo.db.customers.delete_many({})
        mongo.db.accounts.delete_many({})
        mongo.db.transactions.delete_many({})
        mongo.db.alerts.delete_many({})

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
                'created_at': datetime.now(timezone.utc)
            },
            {
                '_id': savings_id,
                'customer_id': johndoe_id,
                'account_type': 'Savings',
                'balance': float('10000.00'),
                'created_at': datetime.now(timezone.utc)
            }
        ]
        mongo.db.accounts.insert_many(accounts)

        # Generate sample transactions
        transactions = []
        alerts = []
        current_date = datetime.now(timezone.utc) - timedelta(days=30)
        account_balances = {str(checking_id): Decimal('5000.00'), str(savings_id): Decimal('10000.00')}

        def round_to_penny(amount):
            return Decimal(amount).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)

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

        return jsonify({'message': 'Data reset successful. Sample data generated for johndoe user.'}), 200

    except Exception as e:
        app.logger.error(f"Error resetting data: {str(e)}")
        return jsonify({'error': 'An error occurred while resetting data'}), 500
@app.route('/admin/deploy_data', methods=['POST'])
def deploy_data():
    if 'admin_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    target_uri = request.form.get('target_uri')
    if not target_uri:
        return jsonify({'error': 'No target URI provided'}), 400

    try:
        # Connect to the target database
        target_client = MongoClient(target_uri)
        target_db = target_client.get_default_database()

        # Connect to the source database
        source_client = MongoClient(os.getenv('MONGO_URI'))
        source_db = source_client.get_default_database()

        # Collections to copy
        collections = ['customers', 'accounts', 'transactions', 'alerts']

        for collection_name in collections:
            # Clear existing data in target collection
            target_db[collection_name].delete_many({})

            # Copy data from source to target
            documents = list(source_db[collection_name].find())
            if documents:
                target_db[collection_name].insert_many(documents)

        return jsonify({'message': 'Data successfully deployed to target database'}), 200

    except Exception as e:
        app.logger.error(f"Error deploying data: {str(e)}")
        return jsonify({'error': 'An error occurred while deploying data'}), 500

    finally:
        if 'target_client' in locals():
            target_client.close()
        if 'source_client' in locals():
            source_client.close()

if __name__ == '__main__':
    app.run(debug=True)
