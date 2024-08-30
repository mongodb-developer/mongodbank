document.addEventListener('DOMContentLoaded', function () {
    const accountSelect = document.getElementById('account-select');
    const transactionsList = document.getElementById('transactions-list');
    const transactionForm = document.getElementById('transaction-form');
    const transferForm = document.getElementById('transfer-form');
    let currentPage = 1;
    const pageInfo = document.getElementById('page-info');
    const prevPageButton = document.getElementById('prev-page');
    const nextPageButton = document.getElementById('next-page');
    const limit = 10; 
    const balanceChartCtx = document.getElementById('balanceChart').getContext('2d');
    let balanceChart;


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
    
                    const transactionItem = `
                        <div class="accordion-item">
                            <h2 class="accordion-header" id="heading-${index}">
                                <button class="accordion-button ${index > 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse-${index}" aria-expanded="${index === 0}" aria-controls="collapse-${index}">
                                    ${transaction.type}: $${transaction.amount} <small class="text-muted ms-3">${new Date(transaction.timestamp).toLocaleString()}</small>
                                    ${fraudFlag ? '<span class="badge bg-danger ms-auto">Fraud Detected</span>' : ''}
                                </button>
                            </h2>
                            <div id="collapse-${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" aria-labelledby="heading-${index}" data-bs-parent="#transactions-accordion">
                                <div class="accordion-body">
                                    <table class="table table-striped">
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
    }
    
    
    
    

    if (accountSelect) {
        accountSelect.addEventListener('change', function () {
            currentPage = 1;  // Reset to page 1 when account changes
            loadTransactions(accountSelect.value, currentPage, limit);
        });
        loadTransactions(accountSelect.value, currentPage, limit);
    }

    if (transactionForm) {
        transactionForm.addEventListener('submit', function(e) {
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
        transferForm.addEventListener('submit', function(e) {
            e.preventDefault();
    
            const sourceAccountId = document.getElementById('source-account').value;
            const destinationAccountId = document.getElementById('destination-account').value;
            const amount = parseFloat(document.getElementById('transfer-amount').value);
    
            console.log("Source Account ID:", sourceAccountId);
            console.log("Destination Account ID:", destinationAccountId);
            console.log("Amount:", amount);
    
            fetch('/transfer', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    source_account_id: sourceAccountId,
                    destination_account_id: destinationAccountId,
                    amount: amount
                }),
            })
            .then(response => response.json())
            .then(data => {
                if (data.error) {
                    alert('Error: ' + data.error);
                } else {
                    alert('Transfer successful!');
                    // Refresh the UI to show the updated balances
                    updateAccountBalances(sourceAccountId, destinationAccountId);
                    loadTransactions(sourceAccountId);
                    loadTransactions(destinationAccountId);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('Transfer failed');
            });
        });
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