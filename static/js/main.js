const balanceChartCtx = document.getElementById('balanceChart').getContext('2d');
let balanceChart;
const accountSelect = document.getElementById('account-select');
let currentPage = 1;
const limit = 10;
const transactionsList = document.getElementById('transactions-list');
const transactionForm = document.getElementById('transaction-form');
const transferForm = document.getElementById('transfer-form');
const pageInfo = document.getElementById('page-info');
const prevPageButton = document.getElementById('prev-page');
const nextPageButton = document.getElementById('next-page');
document.addEventListener('DOMContentLoaded', function () {


    const watermarkPlugin = {
        id: 'watermark',
        beforeDraw: (chart) => {
            const ctx = chart.ctx;
            const chartArea = chart.chartArea;
            const img = new Image();
            img.src = logoUrl;  // Use the dynamically passed logo URL

            img.onload = () => {
                const imgAspectRatio = img.width / img.height;
                let imgWidth, imgHeight;

                if (chartArea.width / chartArea.height < imgAspectRatio) {
                    // Chart area is taller than the image aspect ratio, limit by width
                    imgWidth = chartArea.width * 0.5; // 50% of chart width
                    imgHeight = imgWidth / imgAspectRatio;
                } else {
                    // Chart area is wider than the image aspect ratio, limit by height
                    imgHeight = chartArea.height * 0.9; // 50% of chart height
                    imgWidth = imgHeight * imgAspectRatio;
                }

                const x = (chartArea.left + chartArea.right) / 2 - imgWidth / 2;
                const y = (chartArea.top + chartArea.bottom) / 2 - imgHeight / 2;

                ctx.save();
                ctx.globalAlpha = 0.2; // Set opacity of watermark
                ctx.drawImage(img, x, y, imgWidth, imgHeight);
                ctx.restore();
            };
        }
    };

    Chart.register(watermarkPlugin); // Register the plugin with Chart.js

    prevPageButton.addEventListener('click', function (e) {
        e.preventDefault();
        if (currentPage > 1) {
            currentPage--;
            loadTransactions(accountSelect.value, currentPage, limit);
        }
    });

    nextPageButton.addEventListener('click', function (e) {
        e.preventDefault();
        currentPage++;
        loadTransactions(accountSelect.value, currentPage, limit);
    });

    const statementForm = document.getElementById('statement-form');
    const downloadPdfButton = document.createElement('button');
    downloadPdfButton.type = 'button';
    downloadPdfButton.id = 'download-pdf';
    downloadPdfButton.className = 'btn btn-info mt-2';
    downloadPdfButton.innerHTML = '<i class="fas fa-file-pdf"></i> Download PDF';
    downloadPdfButton.style.display = 'none';

    // Insert the download button after the form
    statementForm.parentNode.insertBefore(downloadPdfButton, statementForm.nextSibling);

    // Update the statement generation code in main.js

    statementForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const accountId = document.getElementById('statement-account-select').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        fetch(`/api/statement?account_id=${accountId}&start_date=${startDate}&end_date=${endDate}`)
            .then(response => response.json())
            .then(statement => {
                if (statement.transactions && statement.transactions.length > 0) {
                    // Display the statement data
                    const statementResult = document.getElementById('statement-result');
                    statementResult.innerHTML = `
                    <h3>Statement Summary</h3>
                    <p>Account Type: ${statement.account_type || 'N/A'}</p>
                    <p>Balance: $${statement.balance !== undefined ? statement.balance.toFixed(2) : 'N/A'}</p>
                    <p>Period: ${statement.start_date || 'N/A'} to ${statement.end_date || 'N/A'}</p>
                    <h4>Transactions</h4>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Date</th>
                                <th>Type</th>
                                <th>Amount</th>
                                <th>Fraud Flags</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${statement.transactions.map(transaction => `
                                <tr>
                                    <td>${transaction.timestamp ? new Date(transaction.timestamp).toLocaleDateString() : 'N/A'}</td>
                                    <td>${transaction.type || 'N/A'}</td>
                                    <td>$${transaction.amount !== undefined ? transaction.amount.toFixed(2) : 'N/A'}</td>
                                    <td>${transaction.fraud_flags && transaction.fraud_flags.length ? transaction.fraud_flags.join(', ') : 'None'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                `;

                    // Show the download button
                    downloadPdfButton.style.display = 'block';
                } else {
                    alert('No transactions found for the specified period.');
                    downloadPdfButton.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error generating statement:', error);
                alert('Failed to generate statement. Please check the console for more details.');
            });
    });

    if (accountSelect) {
        accountSelect.addEventListener('change', function () {
            currentPage = 1;  // Reset to page 1 when account changes
            loadTransactions(accountSelect.value, currentPage, limit);
        });
        loadTransactions(accountSelect.value, currentPage, limit);
    }

    if (transactionForm) {
        transactionForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const accountId = document.getElementById('account-select').value;
            const type = document.getElementById('transaction-type').value;
            const amount = document.getElementById('transaction-amount').value;
            const fraudCheck = document.getElementById('fraud-check').value;  // Get fraud check type

            fetch('/api/transaction', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ account_id: accountId, type, amount, fraud_check: fraudCheck }),
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        alert(data.error);
                    } else {
                        alert('Transaction successful');
                        if (data.fraud_flags.length > 0) {
                            alert('Fraud checks triggered: ' + data.fraud_flags.join(', '));
                        }
                        loadTransactions(accountId);
                        // Update account balance
                        const accountItem = document.querySelector(`#account-select option[value="${accountId}"]`);
                        if (accountItem) {
                            accountItem.textContent = `${accountItem.textContent.split('-')[0]} - $${data.new_balance.toFixed(2)}`;
                        }
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    alert('Transaction failed');
                });
        });
    }

    if (transferForm) {
        transferForm.addEventListener('submit', function (e) {
            e.preventDefault();

            const sourceAccountId = document.getElementById('source-account').value;
            const destinationAccountId = document.getElementById('destination-account').value;
            const amount = document.getElementById('transfer-amount').value;
            const simulateFailure = document.getElementById('simulate-failure').checked;

            fetch('/transfer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    source_account_id: sourceAccountId,
                    destination_account_id: destinationAccountId,
                    amount: amount,
                    simulate_failure: simulateFailure
                }),
            })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        showTransactionFailureModal(data.error, sourceAccountId, destinationAccountId, amount);
                    } else {
                        alert('Transfer successful!');
                        loadTransactions(sourceAccountId);
                        loadTransactions(destinationAccountId);
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showTransactionFailureModal('An unexpected error occurred', sourceAccountId, destinationAccountId, amount);
                });
        });
    }

    function showTransactionFailureModal(reason, sourceAccountId, destinationAccountId, amount) {
        document.getElementById('failure-reason').textContent = reason;
        document.getElementById('failure-source-account-id').textContent = sourceAccountId;
        document.getElementById('failure-destination-account-id').textContent = destinationAccountId;
        document.getElementById('failure-amount').textContent = `$${amount}`;

        const codeExample = `
# Example Code:
source_account_id = "${sourceAccountId}"
destination_account_id = "${destinationAccountId}"
amount = ${amount}

try:
    with client.start_session() as session:
        with session.start_transaction():
            # Debit from source account
            source_account = db.accounts.find_one_and_update(
                {"_id": ObjectId(source_account_id), "balance": {"$gte": amount}},
                {"$inc": {"balance": -amount}},
                session=session
            )
            if not source_account:
                raise errors.OperationFailure("Insufficient funds in source account")

            # Credit to destination account
            destination_account = db.accounts.find_one_and_update(
                {"_id": ObjectId(destination_account_id)},
                {"$inc": {"balance": amount}},
                session=session
            )
            if not destination_account:
                raise errors.OperationFailure("Destination account not found")
            
            session.commit_transaction()

except Exception as e:
    session.abort_transaction()
    print(f"Error: {e}")
`;

        document.getElementById('failure-code-example').textContent = codeExample;

        const transactionFailureModal = new bootstrap.Modal(document.getElementById('transactionFailureModal'));
        transactionFailureModal.show();
    }

    function updateAccountBalances(sourceAccountId, destinationAccountId) {
        // Fetch and update the source account balance
        fetch(`/api/accounts/${sourceAccountId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error fetching source account: ${response.statusText}`);
                }
                return response.json();
            })
            .then(account => {
                document.querySelector(`#source-account [value="${sourceAccountId}"]`).textContent = `${account.account_type} - $${account.balance.toFixed(2)}`;
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to update source account balance.');
            });

        // Fetch and update the destination account balance
        fetch(`/api/accounts/${destinationAccountId}`)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`Error fetching destination account: ${response.statusText}`);
                }
                return response.json();
            })
            .then(account => {
                document.querySelector(`#destination-account [value="${destinationAccountId}"]`).textContent = `${account.account_type} - $${account.balance.toFixed(2)}`;
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Failed to update destination account balance.');
            });
    }
});

let currentTransactionId = null;

function openReviewModal(transactionId) {
    currentTransactionId = transactionId;
    fetch(`/api/transaction/${transactionId}`)
        .then(response => response.json())
        .then(data => {
            const details = `
                    <strong>Type:</strong> ${data.type} <br>
                    <strong>Amount:</strong> $${data.amount} <br>
                    <strong>Date:</strong> ${new Date(data.timestamp).toLocaleString()} <br>
                    ${data.from_account_name ? `<strong>From Account:</strong> ${data.from_account_name} <br>` : ''}
                    ${data.to_account_name ? `<strong>To Account:</strong> ${data.to_account_name} <br>` : ''}
                `;
            document.getElementById('fraud-transaction-details').innerHTML = details;
            const fraudModal = new bootstrap.Modal(document.getElementById('reviewFraudModal'));
            fraudModal.show();
        })
        .catch(error => {
            console.error('Error loading transaction details:', error);
        });
}

function submitReview(status) {
    if (!currentTransactionId) return;

    fetch('/api/review_transaction', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ transaction_id: currentTransactionId, review_status: status }),
    })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                const fraudModal = bootstrap.Modal.getInstance(document.getElementById('reviewFraudModal'));
                fraudModal.hide();
                loadTransactions(accountSelect.value, currentPage, limit);
                alert(`Transaction marked as ${status}`);
            } else {
                alert('Failed to review transaction');
            }
        })
        .catch(error => {
            console.error('Error reviewing transaction:', error);
            alert('Failed to review transaction');
        });
}

function loadTransactions(accountId, page = 1) {
    fetch(`/api/transactions?account_id=${accountId}&page=${page}`)
        .then(response => response.json())
        .then(data => {
            const transactions = data.transactions;
            const labels = transactions.map(transaction => new Date(transaction.timestamp).toLocaleDateString());

            const transactionsAccordion = document.getElementById('transactions-accordion');
            transactionsAccordion.innerHTML = ''; // Clear existing content
            const balances = transactions.reduce((acc, transaction) => {
                const lastBalance = acc.length ? acc[acc.length - 1] : transaction.amount;
                const newBalance = transaction.type === 'deposit'
                    ? lastBalance + transaction.amount
                    : lastBalance - transaction.amount;
                acc.push(newBalance);
                return acc;
            }, []);

            if (balanceChart) {
                balanceChart.destroy(); // Destroy the old chart before creating a new one
            }

            balanceChart = new Chart(balanceChartCtx, {
                type: 'line',
                data: {
                    labels: labels.reverse(),
                    datasets: [{
                        label: 'Account Balance Over Time',
                        data: balances.reverse(),
                        fill: false,
                        borderColor: 'rgba(0, 168, 64, 0.7)',
                        tension: 0.1
                    }]
                },
                options: {
                    scales: {
                        x: {
                            title: {
                                display: true,
                                text: 'Date'
                            }
                        },
                        y: {
                            title: {
                                display: true,
                                text: 'Balance ($)'
                            }
                        }
                    }
                }
            });
            data.transactions.forEach((transaction, index) => {
                const fraudFlag = transaction.fraud_flags && transaction.fraud_flags.length > 0;
                const fraudBadge = fraudFlag 
                    ? '<span class="badge bg-danger ms-2">Potential Fraud</span>' 
                    : '';
                const transactionItem = `
                    <div class="accordion-item">
                        <h2 class="accordion-header" id="heading-${index}">
                            <button class="accordion-button ${index > 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${index}" aria-expanded="${index === 0}" aria-controls="collapse-${index}">
                                ${transaction.type}: $${transaction.amount.toFixed(2)} 
                                <small class="text-muted ms-3">${new Date(transaction.timestamp).toLocaleString()}</small>
                                ${fraudBadge}
                            </button>
                        </h2>
                        <div id="collapse-${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" aria-labelledby="heading-${index}" data-bs-parent="#transactions-accordion">
                            <div class="accordion-body">
                                <table class="table table-striped">
                                    <tr>
                                        <th>Transaction ID</th>
                                        <td>${transaction._id}</td>
                                    </tr>
                                    <tr>
                                        <th>Type</th>
                                        <td>${transaction.type}</td>
                                    </tr>
                                    <tr>
                                        <th>Amount</th>
                                        <td>$${transaction.amount}</td>
                                    </tr>
                                    <tr>
                                        <th>Date</th>
                                        <td>${new Date(transaction.timestamp).toLocaleString()}</td>
                                    </tr>
                                    ${transaction.from_account_name ? `
                                    <tr>
                                        <th>From Account</th>
                                        <td>${transaction.from_account_name}</td>
                                    </tr>` : ''}
                                    ${transaction.to_account_name ? `
                                    <tr>
                                        <th>To Account</th>
                                        <td>${transaction.to_account_name}</td>
                                    </tr>` : ''}
                                    ${fraudFlag ? `
                                    <tr>
                                        <th>Fraud Flags</th>
                                        <td>${transaction.fraud_flags.join(', ')}</td>
                                    </tr>
                                    <tr>
                                        <th>Action</th>
                                        <td>
                                            <button class="btn btn-warning btn-sm" onclick="openReviewModal('${transaction._id}')">Review</button>
                                        </td>
                                    </tr>` : ''}
                                </table>
                            </div>
                        </div>
                    </div>
                `;
                transactionsAccordion.innerHTML += transactionItem;
            });

            // Update pagination information
            document.getElementById('page-info').textContent = `Page ${data.page} of ${data.total_pages}`;
        })
        .catch(error => {
            console.error('Error loading transactions:', error);
            showError('Failed to load transactions.');
        });

        fetch('/api/dashboard_metrics')
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                console.error('Error fetching dashboard metrics:', data.error);
            } else {
                document.getElementById('total-balance').textContent = `$${data.total_balance.toFixed(2)}`;
                document.getElementById('recent-transaction-count').textContent = data.recent_transaction_count;
                document.getElementById('pending-review-count').textContent = data.pending_review_count;
                document.getElementById('alert-count').textContent = data.alert_count;
            }
        })
        .catch(error => {
            console.error('Error fetching dashboard metrics:', error);
        });
}

// Function to show an error message
function showError(message) {
    const errorMessageDiv = document.getElementById('error-message');
    errorMessageDiv.textContent = message;
    errorMessageDiv.classList.remove('d-none');
}