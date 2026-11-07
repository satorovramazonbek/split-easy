import pytest
from fastapi.testclient import TestClient


def auth_headers(client: TestClient, username: str) -> dict[str, str]:
    client.post(
        "/api/auth/register",
        json={
            "username": username,
            "email": f"{username}@example.com",
            "password": "secret123",
        },
    )
    token = client.post(
        "/api/auth/login", data={"username": username, "password": "secret123"}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def aziza(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "aziza")


@pytest.fixture
def ramazon(db_client: TestClient) -> dict[str, str]:
    return auth_headers(db_client, "ramazon")


@pytest.fixture
def group_id(db_client: TestClient, aziza) -> int:
    response = db_client.post("/api/groups", json={"name": "Sayohat"}, headers=aziza)
    assert response.status_code == 201, response.text
    return response.json()["id"]


def members(client: TestClient, group_id: int, headers) -> list[str]:
    data = client.get(f"/api/groups/{group_id}", headers=headers).json()
    return [m["username"] for m in data["members"]]


def test_requires_authentication(db_client: TestClient) -> None:
    assert db_client.get("/api/groups").status_code == 401
    assert db_client.post("/api/groups", json={"name": "X"}).status_code == 401


def test_create_group(db_client: TestClient, aziza) -> None:
    response = db_client.post(
        "/api/groups", json={"name": "Sayohat", "currency": "usd"}, headers=aziza
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Sayohat"
    assert data["currency"] == "USD"
    assert data["members"][0]["username"] == "aziza"
    assert data["members"][0]["is_owner"] is True


@pytest.mark.parametrize(
    "body", [{"name": ""}, {"name": "x" * 101}, {"name": "Uy", "currency": "SOM1"}]
)
def test_create_group_validation(db_client: TestClient, aziza, body) -> None:
    assert db_client.post("/api/groups", json=body, headers=aziza).status_code == 422


def test_blank_name_returns_400(db_client: TestClient, aziza) -> None:
    response = db_client.post("/api/groups", json={"name": "   "}, headers=aziza)

    assert response.status_code == 400


def test_list_my_groups(db_client: TestClient, aziza, ramazon, group_id) -> None:
    db_client.post("/api/groups", json={"name": "Boshqa"}, headers=ramazon)

    response = db_client.get("/api/groups", headers=aziza)

    assert response.status_code == 200
    assert [g["name"] for g in response.json()] == ["Sayohat"]


def test_add_member_and_access(db_client: TestClient, aziza, ramazon, group_id):
    assert db_client.get(f"/api/groups/{group_id}", headers=ramazon).status_code == 403
    assert db_client.get("/api/groups/999", headers=ramazon).status_code == 404

    response = db_client.post(
        f"/api/groups/{group_id}/members", json={"login": "ramazon"}, headers=aziza
    )

    assert response.status_code == 201
    assert members(db_client, group_id, ramazon) == ["aziza", "ramazon"]
    assert [g["id"] for g in db_client.get("/api/groups", headers=ramazon).json()] == [
        group_id
    ]


def test_add_member_errors(db_client: TestClient, aziza, ramazon, group_id) -> None:
    url = f"/api/groups/{group_id}/members"

    assert db_client.post(url, json={"login": "nobody"}, headers=aziza).status_code == (
        404
    )
    db_client.post(url, json={"login": "ramazon"}, headers=aziza)
    assert db_client.post(
        url, json={"login": "ramazon"}, headers=aziza
    ).status_code == (409)


def test_owner_removes_member(db_client: TestClient, aziza, ramazon, group_id):
    url = f"/api/groups/{group_id}/members"
    db_client.post(url, json={"login": "ramazon"}, headers=aziza)
    ramazon_id = db_client.get("/api/auth/me", headers=ramazon).json()["id"]
    owner_id = db_client.get("/api/auth/me", headers=aziza).json()["id"]

    assert db_client.delete(f"{url}/{owner_id}", headers=aziza).status_code == 409
    assert db_client.delete(f"{url}/{ramazon_id}", headers=aziza).status_code == 204
    assert db_client.delete(f"{url}/{ramazon_id}", headers=aziza).status_code == 404
    assert members(db_client, group_id, aziza) == ["aziza"]


def test_member_cannot_add_or_remove(db_client: TestClient, aziza, ramazon, group_id):
    url = f"/api/groups/{group_id}/members"
    auth_headers(db_client, "ali")
    db_client.post(url, json={"login": "ramazon"}, headers=aziza)
    ramazon_id = db_client.get("/api/auth/me", headers=ramazon).json()["id"]

    assert db_client.post(url, json={"login": "ali"}, headers=ramazon).status_code == (
        403
    )
    assert db_client.delete(f"{url}/{ramazon_id}", headers=ramazon).status_code == 403
    assert members(db_client, group_id, aziza) == ["aziza", "ramazon"]


def test_delete_group(db_client: TestClient, aziza, ramazon, group_id) -> None:
    db_client.post(
        f"/api/groups/{group_id}/members", json={"login": "ramazon"}, headers=aziza
    )

    assert db_client.delete(f"/api/groups/{group_id}", headers=ramazon).status_code == (
        403
    )
    assert db_client.delete(f"/api/groups/{group_id}", headers=aziza).status_code == 204
    assert db_client.get(f"/api/groups/{group_id}", headers=aziza).status_code == 404
    assert db_client.get("/api/groups", headers=ramazon).json() == []
