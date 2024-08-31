// static/js/admin_dashboard.js

document.addEventListener('DOMContentLoaded', function() {
    fetchDashboardMetrics();
    fetchTransactionVolume();
});

function fetchDashboardMetrics() {
    fetch('/admin/api/dashboard_metrics')
        .then(response => response.json())
        .then(data => {
            document.getElementById('total-users').textContent = data.total_users;
            document.getElementById('total-transactions').textContent = data.total_transactions;
            document.getElementById('total-accounts').textContent = data.total_accounts;

            populateTable('recent-transactions', data.recent_transactions, transaction => [
                new Date(transaction.timestamp).toLocaleString(),
                `$${transaction.amount.toFixed(2)}`,
                transaction.type
            ]);

            populateTable('fraud-alerts', data.fraud_alerts, alert => [
                new Date(alert.timestamp).toLocaleString(),
                alert.account_id,
                alert.message
            ]);
        })
        .catch(error => console.error('Error fetching dashboard metrics:', error));
}

function populateTable(tableId, data, rowDataFunction) {
    const tableBody = document.querySelector(`#${tableId} tbody`);
    tableBody.innerHTML = '';
    data.forEach(item => {
        const row = document.createElement('tr');
        rowDataFunction(item).forEach(cellData => {
            const cell = document.createElement('td');
            cell.textContent = cellData;
            row.appendChild(cell);
        });
        tableBody.appendChild(row);
    });
}

function fetchTransactionVolume() {
    fetch('/admin/api/transaction_volume')
        .then(response => response.json())
        .then(data => {
            const dates = data.map(item => item._id);
            const counts = data.map(item => item.count);
            const amounts = data.map(item => item.total_amount);

            const ctx = document.getElementById('transaction-volume-chart').getContext('2d');
            new Chart(ctx, {
                type: 'line',
                data: {
                    labels: dates,
                    datasets: [
                        {
                            label: 'Transaction Count',
                            data: counts,
                            borderColor: 'rgba(75, 192, 192, 1)',
                            tension: 0.1
                        },
                        {
                            label: 'Total Amount',
                            data: amounts,
                            borderColor: 'rgba(255, 99, 132, 1)',
                            tension: 0.1
                        }
                    ]
                },
                options: {
                    responsive: true,
                    scales: {
                        x: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Date'
                            }
                        },
                        y: {
                            display: true,
                            title: {
                                display: true,
                                text: 'Value'
                            }
                        }
                    }
                }
            });
        })
        .catch(error => console.error('Error fetching transaction volume:', error));
}

document.getElementById('reset-data-btn').addEventListener('click', function() {
    if (confirm('Are you sure you want to reset all data? This action cannot be undone.')) {
        fetch('/admin/reset_data', {
            method: 'POST',
        })
        .then(response => response.json())
        .then(data => {
            alert(data.message || data.error);
            location.reload();  // Reload the page to reflect the new data
        })
        .catch(error => {
            console.error('Error:', error);
            alert('An error occurred while resetting data');
        });
    }
});