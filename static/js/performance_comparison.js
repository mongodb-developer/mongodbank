document.addEventListener('DOMContentLoaded', function() {
    const querySelector = document.getElementById('querySelector');
    const sqlQueryElem = document.getElementById('sqlQuery');
    const mongoQueryElem = document.getElementById('mongoQuery');
    const runQueriesBtn = document.getElementById('runQueries');
    const resultsElem = document.getElementById('results');

    const queries = {
        account_details: {
            sql: `
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
    `,
            mongo: `
    db.accounts.aggregate([
      { $sample: { size: 1 } },
      { $lookup: {
          from: "transactions",
          localField: "_id",
          foreignField: "account_id",
          as: "transactions"
        }
      },
      { $project: {
          account_type: 1,
          balance: 1,
          recent_transactions: { 
            $slice: [
              { $sortArray: { 
                  input: "$transactions", 
                  sortBy: { timestamp: -1 } 
              }}, 
              10
            ]
          },
          avg_transaction_amount: { $avg: "$transactions.amount" },
          max_transaction_amount: { $max: "$transactions.amount" },
          min_transaction_amount: { $min: "$transactions.amount" },
          total_transactions: { $size: "$transactions" }
        }
      }
    ])
    `,
            description: "This query retrieves detailed account information, including recent transactions and transaction statistics."
        },
        customer_summary: {
            sql: `
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
    `,
            mongo: `
    db.customers.aggregate([
      { $sample: { size: 1 } },
      { $lookup: {
          from: "accounts",
          localField: "_id",
          foreignField: "customer_id",
          as: "accounts"
        }
      },
      { $unwind: "$accounts" },
      { $lookup: {
          from: "transactions",
          localField: "accounts._id",
          foreignField: "account_id",
          as: "accounts.transactions"
        }
      },
      { $group: {
          _id: "$_id",
          username: { $first: "$username" },
          email: { $first: "$email" },
          accounts: {
            $push: {
              account_id: "$accounts._id",
              account_type: "$accounts.account_type",
              balance: "$accounts.balance",
              transaction_count: { $size: "$accounts.transactions" },
              avg_transaction_amount: { $avg: "$accounts.transactions.amount" },
              total_deposits: {
                $sum: {
                  $filter: {
                    input: "$accounts.transactions",
                    as: "t",
                    cond: { $eq: ["$$t.type", "deposit"] }
                  }
                }
              },
              total_withdrawals: {
                $sum: {
                  $filter: {
                    input: "$accounts.transactions",
                    as: "t",
                    cond: { $eq: ["$$t.type", "withdrawal"] }
                  }
                }
              }
            }
          },
          total_balance: { $sum: "$accounts.balance" },
          account_count: { $sum: 1 }
        }
      }
    ])
    `,
            description: "This query provides a comprehensive summary of a customer's accounts, including detailed statistics for each account."
        },
        fraud_analysis: {
            sql: `
    WITH fraudulent_transactions AS (
        SELECT t.id, t.account_id, t.type, t.amount, t.timestamp, t.fraud_flags,
               a.account_type,
               c.username as customer_name,
               ROW_NUMBER() OVER (PARTITION BY t.account_id ORDER BY t.timestamp DESC) as rn
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        JOIN customers c ON a.customer_id = c.id
        WHERE t.timestamp >= :thirty_days_ago
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
            WHERE account_id = ft.account_id AND timestamp >= :thirty_days_ago) as total_transactions
    FROM fraudulent_transactions ft
    JOIN fraud_stats fs ON ft.account_id = fs.account_id
    WHERE ft.rn <= 10
    ORDER BY ft.timestamp DESC
    `,
            mongo: `
    db.transactions.aggregate([
      { $match: {
          timestamp: { $gte: new Date(new Date() - 30 * 24 * 60 * 60 * 1000) },
          fraud_flags: { $exists: true, $ne: [] }
        }
      },
      { $lookup: {
          from: "accounts",
          localField: "account_id",
          foreignField: "_id",
          as: "account"
        }
      },
      { $unwind: "$account" },
      { $lookup: {
          from: "customers",
          localField: "account.customer_id",
          foreignField: "_id",
          as: "customer"
        }
      },
      { $unwind: "$customer" },
      { $group: {
          _id: "$account_id",
          fraud_transactions: { $push: "$$ROOT" },
          fraud_count: { $sum: 1 },
          avg_fraud_amount: { $avg: "$amount" },
          total_fraud_amount: { $sum: "$amount" }
        }
      },
      { $project: {
          fraud_transactions: { $slice: ["$fraud_transactions", 10] },
          fraud_count: 1,
          avg_fraud_amount: 1,
          total_fraud_amount: 1
        }
      },
      { $unwind: "$fraud_transactions" },
      { $project: {
          transaction_id: "$fraud_transactions._id",
          type: "$fraud_transactions.type",
          amount: "$fraud_transactions.amount",
          timestamp: "$fraud_transactions.timestamp",
          fraud_flags: "$fraud_transactions.fraud_flags",
          account_type: "$fraud_transactions.account.account_type",
          customer_name: "$fraud_transactions.customer.username",
          fraud_count: 1,
          avg_fraud_amount: 1,
          total_fraud_amount: 1
        }
      },
      { $sort: { timestamp: -1 } },
      { $limit: 100 }
    ])
    `,
            description: "This query performs a detailed analysis of fraudulent transactions, including statistics per account and overall transaction counts."
        }
    };

    querySelector.addEventListener('change', updateQueries);
    runQueriesBtn.addEventListener('click', runQueries);

    function updateQueries() {
        const selectedQuery = queries[querySelector.value];
        sqlQueryElem.textContent = selectedQuery.sql;
        mongoQueryElem.textContent = selectedQuery.mongo;
    }

    function runQueries() {
        resultsElem.innerHTML = '<p>Running queries...</p>';
        fetch('/api/run_performance_comparison', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ query_type: querySelector.value }),
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            resultsElem.innerHTML = `
                <p>PostgreSQL Execution Time: ${data.postgres_time} ms</p>
                <p>MongoDB Execution Time: ${data.mongo_time} ms</p>
                <p>Performance Gain: ${data.performance_gain}x</p>
                <p>PostgreSQL Results: ${data.postgres_results}</p>
                <p>MongoDB Results: ${data.mongo_results}</p>
            `;
        })
        .catch(error => {
            console.error('Error:', error);
            resultsElem.innerHTML = `<p>An error occurred while running the queries: ${error.message}</p>`;
        });
    }

    updateQueries();
});