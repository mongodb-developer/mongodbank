document.addEventListener('DOMContentLoaded', function() {
    const querySelector = document.getElementById('querySelector');
    const originalMongoQueryElem = document.getElementById('originalMongoQuery');
    const normalizedMongoQueryElem = document.getElementById('normalizedMongoQuery');
    const runQueriesBtn = document.getElementById('runQueries');
    const resultsElem = document.getElementById('results');

    const queries = {
        account_details: {
            original: `
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
])`,
            normalized: `
db.accounts.aggregate([
  { $sample: { size: 1 } },
  { $lookup: {
      from: "transactions",
      localField: "_id",
      foreignField: "account_id",
      pipeline: [
        { $sort: { timestamp: -1 } },
        { $limit: 10 }
      ],
      as: "recent_transactions"
    }
  },
  { $lookup: {
      from: "transactions",
      localField: "_id",
      foreignField: "account_id",
      pipeline: [
        { $group: {
            _id: null,
            avg_amount: { $avg: "$amount" },
            max_amount: { $max: "$amount" },
            min_amount: { $min: "$amount" },
            total_count: { $sum: 1 }
          }
        }
      ],
      as: "transaction_stats"
    }
  },
  { $unwind: "$transaction_stats" },
  { $project: {
      account_type: 1,
      balance: 1,
      recent_transactions: 1,
      avg_transaction_amount: "$transaction_stats.avg_amount",
      max_transaction_amount: "$transaction_stats.max_amount",
      min_transaction_amount: "$transaction_stats.min_amount",
      total_transactions: "$transaction_stats.total_count"
    }
  }
])`
        },
        customer_summary: {
            original: `
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
])`,
            normalized: `
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
      pipeline: [
        { $group: {
            _id: null,
            transaction_count: { $sum: 1 },
            avg_transaction_amount: { $avg: "$amount" },
            total_deposits: {
              $sum: { $cond: [{ $eq: ["$type", "deposit"] }, "$amount", 0] }
            },
            total_withdrawals: {
              $sum: { $cond: [{ $eq: ["$type", "withdrawal"] }, "$amount", 0] }
            }
          }
        }
      ],
      as: "account_stats"
    }
  },
  { $unwind: "$account_stats" },
  { $group: {
      _id: "$_id",
      username: { $first: "$username" },
      email: { $first: "$email" },
      accounts: {
        $push: {
          account_id: "$accounts._id",
          account_type: "$accounts.account_type",
          balance: "$accounts.balance",
          transaction_count: "$account_stats.transaction_count",
          avg_transaction_amount: "$account_stats.avg_transaction_amount",
          total_deposits: "$account_stats.total_deposits",
          total_withdrawals: "$account_stats.total_withdrawals"
        }
      },
      total_balance: { $sum: "$accounts.balance" },
      account_count: { $sum: 1 }
    }
  }
])`
        },
        fraud_analysis: {
            original: `
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
])`,
            normalized: `
db.transactions.aggregate([
  { $match: {
      timestamp: { $gte: new Date(new Date() - 30 * 24 * 60 * 60 * 1000) }
    }
  },
  { $lookup: {
      from: "fraud_flags",
      localField: "_id",
      foreignField: "transaction_id",
      as: "fraud_flags"
    }
  },
  { $match: { fraud_flags: { $ne: [] } } },
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
])`
        }
    };

    function updateQueries() {
        const selectedQuery = queries[querySelector.value];
        originalMongoQueryElem.textContent = selectedQuery.original;
        normalizedMongoQueryElem.textContent = selectedQuery.normalized;
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
                <p>Original MongoDB Execution Time: ${data.original_time} ms</p>
                <p>Normalized MongoDB Execution Time: ${data.normalized_time} ms</p>
                <p>Performance Gain: ${data.performance_gain}x</p>
                <p>Original MongoDB Results: ${data.original_results}</p>
                <p>Normalized MongoDB Results: ${data.normalized_results}</p>
            `;
        })
        .catch(error => {
            console.error('Error:', error);
            resultsElem.innerHTML = `<p>An error occurred while running the queries: ${error.message}</p>`;
        });
    }

    // Add event listener for dropdown change
    querySelector.addEventListener('change', updateQueries);

    // Add event listener for run queries button
    runQueriesBtn.addEventListener('click', runQueries);

    // Initial update of queries
    updateQueries();
});