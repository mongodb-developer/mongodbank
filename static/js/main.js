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

    function loadTransactions(accountId) {
        fetch(`/api/transactions?account_id=${accountId}`)
            .then(response => response.json())
            .then(data => {
                const transactionsAccordion = document.getElementById('transactions-accordion');
                transactionsAccordion.innerHTML = '';  // Clear existing content

                data.transactions.forEach((transaction, index) => {
                    const fraudFlag = transaction.fraud_flags && transaction.fraud_flags.length > 0;
                    const accordionItem = `
                        <div class="accordion-item">
                            <h2 class="accordion-header" id="heading${index}">
                                <button class="accordion-button ${index > 0 ? 'collapsed' : ''}" type="button" data-bs-toggle="collapse" data-bs-target="#collapse${index}" aria-expanded="${index === 0}" aria-controls="collapse${index}">
                                    ${transaction.type}: $${transaction.amount} ${fraudFlag ? '<span class="badge bg-danger ms-2">Fraud Detected</span>' : ''}
                                    <small class="text-muted ms-auto">${new Date(transaction.timestamp).toLocaleString()}</small>
                                </button>
                            </h2>
                            <div id="collapse${index}" class="accordion-collapse collapse ${index === 0 ? 'show' : ''}" aria-labelledby="heading${index}" data-bs-parent="#transactions-accordion">
                                <div class="accordion-body">
                                    <p><strong>Transaction ID:</strong> ${transaction._id}</p>
                                    <p><strong>Type:</strong> ${transaction.type}</p>
                                    <p><strong>Amount:</strong> $${transaction.amount}</p>
                                    <p><strong>Date:</strong> ${new Date(transaction.timestamp).toLocaleString()}</p>
                                    <p><strong>Account ID:</strong> ${transaction.account_id}</p>
                                    ${transaction.from_account_name ? `<p><strong>From Account:</strong> ${transaction.from_account_name}</p>` : ''}
                                    ${transaction.to_account_name ? `<p><strong>To Account:</strong> ${transaction.to_account_name}</p>` : ''}
                                    ${fraudFlag ? `<p><strong>Fraud Detected:</strong> ${transaction.fraud_flags.join(', ')}</p>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                    transactionsAccordion.innerHTML += accordionItem;
                });
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