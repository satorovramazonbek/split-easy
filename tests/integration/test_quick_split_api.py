import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def expense(amount: int, paid_by: int, members=(1, 2, 3, 4)) -> dict:
    return {
        "description": "test",
        "amount": amount,
        "paid_by": paid_by,
        "split_type": "equal",
        "participants": [{"user_id": user_id} for user_id in members],
    }


def test_index_page_is_served(client: TestClient) -> None:
    response = client.get("/")

    assert response.status_code == 200
    assert "SplitEasy" in response.text
    assert "/static/app.js" in response.text


def test_static_files_are_served(client: TestClient) -> None:
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/style.css").status_code == 200


def test_preview_returns_shares(client: TestClient) -> None:
    response = client.post(
        "/api/expenses/preview",
        json={"members": [1, 2, 3], "expense": expense(100, 1, members=(1, 2, 3))},
    )

    assert response.status_code == 200
    assert response.json() == {
        "shares": [
            {"user_id": 1, "share_amount": 34},
            {"user_id": 2, "share_amount": 33},
            {"user_id": 3, "share_amount": 33},
        ]
    }


def test_preview_percentages_from_strings(client: TestClient) -> None:
    body = {
        "members": [1, 2],
        "expense": {
            "amount": 1000,
            "paid_by": 1,
            "split_type": "percentage",
            "participants": [
                {"user_id": 1, "value": "40"},
                {"user_id": 2, "value": "60"},
            ],
        },
    }

    response = client.post("/api/expenses/preview", json=body)

    assert response.status_code == 200
    assert [s["share_amount"] for s in response.json()["shares"]] == [400, 600]


def test_preview_invalid_split_returns_400(client: TestClient) -> None:
    body = {
        "members": [1, 2],
        "expense": {
            "amount": 1000,
            "paid_by": 1,
            "split_type": "percentage",
            "participants": [
                {"user_id": 1, "value": "40"},
                {"user_id": 2, "value": "50"},
            ],
        },
    }

    response = client.post("/api/expenses/preview", json=body)

    assert response.status_code == 400
    assert "100" in response.json()["detail"]


def test_calculate_readme_example(client: TestClient) -> None:
    body = {
        "members": [1, 2, 3, 4],
        "expenses": [expense(400_000, 1), expense(100_000, 2), expense(300_000, 3)],
    }

    response = client.post("/api/calculate", json=body)

    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 800_000
    assert [m["balance"] for m in data["members"]] == [
        200_000,
        -100_000,
        100_000,
        -200_000,
    ]
    assert data["transfers"] == [
        {"from_user_id": 4, "to_user_id": 1, "amount": 200_000},
        {"from_user_id": 2, "to_user_id": 3, "amount": 100_000},
    ]


def test_calculate_rejects_unknown_payer(client: TestClient) -> None:
    body = {"members": [1, 2], "expenses": [expense(100, 7, members=(1, 2))]}

    response = client.post("/api/calculate", json=body)

    assert response.status_code == 400


def test_calculate_rejects_non_positive_amount(client: TestClient) -> None:
    body = {"members": [1, 2], "expenses": [expense(0, 1, members=(1, 2))]}

    response = client.post("/api/calculate", json=body)

    assert response.status_code == 400
