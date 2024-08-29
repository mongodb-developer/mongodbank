// Define simulateVelocityCheck globally
function simulateVelocityCheck() {
    const accountId = document.getElementById('account-id-velocity').value;
    const amount = document.getElementById('transaction-amount-velocity').value;
    const numberOfTransactions = 4; // Number of transactions to simulate
    const delay = 5000; // 5 seconds delay between transactions

    for (let i = 0; i < numberOfTransactions; i++) {
        setTimeout(() => {
            performTransaction(accountId, amount, 'velocity');
        }, i * delay);
    }
}

// Define the cities object globally
const cities = {
    "New York, NY, USA": { lat: 40.7128, lon: -74.0060 },
    "Los Angeles, CA, USA": { lat: 34.0522, lon: -118.2437 },
    "London, England, UK": { lat: 51.5074, lon: -0.1278 },
    "Tokyo, Japan": { lat: 35.6895, lon: 139.6917 },
    "Sydney, Australia": { lat: -33.8688, lon: 151.2093 }
};

// Function to simulate a location check
function simulateLocationCheck() {
    const accountId = document.getElementById('account-id-location').value;
    const amount = document.getElementById('transaction-amount-location').value;
    const city = document.getElementById('city-location').value;

    if (!city || !cities[city]) {
        showError("Please select a valid city.");
        return;
    }

    const { lat, lon } = cities[city];

    performTransaction(accountId, amount, 'location', { latitude: lat, longitude: lon });
}


// Function to show an error message
function showError(message) {
    const errorMessageDiv = document.getElementById('error-message');
    errorMessageDiv.textContent = message;
    errorMessageDiv.classList.remove('d-none');
}

// Function to clear the error message
function clearError() {
    const errorMessageDiv = document.getElementById('error-message');
    errorMessageDiv.textContent = '';
    errorMessageDiv.classList.add('d-none');
}

// Function to show a fraud warning
function showFraudWarning(message) {
    const fraudWarningDiv = document.getElementById('fraud-warning');
    fraudWarningDiv.textContent = message;
    fraudWarningDiv.classList.remove('d-none');
}

// Function to clear the fraud warning
function clearFraudWarning() {
    const fraudWarningDiv = document.getElementById('fraud-warning');
    fraudWarningDiv.textContent = '';
    fraudWarningDiv.classList.add('d-none');
}

function clearFraudWarning() {
    const fraudWarningDiv = document.getElementById('fraud-warning');
    fraudWarningDiv.textContent = '';
    fraudWarningDiv.classList.add('d-none');
}
function performTransaction(accountId, amount, fraudCheck, location = null) {
    const payload = {
        account_id: accountId,
        type: 'withdrawal',  // Set transaction type to withdrawal
        amount: parseFloat(amount),
        fraud_check: fraudCheck,
        location: location
    };

    fetch('/api/transaction', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
    })
    .then(response => response.json())
    .then(data => {
        clearFraudWarning();
        if (data.error) {
            showError(data.error);
        } else {
            let message = 'Transaction successful';
            if (data.fraud_flags && data.fraud_flags.length > 0) {
                message += `\nFraud checks triggered: ${data.fraud_flags.join(', ')}`;
                showFraudWarning('Warning: Fraud detection triggered! Please review the transaction details.');
            }
            // Update the UI based on the response
            loadTransactions(accountId);
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showError('Transaction failed');
    });
}

function loadTransactions(accountId) {
    fetch(`/api/transactions?account_id=${accountId}`)
        .then(response => response.json())
        .then(transactions => {
            const transactionsList = document.getElementById('transactions-list');
            transactionsList.innerHTML = transactions.map(transaction => {
                let fraudFlag = transaction.fraud_flags && transaction.fraud_flags.length > 0;
                return `
                    <li class="list-group-item d-flex justify-content-between align-items-center rounded ${fraudFlag ? 'bg-warning' : ''}">
                        ${transaction.type}: $${transaction.amount}
                        ${fraudFlag ? '<span class="badge bg-danger">Fraud Detected</span>' : ''}
                        <small class="text-muted">${new Date(transaction.timestamp).toLocaleString()}</small>
                    </li>
                `;
            }).join('');
        });
}

document.addEventListener('DOMContentLoaded', function () {

    const errorMessageDiv = document.getElementById('error-message');

    const velocityForm = document.getElementById('velocity-simulation-form');
    if (velocityForm) {
        velocityForm.addEventListener('submit', function (e) {
            e.preventDefault();
            clearError();
            simulateVelocityCheck();
        });
    }

    const locationForm = document.getElementById('location-simulation-form');
    if (locationForm) {
        locationForm.addEventListener('submit', function (e) {
            e.preventDefault();
            clearError();
            simulateLocationCheck();
        });
    }

});
