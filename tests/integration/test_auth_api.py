from fastapi.testclient import TestClient

USER = {"username": "aziza", "email": "aziza@example.com", "password": "secret123"}


def register(client: TestClient, **overrides) -> dict:
    response = client.post("/api/auth/register", json={**USER, **overrides})
    assert response.status_code == 201, response.text
    return response.json()


def login(client: TestClient, login: str = "aziza", password: str = "secret123"):
    return client.post(
        "/api/auth/login", data={"username": login, "password": password}
    )


def test_register_returns_user_without_password(db_client: TestClient) -> None:
    data = register(db_client)

    assert data["id"] == 1
    assert data["username"] == "aziza"
    assert data["email"] == "aziza@example.com"
    assert "password" not in data
    assert "password_hash" not in data


def test_register_duplicate_returns_409(db_client: TestClient) -> None:
    register(db_client)

    response = db_client.post(
        "/api/auth/register", json={**USER, "email": "new@example.com"}
    )

    assert response.status_code == 409


def test_register_validates_input(db_client: TestClient) -> None:
    for bad in (
        {"password": "short"},
        {"email": "not-an-email"},
        {"username": "ab"},
        {"username": "bad name!"},
    ):
        response = db_client.post("/api/auth/register", json={**USER, **bad})
        assert response.status_code == 422, bad


def test_login_returns_bearer_token(db_client: TestClient) -> None:
    register(db_client)

    response = login(db_client)

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]


def test_login_with_email(db_client: TestClient) -> None:
    register(db_client)

    assert login(db_client, login="aziza@example.com").status_code == 200


def test_login_wrong_password_returns_401(db_client: TestClient) -> None:
    register(db_client)

    response = login(db_client, password="wrong-password")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_with_token(db_client: TestClient) -> None:
    register(db_client)
    token = login(db_client).json()["access_token"]

    response = db_client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["username"] == "aziza"


def test_me_without_token_returns_401(db_client: TestClient) -> None:
    assert db_client.get("/api/auth/me").status_code == 401


def test_me_with_invalid_token_returns_401(db_client: TestClient) -> None:
    response = db_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid"}
    )

    assert response.status_code == 401
