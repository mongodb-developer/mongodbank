import inspect
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_pymongo import PyMongo
from bson.objectid import ObjectId
from passlib.hash import scrypt
from config import Config
import datetime
from urllib.parse import urlparse
from flask import jsonify
from flask_cors import CORS
from pymongo import MongoClient, WriteConcern, ReadPreference, errors
from pymongo.read_concern import ReadConcern
import math

import logging
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

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('index'))
    user = mongo.db.customers.find_one({'_id': ObjectId(session['user_id'])})
    accounts = list(mongo.db.accounts.find({'customer_id': ObjectId(session['user_id'])}))
    return render_template('dashboard.html', user=user, accounts=accounts)

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

@app.route('/api/transactions', methods=['GET'])
def get_transactions():
    try:
        if 'user_id' not in session:
            return jsonify({'error': 'Unauthorized'}), 401

        account_id = request.args.get('account_id')
        if not account_id:
            return jsonify({'error': 'No account ID provided'}), 400

        page = int(request.args.get('page', 1))  # Default to page 1
        limit = int(request.args.get('limit', 10))  # Default to 10 items per page
        skip = (page - 1) * limit

        try:
            account_object_id = ObjectId(account_id)
        except Exception as e:
            logging.error(f"Error converting account_id to ObjectId: {e}")
            return jsonify({'error': 'Invalid account ID format'}), 400

        transactions = list(mongo.db.transactions.find({'account_id': account_object_id})
                            .sort('timestamp', -1)
                            .skip(skip)
                            .limit(limit))

        for transaction in transactions:
            transaction['_id'] = str(transaction['_id'])  # Convert _id to string
            transaction['account_id'] = str(transaction['account_id'])  # Convert account_id to string
            if 'from_account' in transaction:
                transaction['from_account'] = str(transaction['from_account'])  # Convert from_account to string
                from_account = mongo.db.accounts.find_one({"_id": ObjectId(transaction['from_account'])})
                if from_account:
                    transaction['from_account_name'] = from_account['account_type']
            if 'to_account' in transaction:
                transaction['to_account'] = str(transaction['to_account'])  # Convert to_account to string
                to_account = mongo.db.accounts.find_one({"_id": ObjectId(transaction['to_account'])})
                if to_account:
                    transaction['to_account_name'] = to_account['account_type']
            if isinstance(transaction['timestamp'], datetime.datetime):
                transaction['timestamp'] = transaction['timestamp'].isoformat()

        total_transactions = mongo.db.transactions.count_documents({'account_id': account_object_id})
        total_pages = (total_transactions + limit - 1) // limit  # Calculate total pages

        return jsonify({
            'transactions': transactions,
            'page': page,
            'total_pages': total_pages
        })

    except Exception as e:
        logging.error(f"Error in get_transactions: {e}")
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
    timestamp = datetime.datetime.now(datetime.UTC)
    
    # Initialize fraud flags
    fraud_flags = []

    # Velocity Check
    if fraud_check == 'velocity':
        velocity_count = db.transactions.count_documents({
            'account_id': ObjectId(account_id),
            'timestamp': {'$gte': timestamp - datetime.timedelta(hours=1)}
        })
        if velocity_count > 10:  # Example threshold
            fraud_flags.append('velocity')

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

    try:
        with client.start_session() as session:
            with session.start_transaction():
                # Step 1: Debit from source account
                source_account = db.accounts.find_one_and_update(
                    {"_id": ObjectId(source_account_id), "balance": {"$gte": amount}},
                    {"$inc": {"balance": -amount}},
                    session=session,
                    return_document=True
                )
                if not source_account:
                    raise errors.OperationFailure("Insufficient funds in source account")

                # Step 2: Credit to destination account
                destination_account = db.accounts.find_one_and_update(
                    {"_id": ObjectId(destination_account_id)},
                    {"$inc": {"balance": amount}},
                    session=session,
                    return_document=True
                )

                if not destination_account:
                    raise errors.OperationFailure("Destination account not found")

                # Step 3: Record transaction in the source account
                source_transaction = {
                    "account_id": ObjectId(source_account_id),
                    "amount": -amount,
                    "type": "transfer_out",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "from_account": ObjectId(source_account_id),
                    "to_account": ObjectId(destination_account_id)
                }
                db.transactions.insert_one(source_transaction, session=session)

                # Step 4: Record transaction in the destination account
                destination_transaction = {
                    "account_id": ObjectId(destination_account_id),
                    "amount": amount,
                    "type": "transfer_in",
                    "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    "from_account": ObjectId(source_account_id),
                    "to_account": ObjectId(destination_account_id)
                }
                db.transactions.insert_one(destination_transaction, session=session)

        return jsonify({"status": "Transfer successful"}), 200
    except errors.OperationFailure as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
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

if __name__ == '__main__':
    app.run(debug=True)
