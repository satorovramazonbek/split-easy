"""Raw SQL reports on a small hand-made dataset (spec section 10.2).

Group "Sayohat" (UZS): aziza (owner), ramazon, ali, vali (never takes part).
    e1 2026-09-05 food           300 000  paid aziza   -> aziza, ramazon, ali 100 000
    e2 2026-09-20 transport       90 000  paid ramazon -> aziza, ramazon     45 000
    e3 2026-10-02 accommodation  600 000  paid ali     -> aziza, ramazon, ali 200 000
    e4 2026-10-02 food            10 000  paid aziza   -> aziza, ali           5 000
    settlement: ramazon -> aziza 50 000
Group "Ish" (USD): ramazon (owner), aziza.
    e5 2026-10-10 food 100 000 paid ramazon -> ramazon, aziza 50 000
Group "Eski" (UZS, deleted): aziza only.
"""

from datetime import UTC, date, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import insert, update
from sqlalchemy.orm import Session

from app.domain.balance import calculate_balances
from app.domain.models import (
    Category,
    Expense,
    ExpenseShare,
    Group,
    GroupMember,
    Settlement,
    SplitType,
    User,
)
from app.repositories.interfaces.report_repository import (
    CategoryTotal,
    CurrencyTotals,
    GroupPosition,
    MonthlyTotal,
)
from app.repositories.sqlalchemy.group_repository import SqlAlchemyGroupRepository
from app.repositories.sqlalchemy.orm_models import (
    ExpenseORM,
    ExpenseShareORM,
    GroupORM,
    SettlementORM,
)
from app.repositories.sqlalchemy.report_repository import SqlAlchemyReportRepository
from app.repositories.sqlalchemy.user_repository import SqlAlchemyUserRepository

NOW = datetime(2026, 11, 7, 12, 0, tzinfo=UTC)


class Data:
    def __init__(self) -> None:
        self.users: dict[str, int] = {}
        self.groups: dict[str, int] = {}
        self.expenses: dict[str, list[Expense]] = {}
        self.settlements: dict[str, list[Settlement]] = {}


def _add_expense(session, data, group, key, day, category, amount, payer, shares):
    group_id = data.groups[group]
    expense_id = session.execute(
        insert(ExpenseORM.__table__).values(
            group_id=group_id,
            description=key,
            amount=amount,
            paid_by=data.users[payer],
            category=category.value,
            split_type=SplitType.EXACT.value,
            expense_date=day,
            created_by=data.users[payer],
            created_at=NOW,
        )
    ).lastrowid
    session.execute(
        insert(ExpenseShareORM.__table__),
        [
            {"expense_id": expense_id, "user_id": data.users[u], "share_amount": s}
            for u, s in shares.items()
        ],
    )
    data.expenses.setdefault(group, []).append(
        Expense(
            id=expense_id,
            group_id=group_id,
            description=key,
            amount=amount,
            paid_by=data.users[payer],
            split_type=SplitType.EXACT,
            shares=tuple(ExpenseShare(data.users[u], s) for u, s in shares.items()),
            category=category,
            expense_date=day,
        )
    )
    return expense_id


@pytest.fixture
def data(session: Session) -> Data:
    data = Data()
    users = SqlAlchemyUserRepository(session)
    groups = SqlAlchemyGroupRepository(session)
    for name in ("aziza", "ramazon", "ali", "vali", "bob"):
        data.users[name] = users.add(
            User(
                id=None,
                username=name,
                email=f"{name}@example.com",
                password_hash="x",
                created_at=NOW,
            )
        ).id

    def group(name, currency, owner, members):
        group_id = groups.add(
            Group(
                id=None,
                name=name,
                currency=currency,
                owner_id=data.users[owner],
                created_at=NOW,
            )
        ).id
        for member in members:
            groups.add_member(GroupMember(group_id, data.users[member], NOW))
        data.groups[name] = group_id

    group("Sayohat", "UZS", "aziza", ["aziza", "ramazon", "ali", "vali"])
    group("Ish", "USD", "ramazon", ["ramazon", "aziza"])
    group("Eski", "UZS", "aziza", ["aziza"])
    session.execute(
        update(GroupORM).where(GroupORM.id == data.groups["Eski"]).values(is_deleted=1)
    )

    add = _add_expense
    add(session, data, "Sayohat", "e1", date(2026, 9, 5), Category.FOOD, 300_000,
        "aziza", {"aziza": 100_000, "ramazon": 100_000, "ali": 100_000})  # fmt: skip
    add(session, data, "Sayohat", "e2", date(2026, 9, 20), Category.TRANSPORT, 90_000,
        "ramazon", {"aziza": 45_000, "ramazon": 45_000})  # fmt: skip
    add(session, data, "Sayohat", "e3", date(2026, 10, 2), Category.ACCOMMODATION,
        600_000, "ali", {"aziza": 200_000, "ramazon": 200_000, "ali": 200_000})  # fmt: skip
    add(session, data, "Sayohat", "e4", date(2026, 10, 2), Category.FOOD, 10_000,
        "aziza", {"aziza": 5_000, "ali": 5_000})  # fmt: skip
    add(session, data, "Ish", "e5", date(2026, 10, 10), Category.FOOD, 100_000,
        "ramazon", {"ramazon": 50_000, "aziza": 50_000})  # fmt: skip

    session.execute(
        insert(SettlementORM.__table__).values(
            group_id=data.groups["Sayohat"],
            from_user_id=data.users["ramazon"],
            to_user_id=data.users["aziza"],
            amount=50_000,
            created_at=NOW,
        )
    )
    data.settlements["Sayohat"] = [
        Settlement(
            id=None,
            group_id=data.groups["Sayohat"],
            from_user_id=data.users["ramazon"],
            to_user_id=data.users["aziza"],
            amount=50_000,
        )
    ]
    session.commit()
    return data


@pytest.fixture
def reports(session: Session) -> SqlAlchemyReportRepository:
    return SqlAlchemyReportRepository(session)


def by_name(data: Data, rows, attr: str = "user_id") -> dict:
    names = {v: k for k, v in data.users.items()}
    return {names[getattr(row, attr)]: row for row in rows}


def test_1_member_balances(reports, data) -> None:
    rows = by_name(data, reports.member_balances(data.groups["Sayohat"]))

    assert {name: row.balance for name, row in rows.items()} == {
        "aziza": -90_000,
        "ramazon": -205_000,
        "ali": 295_000,
        "vali": 0,
    }
    aziza = rows["aziza"]
    assert (aziza.paid, aziza.owed, aziza.sent, aziza.received) == (
        310_000,
        350_000,
        0,
        50_000,
    )
    assert sum(row.balance for row in rows.values()) == 0


@pytest.mark.parametrize("group", ["Sayohat", "Ish"])
def test_1_sql_balances_equal_domain_calculation(reports, data, group) -> None:
    """Cross-check required by the spec: SQL result == Python domain result."""
    group_id = data.groups[group]
    sql = {row.user_id: row.balance for row in reports.member_balances(group_id)}

    domain = calculate_balances(
        data.expenses[group],
        data.settlements.get(group, []),
        member_ids=sql.keys(),
    )

    assert sql == domain


def test_2_category_totals(reports, data) -> None:
    assert reports.category_totals(data.groups["Sayohat"]) == [
        CategoryTotal("accommodation", 1, 600_000),
        CategoryTotal("food", 2, 310_000),
        CategoryTotal("transport", 1, 90_000),
    ]


def test_3_monthly_totals(reports, data) -> None:
    assert reports.monthly_totals(data.groups["Sayohat"]) == [
        MonthlyTotal("2026-09", 2, 390_000),
        MonthlyTotal("2026-10", 2, 610_000),
    ]


def test_4_top_payers(reports, data) -> None:
    rows = reports.top_payers(data.groups["Sayohat"])

    assert [(r.username, r.expense_count, r.total_paid) for r in rows] == [
        ("ali", 1, 600_000),
        ("aziza", 2, 310_000),
        ("ramazon", 1, 90_000),
    ]
    assert len(reports.top_payers(data.groups["Sayohat"], limit=2)) == 2


def test_5_inactive_members(reports, data) -> None:
    assert [r.username for r in reports.inactive_members(data.groups["Sayohat"])] == [
        "vali"
    ]
    assert reports.inactive_members(data.groups["Ish"]) == []


def test_6_above_average_expenses(reports, data) -> None:
    rows = reports.above_average_expenses(data.groups["Sayohat"])

    assert [(r.description, r.amount) for r in rows] == [
        ("e3", 600_000),
        ("e1", 300_000),
    ]
    assert rows[0].group_average == 250_000
    assert rows[0].expense_date == date(2026, 10, 2)


def test_7_running_total(reports, data) -> None:
    rows = reports.running_total(data.groups["Sayohat"])

    assert [r.running_total for r in rows] == [300_000, 390_000, 990_000, 1_000_000]
    assert rows[-1].running_total == sum(r.amount for r in rows)


def test_8_user_overview(reports, data) -> None:
    aziza = reports.user_overview(data.users["aziza"])

    assert aziza.groups == [
        GroupPosition(data.groups["Sayohat"], "Sayohat", "UZS", -90_000),
        GroupPosition(data.groups["Ish"], "Ish", "USD", -50_000),
    ]  # the deleted group "Eski" is not listed
    assert aziza.totals == [
        CurrencyTotals("USD", you_owe=50_000, owed_to_you=0),
        CurrencyTotals("UZS", you_owe=90_000, owed_to_you=0),
    ]

    ramazon = reports.user_overview(data.users["ramazon"])
    assert [g.balance for g in ramazon.groups] == [-205_000, 50_000]


def test_8_user_overview_matches_member_balances(reports, data) -> None:
    for name, user_id in data.users.items():
        for position in reports.user_overview(user_id).groups:
            balances = {
                r.user_id: r.balance for r in reports.member_balances(position.group_id)
            }
            assert position.balance == balances[user_id], name


def test_user_without_groups(reports, data) -> None:
    overview = reports.user_overview(data.users["bob"])

    assert overview.groups == [] and overview.totals == []


def test_empty_group_reports(reports, data) -> None:
    group_id = data.groups["Eski"]

    assert reports.category_totals(group_id) == []
    assert reports.above_average_expenses(group_id) == []
    assert reports.running_total(group_id) == []


def test_parameters_are_bound_not_concatenated(reports, data) -> None:
    """A malicious "id" is just a value that matches nothing."""
    assert reports.category_totals("1 OR 1=1") == []  # type: ignore[arg-type]


# --- API -------------------------------------------------------------------


def token(client: TestClient, username: str) -> dict[str, str]:
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secret123",
        },
    )
    access = client.post(
        "/api/auth/login", data={"username": username, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {access}"}


@pytest.mark.parametrize(
    "report",
    [
        "balances",
        "categories",
        "monthly",
        "top-payers",
        "inactive-members",
        "above-average",
        "running-total",
    ],
)
def test_report_endpoints_and_access(db_client: TestClient, report: str) -> None:
    owner, stranger = token(db_client, "aziza"), token(db_client, "ramazon")
    group_id = db_client.post("/api/groups", json={"name": "X"}, headers=owner).json()[
        "id"
    ]
    url = f"/api/groups/{group_id}/reports/{report}"

    assert db_client.get(url, headers=owner).status_code == 200
    assert db_client.get(url, headers=stranger).status_code == 403
    assert db_client.get(url).status_code == 401
    missing = f"/api/groups/999/reports/{report}"
    assert db_client.get(missing, headers=owner).status_code == 404


def test_balances_endpoint_lists_members(db_client: TestClient) -> None:
    owner = token(db_client, "aziza")
    group_id = db_client.post("/api/groups", json={"name": "X"}, headers=owner).json()[
        "id"
    ]

    body = db_client.get(
        f"/api/groups/{group_id}/reports/balances", headers=owner
    ).json()

    assert body == [
        {
            "user_id": 1,
            "username": "aziza",
            "paid": 0,
            "owed": 0,
            "sent": 0,
            "received": 0,
            "balance": 0,
        }
    ]


def test_overview_endpoint(db_client: TestClient) -> None:
    owner = token(db_client, "aziza")
    db_client.post("/api/groups", json={"name": "X", "currency": "USD"}, headers=owner)

    body = db_client.get("/api/reports/overview", headers=owner).json()

    assert body["groups"][0]["balance"] == 0
    assert body["totals"] == [{"currency": "USD", "you_owe": 0, "owed_to_you": 0}]
