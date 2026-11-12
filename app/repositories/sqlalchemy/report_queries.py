"""Raw SQL report queries (technical specification, section 10.2).

Reports aggregate many rows with JOIN, GROUP BY, subqueries, window functions
and CTEs. Written by hand they are easier to read, to check with
``EXPLAIN QUERY PLAN`` and to tune with indexes than ORM-generated SQL.

Rules:
- every value is a bound parameter (``:group_id``); no string concatenation;
- every query says what it returns and which tables it joins;
- money is INTEGER (so'm), so SUM() is exact.

Balance convention (same as ``app/domain/balance.py``): the payer of an expense
gets ``+amount``, every participant ``-share_amount``; a settlement from A to B
gives A ``+amount`` and B ``-amount``. Positive = the group owes the user.
"""

# 1. Net balance of every member of a group (FR-16).
# Returns: user_id, username, paid, owed, sent, received, balance.
# Joins: group_members, users, expenses, expense_shares, settlements.
# Each kind of money movement is summed in its own subquery, then LEFT JOINed to
# the member list, so members without activity get 0 through COALESCE.
MEMBER_BALANCES = """
SELECT gm.user_id,
       u.username,
       COALESCE(p.paid, 0)     AS paid,
       COALESCE(o.owed, 0)     AS owed,
       COALESCE(s.sent, 0)     AS sent,
       COALESCE(r.received, 0) AS received,
       COALESCE(p.paid, 0) - COALESCE(o.owed, 0)
         + COALESCE(s.sent, 0) - COALESCE(r.received, 0) AS balance
FROM group_members AS gm
JOIN users AS u ON u.id = gm.user_id
LEFT JOIN (SELECT paid_by AS user_id, SUM(amount) AS paid
           FROM expenses
           WHERE group_id = :group_id
           GROUP BY paid_by) AS p ON p.user_id = gm.user_id
LEFT JOIN (SELECT es.user_id, SUM(es.share_amount) AS owed
           FROM expense_shares AS es
           JOIN expenses AS e ON e.id = es.expense_id
           WHERE e.group_id = :group_id
           GROUP BY es.user_id) AS o ON o.user_id = gm.user_id
LEFT JOIN (SELECT from_user_id AS user_id, SUM(amount) AS sent
           FROM settlements
           WHERE group_id = :group_id
           GROUP BY from_user_id) AS s ON s.user_id = gm.user_id
LEFT JOIN (SELECT to_user_id AS user_id, SUM(amount) AS received
           FROM settlements
           WHERE group_id = :group_id
           GROUP BY to_user_id) AS r ON r.user_id = gm.user_id
WHERE gm.group_id = :group_id
  AND gm.left_at IS NULL  -- members who left have balance 0 (FR-7)
ORDER BY gm.user_id
"""

# 2. Total spending per category in a group (FR-26).
# Returns: category, expense_count, total. Biggest total first.
# Joins: expenses only.
CATEGORY_TOTALS = """
SELECT category,
       COUNT(*)    AS expense_count,
       SUM(amount) AS total
FROM expenses
WHERE group_id = :group_id
GROUP BY category
ORDER BY total DESC, category
"""

# 3. Monthly spending of a group (FR-26).
# Returns: month ('YYYY-MM'), expense_count, total. Oldest month first.
# Joins: expenses only; strftime() turns the date into a month key.
MONTHLY_TOTALS = """
SELECT strftime('%Y-%m', expense_date) AS month,
       COUNT(*)    AS expense_count,
       SUM(amount) AS total
FROM expenses
WHERE group_id = :group_id
GROUP BY month
ORDER BY month
"""

# 4. Members who paid the most (default top 3).
# Returns: user_id, username, expense_count, total_paid.
# Joins: expenses -> users. Ties are broken by user id, so the order is stable.
TOP_PAYERS = """
SELECT e.paid_by        AS user_id,
       u.username,
       COUNT(*)         AS expense_count,
       SUM(e.amount)    AS total_paid
FROM expenses AS e
JOIN users AS u ON u.id = e.paid_by
WHERE e.group_id = :group_id
GROUP BY e.paid_by, u.username
ORDER BY total_paid DESC, e.paid_by
LIMIT :limit
"""

# 5. Members who have not taken part in any expense of the group yet:
#    neither paid one nor have a share in one.
# Returns: user_id, username, joined_at.
# Joins: group_members, users; NOT EXISTS against expenses and expense_shares.
INACTIVE_MEMBERS = """
SELECT gm.user_id, u.username, gm.joined_at
FROM group_members AS gm
JOIN users AS u ON u.id = gm.user_id
WHERE gm.group_id = :group_id
  AND gm.left_at IS NULL
  AND NOT EXISTS (SELECT 1
                  FROM expenses AS e
                  WHERE e.group_id = gm.group_id
                    AND e.paid_by = gm.user_id)
  AND NOT EXISTS (SELECT 1
                  FROM expense_shares AS es
                  JOIN expenses AS e ON e.id = es.expense_id
                  WHERE es.user_id = gm.user_id
                    AND e.group_id = gm.group_id)
ORDER BY gm.user_id
"""

# 6. Expenses bigger than the group's average expense.
# Returns: id, description, amount, paid_by, expense_date, group_average.
# Joins: expenses only; the average comes from a scalar subquery.
ABOVE_AVERAGE_EXPENSES = """
SELECT e.id,
       e.description,
       e.amount,
       e.paid_by,
       e.expense_date,
       (SELECT AVG(amount) FROM expenses WHERE group_id = :group_id) AS group_average
FROM expenses AS e
WHERE e.group_id = :group_id
  AND e.amount > (SELECT AVG(amount) FROM expenses WHERE group_id = :group_id)
ORDER BY e.amount DESC, e.id
"""

# 7. Running (cumulative) total of a group's spending in date order.
# Returns: id, expense_date, amount, running_total.
# Joins: expenses only; window function SUM() OVER (ORDER BY ...).
# id breaks ties between expenses of the same day.
RUNNING_TOTAL = """
SELECT id,
       expense_date,
       amount,
       SUM(amount) OVER (ORDER BY expense_date, id
                         ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
         AS running_total
FROM expenses
WHERE group_id = :group_id
ORDER BY expense_date, id
"""

# 8. A user's position in every active group they belong to (FR-19).
# Returns: group_id, group_name, currency, balance.
# Joins: groups, group_members (CTE my_groups); expenses, expense_shares and
# settlements combined with UNION ALL into one list of signed movements.
# The repository adds the totals "you owe" / "you are owed" per currency.
USER_OVERVIEW = """
WITH my_groups AS (
    SELECT g.id, g.name, g.currency
    FROM group_members AS gm
    JOIN groups AS g ON g.id = gm.group_id
    WHERE gm.user_id = :user_id
      AND gm.left_at IS NULL
      AND g.is_deleted = 0
),
movements AS (
    SELECT e.group_id, e.amount AS delta          -- paid by the user
    FROM expenses AS e
    WHERE e.group_id IN (SELECT id FROM my_groups)
      AND e.paid_by = :user_id
    UNION ALL
    SELECT e.group_id, -es.share_amount           -- the user's shares
    FROM expense_shares AS es
    JOIN expenses AS e ON e.id = es.expense_id
    WHERE es.user_id = :user_id
    UNION ALL
    SELECT group_id, amount                       -- settlements sent
    FROM settlements
    WHERE from_user_id = :user_id
    UNION ALL
    SELECT group_id, -amount                      -- settlements received
    FROM settlements
    WHERE to_user_id = :user_id
)
SELECT mg.id       AS group_id,
       mg.name     AS group_name,
       mg.currency,
       COALESCE(SUM(m.delta), 0) AS balance
FROM my_groups AS mg
LEFT JOIN movements AS m ON m.group_id = mg.id
GROUP BY mg.id, mg.name, mg.currency
ORDER BY mg.id
"""
