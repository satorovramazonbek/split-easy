"""API: edit (FR-12), category filter (FR-14), member removal (FR-7), export (FR-24/25)."""

import csv
import io

from fastapi.testclient import TestClient

from tests.integration.test_expenses_api import (  # noqa: F401  (fixtures)
    add_expense,
    aziza,
    balances,
    bobur,
    group,
    ramazon,
)
from tests.integration.test_groups_api import auth_headers


def url(group: dict, path: str = "") -> str:
    return f"/api/groups/{group['id']}{path}"


# --- FR-12: edit --------------------------------------------------------------------


def test_author_edits_expense_with_put(db_client: TestClient, group, ramazon) -> None:
    expense_id = add_expense(
        db_client, group, ramazon, paid_by=group["ramazon"]
    ).json()["id"]

    response = db_client.put(
        url(group, f"/expenses/{expense_id}"),
        json={
            "description": "Ovqat (tuzatildi)",
            "amount": 90_000,
            "paid_by": group["ramazon"],
            "split_type": "exact",
            "category": "food",
            "participants": [
                {"user_id": group["ramazon"], "value": 30_000},
                {"user_id": group["bobur"], "value": 60_000},
            ],
        },
        headers=ramazon,
    )

    assert response.status_code == 200, response.text
    data = response.json()
    assert data["description"] == "Ovqat (tuzatildi)"
    assert {s["user_id"]: s["share_amount"] for s in data["shares"]} == {
        group["ramazon"]: 30_000,
        group["bobur"]: 60_000,
    }
    assert balances(db_client, group, ramazon)[group["bobur"]] == -60_000


def test_owner_may_edit_others_may_not(db_client, group, aziza, ramazon, bobur) -> None:
    expense = add_expense(db_client, group, ramazon, paid_by=group["ramazon"]).json()
    body = {
        "description": "Yangi",
        "amount": 1_000,
        "paid_by": group["ramazon"],
        "participants": [{"user_id": group["ramazon"]}],
    }
    path = url(group, f"/expenses/{expense['id']}")

    assert db_client.put(path, json=body, headers=bobur).status_code == 403
    assert db_client.put(path, json=body, headers=aziza).status_code == 200
    assert (
        db_client.put(url(group, "/expenses/999"), json=body, headers=aziza).status_code
        == 404
    )


# --- FR-14: category filter -----------------------------------------------------------


def test_category_filter(db_client, group, aziza) -> None:
    add_expense(db_client, group, aziza, category="food")
    add_expense(db_client, group, aziza, category="transport", description="Taksi")

    food = db_client.get(url(group, "/expenses?category=food"), headers=aziza).json()
    bad = db_client.get(url(group, "/expenses?category=cars"), headers=aziza)

    assert [e["category"] for e in food["items"]] == ["food"]
    assert food["total"] == 1
    assert bad.status_code == 422


# --- FR-7: remove a member only at balance 0 -----------------------------------------


def test_member_is_removed_only_after_the_debt_is_settled(
    db_client, group, aziza, ramazon
) -> None:
    add_expense(db_client, group, aziza)  # ramazon owes 100 000
    member = url(group, f"/members/{group['ramazon']}")

    refused = db_client.delete(member, headers=aziza)
    assert refused.status_code == 409
    assert "balansi 0 emas" in refused.json()["detail"]

    db_client.post(
        url(group, "/settlements"),
        json={
            "from_user_id": group["ramazon"],
            "to_user_id": group["aziza"],
            "amount": 100_000,
        },
        headers=ramazon,
    )
    assert db_client.delete(member, headers=aziza).status_code == 204

    # ramazon no longer sees the group, the history stays and still adds up
    assert db_client.get(url(group), headers=ramazon).status_code == 403
    assert db_client.get(url(group, "/expenses"), headers=aziza).json()["total"] == 1
    assert sum(balances(db_client, group, aziza).values()) == 0
    # and he can be added again
    again = db_client.post(
        url(group, "/members"), json={"login": "ramazon"}, headers=aziza
    )
    assert again.status_code == 201


# --- FR-24, FR-25: export --------------------------------------------------------------


def test_export_csv(db_client, group, aziza) -> None:
    add_expense(db_client, group, aziza, description="Ovqat, kechki")

    response = db_client.get(url(group, "/export?format=csv"), headers=aziza)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "attachment" in response.headers["content-disposition"]
    rows = list(csv.reader(io.StringIO(response.text)))
    assert rows[1][1] == "Ovqat, kechki"
    assert rows[1][5] == "aziza"


def test_export_json_and_errors(db_client, group, aziza) -> None:
    add_expense(db_client, group, aziza)
    outsider_headers = auth_headers(db_client, "begona")

    data = db_client.get(url(group, "/export?format=json"), headers=aziza).json()
    assert data[0]["shares"][0]["share_amount"] == 100_000
    assert (
        db_client.get(url(group, "/export?format=xml"), headers=aziza).status_code
        == 400
    )
    assert (
        db_client.get(url(group, "/export"), headers=outsider_headers).status_code
        == 403
    )
    assert db_client.get("/api/groups/999/export", headers=aziza).status_code == 404
