"""Group expenses, settlements and notifications through the JSON API."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_groups_api import auth_headers


@pytest.fixture
def aziza(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "aziza")


@pytest.fixture
def ramazon(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "ramazon")


@pytest.fixture
def bobur(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "bobur")


def me(client: TestClient, headers) -> int:
    return client.get("/api/auth/me", headers=headers).json()["id"]


@pytest.fixture
def group(db_client: TestClient, aziza, ramazon, bobur) -> dict:
    """Group of aziza (owner), ramazon and bobur."""
    group_id = db_client.post(
        "/api/groups", json={"name": "Sayohat"}, headers=aziza
    ).json()["id"]
    for login in ("ramazon", "bobur"):
        response = db_client.post(
            f"/api/groups/{group_id}/members", json={"login": login}, headers=aziza
        )
        assert response.status_code == 201, response.text
    return {
        "id": group_id,
        "aziza": me(db_client, aziza),
        "ramazon": me(db_client, ramazon),
        "bobur": me(db_client, bobur),
    }


def add_expense(client, group, headers, **overrides):
    body = {
        "description": "Ovqat",
        "amount": 300_000,
        "paid_by": group["aziza"],
        "split_type": "equal",
        "category": "food",
        "participants": [
            {"user_id": group[name]} for name in ("aziza", "ramazon", "bobur")
        ],
    }
    body.update(overrides)
    return client.post(
        f"/api/groups/{group['id']}/expenses", json=body, headers=headers
    )


def balances(client, group, headers) -> dict[int, int]:
    rows = client.get(
        f"/api/groups/{group['id']}/reports/balances", headers=headers
    ).json()
    return {row["user_id"]: row["balance"] for row in rows}


# --- adding expenses -----------------------------------------------------------


def test_add_equal_expense_is_saved_and_changes_balances(
    db_client, group, aziza, ramazon
) -> None:
    response = add_expense(db_client, group, aziza)

    assert response.status_code == 201, response.text
    data = response.json()
    assert data["amount"] == 300_000
    assert data["created_by"] == group["aziza"]
    assert sorted(s["share_amount"] for s in data["shares"]) == [100_000] * 3
    # Visible to another member, from the database.
    listed = db_client.get(f"/api/groups/{group['id']}/expenses", headers=ramazon)
    assert listed.json()["total"] == 1
    assert balances(db_client, group, ramazon) == {
        group["aziza"]: 200_000,
        group["ramazon"]: -100_000,
        group["bobur"]: -100_000,
    }


@pytest.mark.parametrize(
    ("split_type", "values", "expected"),
    [
        ("exact", [50_000, 100_000, 150_000], [50_000, 100_000, 150_000]),
        ("percentage", ["50", "25", "25"], [150_000, 75_000, 75_000]),
        ("shares", [2, 1, 0.5], [171_429, 85_714, 42_857]),
    ],
)
def test_other_split_types(
    db_client, group, aziza, split_type, values, expected
) -> None:
    people = ("aziza", "ramazon", "bobur")
    response = add_expense(
        db_client,
        group,
        aziza,
        split_type=split_type,
        participants=[
            {"user_id": group[n], "value": v} for n, v in zip(people, values)
        ],
    )

    assert response.status_code == 201, response.text
    shares = {s["user_id"]: s["share_amount"] for s in response.json()["shares"]}
    assert [shares[group[n]] for n in people] == expected
    assert sum(shares.values()) == 300_000


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"split_type": "exact", "participants": "values:1,2,3"},
            "Aniq summalar yig'indisi",
        ),
        (
            {"split_type": "percentage", "participants": "values:10,10,10"},
            "Foizlar yig'indisi 100",
        ),
        ({"split_type": "shares", "participants": "values:none"}, "qiymat kiriting"),
        ({"description": "   "}, "tavsifini kiriting"),
    ],
)
def test_invalid_split_is_rejected_in_uzbek(
    db_client, group, aziza, overrides, message
) -> None:
    participants = overrides.pop("participants", None)
    if participants:
        raw = participants.removeprefix("values:")
        values = [None] * 3 if raw == "none" else raw.split(",")
        overrides["participants"] = [
            {"user_id": group[n], "value": v}
            for n, v in zip(("aziza", "ramazon", "bobur"), values)
        ]

    response = add_expense(db_client, group, aziza, **overrides)

    assert response.status_code == 400
    assert message in response.json()["detail"]
    assert (
        db_client.get(f"/api/groups/{group['id']}/expenses", headers=aziza).json()[
            "total"
        ]
        == 0
    )


def test_payer_and_participants_must_be_members(db_client, group, aziza) -> None:
    outsider = me(db_client, auth_headers(db_client, "begona"))

    assert add_expense(db_client, group, aziza, paid_by=outsider).status_code == 400
    response = add_expense(
        db_client, group, aziza, participants=[{"user_id": outsider}]
    )
    assert response.status_code == 400
    assert "guruh a'zosi" in response.json()["detail"]


def test_request_validation(db_client, group, aziza) -> None:
    assert add_expense(db_client, group, aziza, amount=0).status_code == 422
    assert add_expense(db_client, group, aziza, amount=10.5).status_code == 422
    assert add_expense(db_client, group, aziza, participants=[]).status_code == 422
    assert add_expense(db_client, group, aziza, category="cars").status_code == 422


def test_access_rules(db_client, group, aziza) -> None:
    outsider = auth_headers(db_client, "begona")

    assert add_expense(db_client, group, outsider).status_code == 403
    assert (
        db_client.get(f"/api/groups/{group['id']}/expenses", headers=outsider)
    ).status_code == 403
    assert db_client.get(f"/api/groups/{group['id']}/expenses").status_code == 401
    assert db_client.get("/api/groups/999/expenses", headers=aziza).status_code == 404


def test_list_is_paginated_newest_first(db_client, group, aziza) -> None:
    for day in range(1, 6):
        add_expense(
            db_client,
            group,
            aziza,
            description=f"X{day}",
            expense_date=f"2026-11-0{day}",
        )

    page = db_client.get(
        f"/api/groups/{group['id']}/expenses?limit=2&offset=1", headers=aziza
    ).json()

    assert page["total"] == 5
    assert [e["description"] for e in page["items"]] == ["X4", "X3"]


def test_get_expense(db_client, group, aziza) -> None:
    expense_id = add_expense(db_client, group, aziza).json()["id"]

    url = f"/api/groups/{group['id']}/expenses/{expense_id}"
    assert db_client.get(url, headers=aziza).json()["description"] == "Ovqat"
    assert (
        db_client.get(f"/api/groups/{group['id']}/expenses/999", headers=aziza)
    ).status_code == 404


def test_expense_of_another_group_is_not_found(db_client, group, aziza) -> None:
    other = db_client.post("/api/groups", json={"name": "Boshqa"}, headers=aziza)
    expense_id = add_expense(db_client, group, aziza).json()["id"]

    response = db_client.get(
        f"/api/groups/{other.json()['id']}/expenses/{expense_id}", headers=aziza
    )
    assert response.status_code == 404


# --- deleting --------------------------------------------------------------------


def test_author_and_owner_can_delete_others_cannot(
    db_client, group, aziza, ramazon, bobur
) -> None:
    by_ramazon = add_expense(
        db_client, group, ramazon, paid_by=group["ramazon"]
    ).json()["id"]
    url = f"/api/groups/{group['id']}/expenses/{by_ramazon}"

    assert db_client.delete(url, headers=bobur).status_code == 403
    assert db_client.delete(url, headers=aziza).status_code == 204  # owner
    assert db_client.get(url, headers=aziza).status_code == 404

    own = add_expense(db_client, group, bobur, paid_by=group["bobur"]).json()["id"]
    assert (
        db_client.delete(
            f"/api/groups/{group['id']}/expenses/{own}", headers=bobur
        ).status_code
        == 204
    )
    assert balances(db_client, group, aziza) == dict.fromkeys(group_ids(group), 0)


def group_ids(group) -> list[int]:
    return [group["aziza"], group["ramazon"], group["bobur"]]


# --- settlements -------------------------------------------------------------------


def test_settlement_clears_debt(db_client, group, aziza, ramazon) -> None:
    add_expense(db_client, group, aziza)

    response = db_client.post(
        f"/api/groups/{group['id']}/settlements",
        json={
            "from_user_id": group["ramazon"],
            "to_user_id": group["aziza"],
            "amount": 100_000,
        },
        headers=ramazon,
    )

    assert response.status_code == 201, response.text
    assert balances(db_client, group, aziza)[group["ramazon"]] == 0
    history = db_client.get(
        f"/api/groups/{group['id']}/settlements", headers=aziza
    ).json()
    assert [(s["from_user_id"], s["amount"]) for s in history] == [
        (group["ramazon"], 100_000)
    ]


def test_settlement_rules(db_client, group, aziza, ramazon, bobur) -> None:
    url = f"/api/groups/{group['id']}/settlements"

    def settle(headers, frm, to, amount=1000):
        return db_client.post(
            url,
            json={
                "from_user_id": group[frm],
                "to_user_id": group[to],
                "amount": amount,
            },
            headers=headers,
        )

    # bobur is neither party nor owner
    assert settle(bobur, "ramazon", "aziza").status_code == 403
    # the owner may record any payment
    assert settle(aziza, "ramazon", "bobur").status_code == 201
    response = settle(ramazon, "ramazon", "ramazon")
    assert response.status_code == 400
    assert "O'zingizga" in response.json()["detail"]
    assert settle(ramazon, "ramazon", "aziza", amount=0).status_code == 422
    outsider = me(db_client, auth_headers(db_client, "begona"))
    response = db_client.post(
        url,
        json={"from_user_id": group["aziza"], "to_user_id": outsider, "amount": 5},
        headers=aziza,
    )
    assert response.status_code == 400


# --- notifications -----------------------------------------------------------------


def test_participants_are_notified(db_client, group, aziza, ramazon) -> None:
    add_expense(db_client, group, aziza)

    assert db_client.get("/api/notifications/unread-count", headers=aziza).json() == {
        "unread": 0
    }  # the author is not notified
    items = db_client.get("/api/notifications", headers=ramazon).json()
    assert len(items) == 1
    assert "Ovqat" in items[0]["message"]
    assert "100 000" in items[0]["message"]
    assert items[0]["is_read"] is False


def test_settlement_notifies_the_other_party(db_client, group, aziza, ramazon) -> None:
    db_client.post(
        f"/api/groups/{group['id']}/settlements",
        json={
            "from_user_id": group["ramazon"],
            "to_user_id": group["aziza"],
            "amount": 5000,
        },
        headers=ramazon,
    )

    items = db_client.get("/api/notifications", headers=aziza).json()
    assert [("ramazon → aziza" in n["message"]) for n in items] == [True]
    assert db_client.get("/api/notifications", headers=ramazon).json() == []


def test_mark_read(db_client, group, aziza, ramazon) -> None:
    add_expense(db_client, group, aziza)
    add_expense(db_client, group, aziza, description="Taksi")
    first = db_client.get("/api/notifications", headers=ramazon).json()[0]["id"]

    # someone else's notification looks missing
    assert (
        db_client.post(f"/api/notifications/{first}/read", headers=aziza).status_code
        == 404
    )
    assert (
        db_client.post(f"/api/notifications/{first}/read", headers=ramazon)
    ).status_code == 204
    unread = db_client.get(
        "/api/notifications?unread_only=true", headers=ramazon
    ).json()
    assert len(unread) == 1
    assert db_client.post("/api/notifications/read-all", headers=ramazon).json() == {
        "marked": 1
    }
    assert db_client.get("/api/notifications/unread-count", headers=ramazon).json() == {
        "unread": 0
    }


def test_expense_and_notifications_are_saved_together(
    db_client, group, aziza, monkeypatch
) -> None:
    """Unit of Work: if the notifications cannot be written, no expense is kept."""
    from app.repositories.sqlalchemy.notification_repository import (
        SqlAlchemyNotificationRepository,
    )

    def broken(self, notifications):
        list(notifications)
        raise RuntimeError("disk full")

    monkeypatch.setattr(SqlAlchemyNotificationRepository, "add_many", broken)
    client = TestClient(db_client.app, raise_server_exceptions=False)

    assert add_expense(client, group, aziza).status_code == 500
    monkeypatch.undo()
    listed = db_client.get(f"/api/groups/{group['id']}/expenses", headers=aziza)
    assert listed.json()["total"] == 0
