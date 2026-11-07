# SplitEasy — ma'lumotlar bazasi

Ushbu hujjat texnik topshiriqning 10-bo'limiga (10.7) muvofiq bazaning tuzilishi,
normalizatsiyasi, cheklovlari, indekslari va tranzaksiya qarorlarini tushuntiradi.

| Manba | Fayl |
|---|---|
| ERD | [`docs/erd.png`](erd.png) — `poetry run python scripts/draw_erd.py` bilan ORM'dan chiziladi |
| Qo'lda yozilgan sxema | [`docs/schema.sql`](schema.sql) |
| Migratsiyalar | [`migrations/versions/`](../migrations/versions) |
| ORM modellari | [`app/repositories/sqlalchemy/orm_models.py`](../app/repositories/sqlalchemy/orm_models.py) |

Uchala manba (Alembic, `schema.sql`, ORM) **bir xil sxema** beradi — buni
`tests/integration/test_schema.py` SQLite katalogi (`PRAGMA table_info`,
`foreign_key_list`, `index_list`) va `CHECK` ifodalari bo'yicha solishtiradi.

Bazani yaratish:

```bash
poetry run alembic upgrade head          # bo'sh bazadan to'liq sxema
poetry run alembic downgrade base        # hammasini qaytarish
```

---

## 1. ERD va jadvallar

![ERD](erd.png)

| Jadval | Vazifasi | Bog'lanishlar |
|---|---|---|
| `users` | Ro'yxatdan o'tgan foydalanuvchilar | — |
| `groups` | Xarajat guruhlari | `users` 1:N `groups` (ega) |
| `group_members` | A'zolik | `users` **M:N** `groups` shu jadval orqali |
| `expenses` | Xarajatlar | `groups` 1:N, `group_members` 1:N (to'lovchi), `users` 1:N (muallif) |
| `expense_shares` | Har bir ishtirokchining ulushi | `expenses` 1:N, `users` 1:N |
| `settlements` | Qarzni yopish to'lovlari | `groups` 1:N, `group_members` 1:N (ikki marta: yuboruvchi, oluvchi) |
| `notifications` | Ilova ichidagi bildirishnomalar | `users` 1:N |

Texnik topshiriqdagi ro'yxatdan farqlar:

- `users.name` o'rniga **`username`** (DESIGN.md 5.1 bo'yicha, unikal, login uchun). ⚠️ TZ'da
  `name` — qaysi biri qolishi jamoa bilan kelishilishi kerak (PR #9 da ko'tarilgan).
- `expenses` va `settlements` to'lovchi/ishtirokchini to'g'ridan-to'g'ri `users` ga emas,
  `group_members (group_id, user_id)` ga **kompozit FK** bilan bog'laydi (3-bo'lim).

---

## 2. Normalizatsiya

Barcha jadvallar **3NF** da: har bir jadvalda kalit bo'lmagan ustunlar faqat butun kalitga
bog'liq (2NF) va bir-biriga tranzitiv bog'liq emas (3NF). Takrorlanuvchi guruhlar yo'q,
har bir katakda bitta qiymat (1NF): masalan, ishtirokchilar ro'yxati ustunda vergul bilan
emas, `expense_shares` da alohida qatorlarda.

| Jadval | Kalit | Funksional bog'liqliklar | Izoh |
|---|---|---|---|
| `users` | `id` (yana `username`, `email` — nomzod kalitlar) | `id → username, email, password_hash, created_at` | Nomzod kalitlar ham to'liq aniqlaydi — BCNF |
| `groups` | `id` | `id → name, currency, owner_id, is_deleted, created_at` | Ega nomi bu yerda **saqlanmaydi** (`owner_id → username` tranzitiv bo'lardi) |
| `group_members` | `(group_id, user_id)` | `(group_id, user_id) → joined_at` | `joined_at` butun kalitga bog'liq — 2NF |
| `expenses` | `id` | `id → group_id, description, amount, paid_by, category, split_type, expense_date, created_by, created_at` | Valyuta guruhdan olinadi, takrorlanmaydi |
| `expense_shares` | `(expense_id, user_id)` | `(expense_id, user_id) → share_amount` | Pastdagi denormalizatsiyaga qarang |
| `settlements` | `id` | `id → group_id, from_user_id, to_user_id, amount, created_at` | — |
| `notifications` | `id` | `id → user_id, message, is_read, created_at` | — |

### Ongli denormalizatsiya: `expense_shares.share_amount`

`share_amount` — **hosila ma'lumot**: uni `expenses.amount`, `split_type` va ishtirokchilar
qiymatlaridan strategiya yordamida qayta hisoblash mumkin. Shunga qaramay saqlanadi, chunki:

1. **Balans tez hisoblanadi** — bitta `SUM(share_amount) GROUP BY user_id`, har bir xarajat
   uchun strategiyani qayta ishga tushirish shart emas.
2. **Yaxlitlash natijasi o'zgarmaydi** — qoldiq tiyinlar kimga tushgani yozib qo'yiladi;
   kelajakda bo'lish algoritmi o'zgarsa ham eski xarajatlar o'zgarmaydi.
3. Foiz/ulush qiymatlarini (`value`) alohida saqlash kerak bo'lmaydi.

**Xavf:** ulushlar yig'indisi `amount` ga teng bo'lmay qolishi mumkin. SQLite qatorlararo
`CHECK` ni qo'llab-quvvatlamaydi, shuning uchun himoya uch qatlamda:

- domen: `Expense.__post_init__` yig'indi `amount` ga teng bo'lmasa xato beradi
  (`tests/unit/test_models.py`);
- tranzaksiya: xarajat va uning barcha ulushlari bitta tranzaksiyada yoziladi (7-bo'lim);
- baza: `share_amount >= 0`, `amount > 0` va `(expense_id, user_id)` PK.

### Soft delete: `groups.is_deleted`

- Guruh o'chirilganda qator qolaveradi — xarajat va to'lovlar tarixi saqlanadi
  (`expenses.group_id` va `settlements.group_id` `ON DELETE RESTRICT`).
- **So'rovlarga ta'siri:** har bir ro'yxat so'rovi `is_deleted = 0` filtrini qo'shishi shart
  (`SqlAlchemyGroupRepository.list_for_user`); servis o'chirilgan guruhga 404 qaytaradi.
- **UNIQUE ga ta'siri:** hozir guruh nomi unikal emas, shuning uchun muammo yo'q. Agar
  kelajakda "bir egada bir xil nomli guruh bo'lmasin" talabi qo'shilsa, oddiy
  `UNIQUE(owner_id, name)` o'chirilgan guruh nomini qayta ishlatishga to'sqinlik qiladi —
  buning o'rniga **qisman indeks** kerak bo'ladi:
  `CREATE UNIQUE INDEX ... ON groups (owner_id, name) WHERE is_deleted = 0`.

---

## 3. Cheklovlar (constraints)

Hamma qoidalar bazaning o'zida e'lon qilingan — faqat Python'dagi tekshiruvga tayanilmaydi.
Testlar: `tests/integration/test_constraints.py`, `test_group_repository.py`.

| Cheklov | Jadval | Nima | Nega |
|---|---|---|---|
| `pk_*` | hammasi | PRIMARY KEY | Har bir qator yagona aniqlanadi |
| `pk_group_members` | `group_members` | PK `(group_id, user_id)` | Bir kishi guruhga ikki marta qo'shilmaydi |
| `pk_expense_shares` | `expense_shares` | PK `(expense_id, user_id)` | Bir xarajatda bir kishining bitta ulushi |
| `uq_users_email`, `uq_users_username` | `users` | UNIQUE | Login yagona; servis 409 qaytaradi |
| NOT NULL | hammasi | `created_by` dan boshqa barcha ustunlar | Majburiy maydonlar bo'sh qolmaydi |
| `ck_groups_name_not_blank` | `groups` | `length(trim(name)) > 0` | Faqat bo'shliqdan iborat nom |
| `ck_groups_currency_code` | `groups` | `length(currency) = 3` | ISO kod (`UZS`, `USD`) |
| `ck_expenses_amount_positive` | `expenses` | `amount > 0` | Nol yoki manfiy xarajat yo'q |
| `ck_expenses_description_not_blank` | `expenses` | `length(trim(description)) > 0` | — |
| `ck_expenses_category_valid` | `expenses` | `category IN (...)` | Domen `Category` enum'i bilan bir xil |
| `ck_expenses_split_type_valid` | `expenses` | `split_type IN (...)` | Domen `SplitType` enum'i bilan bir xil |
| `ck_expense_shares_share_amount_non_negative` | `expense_shares` | `share_amount >= 0` | Ulush manfiy bo'lmaydi (nol mumkin: "aniq summa"da 0) |
| `ck_settlements_amount_positive` | `settlements` | `amount > 0` | — |
| `ck_settlements_different_users` | `settlements` | `from_user_id <> to_user_id` | O'ziga o'zi to'lamaydi |
| `ck_notifications_message_not_blank` | `notifications` | `length(trim(message)) > 0` | — |
| `fk_expenses_group_id_paid_by_group_members` | `expenses` | kompozit FK → `group_members` | **To'lovchi shu guruh a'zosi bo'lishi shart** |
| `fk_settlements_group_id_{from,to}_user_id_group_members` | `settlements` | kompozit FK → `group_members` | Ikkala tomon ham guruh a'zosi |

Cheklov nomlari `NAMING_CONVENTION` (`app/infrastructure/database.py`) bo'yicha
deterministik — Alembic, `schema.sql` va ORM bir xil nom beradi.

**SQLite eslatmasi:** foreign key'lar faqat `PRAGMA foreign_keys = ON` bo'lsa ishlaydi va bu
**har bir ulanishda** qayta yoqilishi kerak. `make_engine()` buni `connect` hodisasida
bajaradi (ilova, testlar va Alembic uchun bir xil).

### `ON DELETE` qoidalari

| FK | Qoida | Nega |
|---|---|---|
| `groups.owner_id → users` | RESTRICT | Egasi bor guruhni yetim qoldirmaslik |
| `group_members.group_id → groups` | CASCADE | A'zolik guruhsiz ma'nosiz (guruhlar odatda soft delete qilinadi) |
| `group_members.user_id → users` | CASCADE | Foydalanuvchi o'chsa a'zoligi ham ketadi — lekin moliyaviy tarixi bo'lsa pastdagi RESTRICT to'xtatadi |
| `expenses.group_id → groups` | RESTRICT | Moliyaviy tarix o'chmasligi kerak — guruh soft delete qilinadi |
| `expenses.(group_id, paid_by) → group_members` | RESTRICT | Xarajat to'lagan a'zoni guruhdan chiqarib bo'lmaydi (servis 409 qaytaradi) |
| `expenses.created_by → users` | **SET NULL** | Muallif — faqat ma'lumot uchun; u o'chsa xarajat qoladi |
| `expense_shares.expense_id → expenses` | CASCADE | Ulush xarajatning bir qismi; tahrirlashda eski ulushlar o'chiriladi |
| `expense_shares.user_id → users` | RESTRICT | Kimdir qarzdor bo'lgan ulushni yo'qotmaslik |
| `settlements.group_id → groups` | RESTRICT | Moliyaviy tarix |
| `settlements.(group_id, from/to) → group_members` | RESTRICT | To'lovda qatnashgan a'zoni chiqarib bo'lmaydi |
| `notifications.user_id → users` | CASCADE | Bildirishnoma faqat egasi uchun kerak |

**Ma'lum cheklov:** `expense_shares` da `group_id` yo'q, shuning uchun "ulush egasi guruh
a'zosi" qoidasini kompozit FK bilan ta'minlab bo'lmaydi (buning uchun `group_id` ni
takrorlash — 3NF'ni buzish kerak bo'lardi). Bu qoidani xarajat servisi tekshiradi;
faqat ulushda qatnashgan a'zoni chiqarishni taqiqlash ham servisda (`GroupService` dagi TODO).

---

## 4. Xom SQL hisobot so'rovlari

> ⏳ Keyingi bosqich: `ReportRepository` interfeysi va `report_queries.py` (TZ 10.2).

---

## 5. Indekslar

PRIMARY KEY va UNIQUE o'z indeksini o'zi yaratadi (`sqlite_autoindex_*`), ular takrorlanmaydi.
Qo'shimcha indekslar alohida migratsiyada (`0004_add_query_indexes`) — benchmark uchun
`alembic downgrade 0003` / `upgrade head` bilan ularni o'chirib-yoqish mumkin.

| Indeks | So'rov | Ustunlar tartibi nega shunday |
|---|---|---|
| `ix_group_members_user_id` | "Mening guruhlarim" (`WHERE user_id = ?`) | PK `(group_id, user_id)` faqat `group_id` bo'yicha qidirishga yaraydi |
| `ix_expenses_group_id_expense_date_id` (**composite**) | Guruh xarajatlari, sana bo'yicha, sahifalab | `group_id` — tenglik filtri birinchi; keyin `expense_date, id` — tartiblash indeksdan olinadi, `id` keyset pagination uchun bir xil sanalarni ajratadi |
| `ix_expenses_group_id_paid_by` (composite) | Guruhda kim qancha to'lagan (`GROUP BY paid_by`); a'zoni o'chirishdagi kompozit FK tekshiruvi | FK ustunlari tartibida |
| `ix_expense_shares_user_id` | Foydalanuvchining ulushlari (balans) | PK `(expense_id, user_id)` `user_id` bo'yicha yordam bermaydi |
| `ix_settlements_group_id_created_at` | Guruh to'lovlari tarixi | Filtr, keyin tartib |
| `ix_notifications_user_id_created_at` | "Mening bildirishnomalarim", yangilari birinchi | Filtr, keyin tartib |

**Indekslanmagan ustunlar (ongli qaror):**

- `groups.is_deleted` — faqat ikki qiymat, deyarli hammasi `0`; indeks selektiv emas, yozishni
  sekinlashtiradi xolos.
- `groups.owner_id` — foydalanuvchi o'chirish ilovada yo'q, "egasi bo'yicha guruhlar" so'rovi
  ham yo'q; FK tekshiruvi kamdan-kam ishlaydi.

> ⏳ Keyingi bosqich: `scripts/seed.py`, `EXPLAIN QUERY PLAN` natijalari va
> `scripts/benchmark.py` bilan "indekssiz / indeks bilan" o'lchov jadvali (TZ 10.3).
> O'lchov natijasiga ko'ra indekslar ro'yxati o'zgarishi mumkin.

---

## 6. N+1 muammosi

> ⏳ Keyingi bosqich: xarajatlar ro'yxati (TZ 10.6). Hozircha guruh a'zolarining
> ismlari bitta `IN (...)` so'rovi bilan olinadi (`UserRepository.get_many`) — a'zolar
> soniga qarab so'rovlar ko'paymaydi.

---

## 7. Tranzaksiyalar va ACID

**Hozirgi holat:** har bir HTTP so'rov bitta sessiya va bitta tranzaksiyada ishlaydi
(`get_session`): muvaffaqiyatda `commit`, xatoda `rollback`. Masalan, guruh yaratish
(`groups` qatori + egasining `group_members` qatori) bitta tranzaksiya — yarim yaratilgan
guruh qolmaydi. Kutilgan xatolar (takroriy a'zo, tarixi bor a'zoni chiqarish) **savepoint**
(`begin_nested`) ichida ushlanadi: faqat o'sha qadam bekor qilinadi, tranzaksiya davom etadi.

> ⏳ TZ 10.4 tranzaksiya chegarasini **servis qatlamida** belgilashni talab qiladi.
> Xarajat servisi bilan birga Unit of Work qo'shiladi: servis `with uow:` ichida
> xarajat va barcha ulushlarni yozadi.

| ACID | Loyihada qayerda |
|---|---|
| **A**tomicity | Xarajat va uning ulushlari, guruh va egasining a'zoligi — yo hammasi, yo hech biri yoziladi |
| **C**onsistency | `CHECK`, `FOREIGN KEY`, `UNIQUE` har bir tranzaksiya oxirida bazani to'g'ri holatda saqlaydi; buzilsa `IntegrityError` va `rollback` |
| **I**solation | SQLite yozishda butun bazani bloklaydi — bir vaqtda ikki yozuvchi bir-birining yarim natijasini ko'rmaydi |
| **D**urability | `commit` dan keyin ma'lumot faylda (SQLite jurnali), server qayta ishga tushsa ham qoladi |

---

## Migratsiyalar

| Revizion | Mazmuni |
|---|---|
| `0001` | `users` |
| `0002` | `groups`, `group_members` |
| `0003` | `expenses`, `expense_shares`, `settlements`, `notifications` |
| `0004` | so'rov indekslari |

Har birida `upgrade` va `downgrade` bor. `alembic check` ORM bilan farq yo'qligini
ko'rsatadi; `test_schema.py` esa `upgrade head`, `downgrade base` va indeks
migratsiyasini qaytarishni tekshiradi.
