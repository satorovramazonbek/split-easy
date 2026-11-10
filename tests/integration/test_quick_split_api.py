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


@pytest.mark.parametrize(
    "path",
    [
        "/static/app.js",
        "/static/theme.css",
        "/static/favicon.svg",
        "/static/vendor/bootstrap/bootstrap.min.css",
        "/static/vendor/bootstrap/bootstrap.bundle.min.js",
        "/static/fonts/inter-latin-wght-normal.woff2",
    ],
)
def test_static_files_are_served(client: TestClient, path: str) -> None:
    assert client.get(path).status_code == 200


@pytest.mark.parametrize("page", ["/", "/login", "/register"])
def test_pages_work_without_internet(client: TestClient, page: str) -> None:
    """The demo must not depend on a CDN: every asset is served locally."""
    html = client.get(page).text

    assert "cdn." not in html
    assert "https://" not in html
    assert 'id="i-users"' in html  # the icon sprite is inlined


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


def shares_body(amount: int, first_share: str) -> dict:
    return {
        "members": [1, 2],
        "expense": {
            "amount": amount,
            "paid_by": 1,
            "split_type": "shares",
            "participants": [
                {"user_id": 1, "value": first_share},
                {"user_id": 2, "value": "1"},
            ],
        },
    }


@pytest.mark.parametrize(
    ("amount", "first_share"),
    [
        (1000, "1e999999"),  # huge number -> huge exact fraction
        (1000, "1e-999999"),  # tiny number -> huge denominator
        (1000, "0.0000001"),  # more than 6 decimal places
        (10**15 + 1, "1"),  # amount above the limit
    ],
)
def test_preview_rejects_values_outside_limits(
    client: TestClient, amount: int, first_share: str
) -> None:
    response = client.post(
        "/api/expenses/preview", json=shares_body(amount, first_share)
    )

    assert response.status_code == 422


def test_preview_accepts_values_at_limits(client: TestClient) -> None:
    response = client.post(
        "/api/expenses/preview", json=shares_body(10**15, "0.000001")
    )

    assert response.status_code == 200
    assert sum(s["share_amount"] for s in response.json()["shares"]) == 10**15
