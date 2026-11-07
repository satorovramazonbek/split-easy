# Benchmark: indekssiz va indeks bilan

`scripts/benchmark.py` tomonidan yaratilgan — qo'lda tahrirlamang.

- Ma'lumot: `scripts/seed.py` — users 1,000, groups 200, expenses 100,000, expense_shares 300,221
- Har bir so'rov: 1 ta qizdirish + 7 ta o'lchov, o'rtacha
- Parametrlar: `{'group_id': 172, 'user_id': 141, 'offset': 90000, 'after_id': 10001}`
- Muhit: Python 3.12.10, SQLite 3.49.1, Windows AMD64

| So'rov | Indekssiz (ms) | Indeks bilan (ms) | Tezlashish | Reja (oldin → keyin) |
|---|---:|---:|---:|---|
| Guruh xarajatlari, 1-sahifa (FR-13) | 15.56 | 0.11 | 136.0× | `SCAN expenses` → `SEARCH expenses INDEX ix_expenses_group_id_expense_date_id` |
| Kategoriya bo'yicha filtr (FR-14) | 21.80 | 0.15 | 143.9× | `SCAN expenses` → `SEARCH expenses INDEX ix_expenses_group_id_expense_date_id` |
| A'zolar balansi (1-so'rov) | 39.90 | 9.32 | 4.3× | `SCAN expenses` → `SEARCH expenses COVERING INDEX ix_expenses_group_id_paid_by_amount` |
| Foydalanuvchi umumiy holati (8-so'rov) | 64.16 | 14.39 | 4.5× | `SCAN e` → `SEARCH e COVERING INDEX ix_expenses_group_id_paid_by_amount` |
| Mening guruhlarim | 0.13 | 0.06 | 2.1× | `SCAN g` → `SEARCH gm INDEX ix_group_members_user_id` |
| O'qilmagan bildirishnomalar | 7.26 | 0.10 | 75.2× | `SCAN notifications` → `SEARCH notifications INDEX ix_notifications_user_id_created_at` |
| Kategoriyalar jami (2-so'rov) | 16.41 | 4.82 | 3.4× | `SCAN expenses` → `SEARCH expenses INDEX ix_expenses_group_id_paid_by_amount` |
| Eng ko'p to'laganlar (4-so'rov) | 25.13 | 0.70 | 35.7× | `SCAN e` → `SEARCH e COVERING INDEX ix_expenses_group_id_paid_by_amount` |
| Bonus: chuqur sahifa, OFFSET | 10.43 | 10.73 | 1.0× | `SCAN expenses` → `SCAN expenses` |
| Bonus: chuqur sahifa, keyset | 0.06 | 0.07 | 1.0× | `SEARCH expenses INTEGER PRIMARY KEY` → `SEARCH expenses INTEGER PRIMARY KEY` |

## EXPLAIN QUERY PLAN

### Guruh xarajatlari, 1-sahifa (FR-13)

Indekssiz:

```text
SCAN expenses
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
SEARCH expenses USING INDEX ix_expenses_group_id_expense_date_id (group_id=?)
```

### Kategoriya bo'yicha filtr (FR-14)

Indekssiz:

```text
SCAN expenses
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
SEARCH expenses USING INDEX ix_expenses_group_id_expense_date_id (group_id=?)
```

### A'zolar balansi (1-so'rov)

Indekssiz:

```text
MATERIALIZE p
SCAN expenses
USE TEMP B-TREE FOR GROUP BY
MATERIALIZE o
SCAN e
SEARCH es USING INDEX sqlite_autoindex_expense_shares_1 (expense_id=?)
USE TEMP B-TREE FOR GROUP BY
MATERIALIZE s
SCAN settlements
USE TEMP B-TREE FOR GROUP BY
MATERIALIZE r
SCAN settlements
USE TEMP B-TREE FOR GROUP BY
SEARCH gm USING COVERING INDEX sqlite_autoindex_group_members_1 (group_id=?)
SEARCH u USING INTEGER PRIMARY KEY (rowid=?)
BLOOM FILTER ON p (user_id=?)
SEARCH p USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON o (user_id=?)
SEARCH o USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON s (user_id=?)
SEARCH s USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON r (user_id=?)
SEARCH r USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
```

Indeks bilan:

```text
MATERIALIZE p
SEARCH expenses USING COVERING INDEX ix_expenses_group_id_paid_by_amount (group_id=?)
MATERIALIZE o
SEARCH e USING COVERING INDEX ix_expenses_group_id_paid_by_amount (group_id=?)
SEARCH es USING INDEX sqlite_autoindex_expense_shares_1 (expense_id=?)
USE TEMP B-TREE FOR GROUP BY
MATERIALIZE s
SEARCH settlements USING INDEX ix_settlements_group_id_created_at (group_id=?)
USE TEMP B-TREE FOR GROUP BY
MATERIALIZE r
SEARCH settlements USING INDEX ix_settlements_group_id_created_at (group_id=?)
USE TEMP B-TREE FOR GROUP BY
SEARCH gm USING COVERING INDEX sqlite_autoindex_group_members_1 (group_id=?)
SEARCH u USING INTEGER PRIMARY KEY (rowid=?)
BLOOM FILTER ON p (user_id=?)
SEARCH p USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON o (user_id=?)
SEARCH o USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON s (user_id=?)
SEARCH s USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
BLOOM FILTER ON r (user_id=?)
SEARCH r USING AUTOMATIC COVERING INDEX (user_id=?) LEFT-JOIN
```

### Foydalanuvchi umumiy holati (8-so'rov)

Indekssiz:

```text
MATERIALIZE movements
COMPOUND QUERY
LEFT-MOST SUBQUERY
SCAN e
LIST SUBQUERY 2
BLOOM FILTER ON g (is_deleted=?)
SEARCH g USING AUTOMATIC PARTIAL COVERING INDEX (is_deleted=?)
SEARCH gm USING COVERING INDEX sqlite_autoindex_group_members_1 (group_id=? AND user_id=?)
CREATE BLOOM FILTER
UNION ALL
SCAN es
SEARCH e USING INTEGER PRIMARY KEY (rowid=?)
UNION ALL
SCAN settlements
UNION ALL
SCAN settlements
SCAN g
SEARCH gm USING COVERING INDEX sqlite_autoindex_group_members_1 (group_id=? AND user_id=?)
BLOOM FILTER ON m (group_id=?)
SEARCH m USING AUTOMATIC COVERING INDEX (group_id=?) LEFT-JOIN
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
MATERIALIZE movements
COMPOUND QUERY
LEFT-MOST SUBQUERY
SEARCH e USING COVERING INDEX ix_expenses_group_id_paid_by_amount (group_id=? AND paid_by=?)
LIST SUBQUERY 2
SEARCH gm USING INDEX ix_group_members_user_id (user_id=?)
SEARCH g USING INTEGER PRIMARY KEY (rowid=?)
CREATE BLOOM FILTER
UNION ALL
SEARCH es USING INDEX ix_expense_shares_user_id (user_id=?)
SEARCH e USING INTEGER PRIMARY KEY (rowid=?)
UNION ALL
SCAN settlements
UNION ALL
SCAN settlements
SEARCH gm USING INDEX ix_group_members_user_id (user_id=?)
SEARCH g USING INTEGER PRIMARY KEY (rowid=?)
BLOOM FILTER ON m (group_id=?)
SEARCH m USING AUTOMATIC COVERING INDEX (group_id=?) LEFT-JOIN
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

### Mening guruhlarim

Indekssiz:

```text
SCAN g
SEARCH gm USING COVERING INDEX sqlite_autoindex_group_members_1 (group_id=? AND user_id=?)
```

Indeks bilan:

```text
SEARCH gm USING INDEX ix_group_members_user_id (user_id=?)
SEARCH g USING INTEGER PRIMARY KEY (rowid=?)
```

### O'qilmagan bildirishnomalar

Indekssiz:

```text
SCAN notifications
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
SEARCH notifications USING INDEX ix_notifications_user_id_created_at (user_id=?)
```

### Kategoriyalar jami (2-so'rov)

Indekssiz:

```text
SCAN expenses
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
SEARCH expenses USING INDEX ix_expenses_group_id_paid_by_amount (group_id=?)
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

### Eng ko'p to'laganlar (4-so'rov)

Indekssiz:

```text
SCAN e
SEARCH u USING INTEGER PRIMARY KEY (rowid=?)
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

Indeks bilan:

```text
SEARCH e USING COVERING INDEX ix_expenses_group_id_paid_by_amount (group_id=?)
SEARCH u USING INTEGER PRIMARY KEY (rowid=?)
USE TEMP B-TREE FOR GROUP BY
USE TEMP B-TREE FOR ORDER BY
```

### Bonus: chuqur sahifa, OFFSET

Indekssiz:

```text
SCAN expenses
```

Indeks bilan:

```text
SCAN expenses
```

### Bonus: chuqur sahifa, keyset

Indekssiz:

```text
SEARCH expenses USING INTEGER PRIMARY KEY (rowid<?)
```

Indeks bilan:

```text
SEARCH expenses USING INTEGER PRIMARY KEY (rowid<?)
```
