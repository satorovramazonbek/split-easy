-- SplitEasy ma'lumotlar bazasi sxemasi (SQLite).
--
-- Qo'lda yozilgan. Alembic migratsiyalari (migrations/) va ORM modellari
-- (app/repositories/sqlalchemy/orm_models.py) aynan shu sxemani berishi kerak:
-- tests/integration/test_schema.py uchalasini solishtiradi.
--
-- Ishlatish:  sqlite3 spliteasy.db < docs/schema.sql
-- Pul summalari INTEGER (so'm), hech qachon REAL emas.
-- Har bir ulanishda: PRAGMA foreign_keys = ON;  (aks holda FK tekshirilmaydi)

PRAGMA foreign_keys = ON;

-- Foydalanuvchilar ------------------------------------------------------------
CREATE TABLE users (
    id            INTEGER      NOT NULL,
    username      VARCHAR(32)  NOT NULL,
    email         VARCHAR(254) NOT NULL,
    password_hash VARCHAR(255) NOT NULL,       -- Argon2 xeshi, ochiq parol emas
    created_at    DATETIME     NOT NULL,
    CONSTRAINT pk_users PRIMARY KEY (id),
    CONSTRAINT uq_users_email UNIQUE (email),
    CONSTRAINT uq_users_username UNIQUE (username)
);

-- Guruhlar --------------------------------------------------------------------
CREATE TABLE groups (
    id         INTEGER      NOT NULL,
    name       VARCHAR(100) NOT NULL,
    currency   VARCHAR(3)   NOT NULL,
    owner_id   INTEGER      NOT NULL,
    is_deleted BOOLEAN      DEFAULT 0 NOT NULL, -- soft delete
    created_at DATETIME     NOT NULL,
    CONSTRAINT pk_groups PRIMARY KEY (id),
    CONSTRAINT ck_groups_currency_code CHECK (length(currency) = 3),
    CONSTRAINT ck_groups_name_not_blank CHECK (length(trim(name)) > 0),
    CONSTRAINT fk_groups_owner_id_users FOREIGN KEY (owner_id)
        REFERENCES users (id) ON DELETE RESTRICT
);

-- Guruh a'zoligi: users <-> groups M:N bog'lanishi ---------------------------
CREATE TABLE group_members (
    group_id  INTEGER  NOT NULL,
    user_id   INTEGER  NOT NULL,
    joined_at DATETIME NOT NULL,
    CONSTRAINT pk_group_members PRIMARY KEY (group_id, user_id),
    CONSTRAINT fk_group_members_group_id_groups FOREIGN KEY (group_id)
        REFERENCES groups (id) ON DELETE CASCADE,
    CONSTRAINT fk_group_members_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
);

-- Xarajatlar ------------------------------------------------------------------
CREATE TABLE expenses (
    id           INTEGER      NOT NULL,
    group_id     INTEGER      NOT NULL,
    description  VARCHAR(200) NOT NULL,
    amount       INTEGER      NOT NULL,
    paid_by      INTEGER      NOT NULL,
    category     VARCHAR(20)  NOT NULL,
    split_type   VARCHAR(20)  NOT NULL,
    expense_date DATE         NOT NULL,
    created_by   INTEGER,                      -- muallif o'chsa NULL bo'ladi
    created_at   DATETIME     NOT NULL,
    CONSTRAINT pk_expenses PRIMARY KEY (id),
    CONSTRAINT ck_expenses_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_expenses_description_not_blank CHECK (length(trim(description)) > 0),
    CONSTRAINT ck_expenses_category_valid
        CHECK (category IN ('food', 'transport', 'accommodation', 'other')),
    CONSTRAINT ck_expenses_split_type_valid
        CHECK (split_type IN ('equal', 'exact', 'percentage', 'shares')),
    -- To'lovchi shu guruh a'zosi bo'lishi shart (kompozit FK).
    CONSTRAINT fk_expenses_group_id_paid_by_group_members
        FOREIGN KEY (group_id, paid_by)
        REFERENCES group_members (group_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_expenses_group_id_groups FOREIGN KEY (group_id)
        REFERENCES groups (id) ON DELETE RESTRICT,
    CONSTRAINT fk_expenses_created_by_users FOREIGN KEY (created_by)
        REFERENCES users (id) ON DELETE SET NULL
);

-- Xarajat ulushlari (bo'lish natijasi; ongli denormalizatsiya) ---------------
CREATE TABLE expense_shares (
    expense_id   INTEGER NOT NULL,
    user_id      INTEGER NOT NULL,
    share_amount INTEGER NOT NULL,
    CONSTRAINT pk_expense_shares PRIMARY KEY (expense_id, user_id),
    CONSTRAINT ck_expense_shares_share_amount_non_negative CHECK (share_amount >= 0),
    CONSTRAINT fk_expense_shares_expense_id_expenses FOREIGN KEY (expense_id)
        REFERENCES expenses (id) ON DELETE CASCADE,
    CONSTRAINT fk_expense_shares_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE RESTRICT
);

-- Hisob-kitob to'lovlari -----------------------------------------------------
CREATE TABLE settlements (
    id           INTEGER  NOT NULL,
    group_id     INTEGER  NOT NULL,
    from_user_id INTEGER  NOT NULL,
    to_user_id   INTEGER  NOT NULL,
    amount       INTEGER  NOT NULL,
    created_at   DATETIME NOT NULL,
    CONSTRAINT pk_settlements PRIMARY KEY (id),
    CONSTRAINT ck_settlements_amount_positive CHECK (amount > 0),
    CONSTRAINT ck_settlements_different_users CHECK (from_user_id <> to_user_id),
    CONSTRAINT fk_settlements_group_id_from_user_id_group_members
        FOREIGN KEY (group_id, from_user_id)
        REFERENCES group_members (group_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_settlements_group_id_to_user_id_group_members
        FOREIGN KEY (group_id, to_user_id)
        REFERENCES group_members (group_id, user_id) ON DELETE RESTRICT,
    CONSTRAINT fk_settlements_group_id_groups FOREIGN KEY (group_id)
        REFERENCES groups (id) ON DELETE RESTRICT
);

-- Bildirishnomalar -----------------------------------------------------------
CREATE TABLE notifications (
    id         INTEGER  NOT NULL,
    user_id    INTEGER  NOT NULL,
    message    TEXT     NOT NULL,
    is_read    BOOLEAN  DEFAULT 0 NOT NULL,
    created_at DATETIME NOT NULL,
    CONSTRAINT pk_notifications PRIMARY KEY (id),
    CONSTRAINT ck_notifications_message_not_blank CHECK (length(trim(message)) > 0),
    CONSTRAINT fk_notifications_user_id_users FOREIGN KEY (user_id)
        REFERENCES users (id) ON DELETE CASCADE
);

-- Indekslar (migrations/versions/0004, 0005; asoslanishi docs/DB.md da) ------
-- UNIQUE va PRIMARY KEY o'z indeksini o'zi yaratadi, ular bu yerda takrorlanmaydi.
CREATE INDEX ix_group_members_user_id ON group_members (user_id);
CREATE INDEX ix_expenses_group_id_expense_date_id ON expenses (group_id, expense_date, id);
CREATE INDEX ix_expenses_group_id_paid_by_amount ON expenses (group_id, paid_by, amount);
CREATE INDEX ix_expense_shares_user_id ON expense_shares (user_id);
CREATE INDEX ix_settlements_group_id_created_at ON settlements (group_id, created_at);
CREATE INDEX ix_notifications_user_id_created_at ON notifications (user_id, created_at);
