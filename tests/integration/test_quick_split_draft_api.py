"""Saved quick split page: guests have none, signed-in users keep theirs."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_groups_api import auth_headers
from tests.integration.test_pages import register

URL = "/api/quick-split/draft"

DRAFT = {
    "participants": [{"id": 1, "name": "Ali"}, {"id": 2, "name": "Vali"}],
    "expenses": [
        {
            "id": 1,
            "description": "Taksi",
            "amount": 100_000,
            "paid_by": 1,
            "split_type": "equal",
            "participants": [{"user_id": 1}, {"user_id": 2}],
            "shares": [
                {"user_id": 1, "share_amount": 50_000},
                {"user_id": 2, "share_amount": 50_000},
            ],
        }
    ],
}


@pytest.fixture
def aziza(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "aziza")


def test_guest_cannot_save(db_client: TestClient) -> None:
    assert db_client.get(URL).status_code == 401
    assert db_client.put(URL, json=DRAFT).status_code == 401


def test_new_user_starts_empty(db_client, aziza) -> None:
    data = db_client.get(URL, headers=aziza).json()

    assert data == {"participants": [], "expenses": [], "updated_at": None}


def test_save_and_load_back(db_client, aziza) -> None:
    saved = db_client.put(URL, json=DRAFT, headers=aziza)

    assert saved.status_code == 200, saved.text
    loaded = db_client.get(URL, headers=aziza).json()
    assert loaded["participants"] == DRAFT["participants"]
    assert loaded["expenses"][0]["description"] == "Taksi"
    assert loaded["updated_at"] is not None


def test_save_replaces_previous(db_client, aziza) -> None:
    db_client.put(URL, json=DRAFT, headers=aziza)
    db_client.put(
        URL, json={"participants": [{"id": 7, "name": "Sardor"}]}, headers=aziza
    )

    loaded = db_client.get(URL, headers=aziza).json()
    assert loaded["participants"] == [{"id": 7, "name": "Sardor"}]
    assert loaded["expenses"] == []


def test_users_do_not_see_each_other(db_client, aziza) -> None:
    db_client.put(URL, json=DRAFT, headers=aziza)
    ramazon = auth_headers(db_client, "ramazon")

    assert db_client.get(URL, headers=ramazon).json()["participants"] == []


def test_clear(db_client, aziza) -> None:
    db_client.put(URL, json=DRAFT, headers=aziza)

    assert db_client.delete(URL, headers=aziza).status_code == 204
    assert db_client.get(URL, headers=aziza).json()["expenses"] == []


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d["participants"].append({"id": 1, "name": "Ali2"}), "id'lari"),
        (lambda d: d["participants"].append({"id": 3, "name": "ali"}), "ismlari"),
        (lambda d: d["expenses"][0].update(paid_by=9), "noma'lum"),
        (
            lambda d: d["expenses"][0]["shares"][0].update(share_amount=1),
            "Ulushlar yig'indisi",
        ),
        (lambda d: d["expenses"].append(dict(d["expenses"][0])), "Xarajatlar id"),
    ],
)
def test_inconsistent_draft_is_rejected(db_client, aziza, change, message) -> None:
    import copy

    draft = copy.deepcopy(DRAFT)
    change(draft)

    response = db_client.put(URL, json=draft, headers=aziza)
    assert response.status_code == 400
    assert message in response.json()["detail"]


def test_schema_limits(db_client, aziza) -> None:
    long_name = {"participants": [{"id": 1, "name": "x" * 21}]}
    assert db_client.put(URL, json=long_name, headers=aziza).status_code == 422
    bad_type = {
        "participants": DRAFT["participants"],
        "expenses": [dict(DRAFT["expenses"][0], split_type="random")],
    }
    assert db_client.put(URL, json=bad_type, headers=aziza).status_code == 422


# --- the page's own requests: login cookie ------------------------------------------


def test_page_saves_with_login_cookie(db_client: TestClient) -> None:
    register(db_client, "aziza")  # sets the HttpOnly cookie

    assert db_client.put(URL, json=DRAFT).status_code == 200
    assert db_client.get(URL).json()["participants"] == DRAFT["participants"]


def test_cookie_write_must_be_json(db_client: TestClient) -> None:
    """A form on another site sends the cookie but cannot send JSON (CSRF)."""
    register(db_client, "aziza")

    response = db_client.put(
        URL,
        content=b"participants=1",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 415
    assert db_client.delete(URL).status_code == 415
