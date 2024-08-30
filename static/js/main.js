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


    const statementForm = document.getElementById('statement-form');
    const downloadPdfButton = document.createElement('button');
    downloadPdfButton.type = 'button';
    downloadPdfButton.id = 'download-pdf';
    downloadPdfButton.className = 'btn btn-info mt-2';
    downloadPdfButton.innerHTML = '<i class="fas fa-file-pdf"></i> Download PDF';
    downloadPdfButton.style.display = 'none';

    // Insert the download button after the form
    statementForm.parentNode.insertBefore(downloadPdfButton, statementForm.nextSibling);

    statementForm.addEventListener('submit', function (e) {
        e.preventDefault();

        const accountId = document.getElementById('statement-account-select').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        fetch(`/api/statement?account_id=${accountId}&start_date=${startDate}&end_date=${endDate}`)
        .then(response => response.json())
        .then(data => {
            console.log("API response:", data);  // Debugging line
            if (data.error) {
                alert(data.error);
            } else {
                displayStatement(data);
                downloadPdfButton.style.display = 'block';  // Show the download button
                // Store the statement parameters for PDF download
                downloadPdfButton.dataset.accountId = accountId;
                downloadPdfButton.dataset.startDate = startDate;
                downloadPdfButton.dataset.endDate = endDate;
            }
        })
        .catch(error => {
            console.error('Error generating statement:', error);
            alert('Failed to generate statement');
        });
    });

    downloadPdfButton.addEventListener('click', function() {
        const accountId = this.dataset.accountId;
        const startDate = this.dataset.startDate;
        const endDate = this.dataset.endDate;

        fetch(`/api/generate_pdf_statement?account_id=${accountId}&start_date=${startDate}&end_date=${endDate}`)
            .then(response => response.blob())
            .then(blob => {
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = `statement_${startDate}_to_${endDate}.pdf`;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
            })
            .catch(error => {
                console.error('Error downloading PDF:', error);
                alert('Failed to download PDF statement');
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

    document.getElementById('statement-form').addEventListener('submit', function (e) {
        e.preventDefault();

        const accountId = document.getElementById('statement-account-select').value;
        const startDate = document.getElementById('start-date').value;
        const endDate = document.getElementById('end-date').value;

        fetch(`/api/statement?account_id=${accountId}&start_date=${startDate}&end_date=${endDate}`)
        .then(response => response.json())
        .then(data => {
            console.log("API response:", data);  // Debugging line
            if (data.error) {
                alert(data.error);
            } else {
                displayStatement(data);
            }
        })
        .catch(error => {
            console.error('Error generating statement:', error);
            alert('Failed to generate statement');
        });
    });

    function displayStatement(data) {
        console.log("Received statement data:", data);  // Debugging line

        const statementResultDiv = document.getElementById('statement-result');
        statementResultDiv.innerHTML = `
            <h3>${data.account_type} Statement</h3>
            <p><strong>Balance:</strong> $${data.balance.toFixed(2)}</p>
            <p><strong>Period:</strong> ${new Date(data.start_date).toLocaleDateString()} to ${new Date(data.end_date).toLocaleDateString()}</p>
            <table class="table table-striped">
                <thead>
                    <tr>
                        <th>Date</th>
                        <th>Type</th>
                        <th>Amount</th>
                        <th>From Account</th>
                        <th>To Account</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.transactions.map(transaction => `
                        <tr>
                            <td>${new Date(transaction.timestamp).toLocaleString()}</td>
                            <td>${transaction.type}</td>
                            <td>$${transaction.amount}</td>
                            <td>${transaction.from_account_name || '-'}</td>
                            <td>${transaction.to_account_name || '-'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;

        if (data.transactions.length === 0) {
            console.warn("No transactions found for the specified period.");
            statementResultDiv.innerHTML += `<p>No transactions found for the specified period.</p>`;
        }
    }
});