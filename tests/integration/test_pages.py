"""HTML pages: cookie login, forms, access rules and safety checks."""

import pytest
from fastapi.testclient import TestClient

from app.web.pages import COOKIE_NAME, safe_next


def register(client: TestClient, username: str, password: str = "secret123"):
    return client.post(
        "/register",
        data={
            "username": username,
            "email": f"{username}@example.com",
            "password": password,
        },
    )


@pytest.fixture
def aziza(db_client: TestClient) -> TestClient:
    response = register(db_client, "aziza")
    assert response.status_code == 200, response.text  # followed redirect
    return db_client


def other_client(db_client: TestClient, username: str) -> TestClient:
    """A second browser with its own cookies, same app and database."""
    client = TestClient(db_client.app)
    register(client, username)
    return client


def create_group(client: TestClient, name: str = "Sayohat") -> int:
    response = client.post("/groups", data={"name": name, "currency": "UZS"})
    assert response.status_code == 200
    return int(str(response.url).rstrip("/").split("/")[-1].split("?")[0])


# --- authentication ----------------------------------------------------------


def test_register_logs_in_with_httponly_cookie(db_client: TestClient) -> None:
    response = register(db_client, "aziza")

    assert response.url.path == "/groups"
    assert "Xush kelibsiz" in response.text
    assert "aziza" in response.text
    set_cookie = response.history[0].headers["set-cookie"].lower()
    assert COOKIE_NAME in set_cookie
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie


def test_register_shows_validation_errors(db_client: TestClient) -> None:
    response = db_client.post(
        "/register", data={"username": "a b", "email": "bad", "password": "1"}
    )

    assert response.status_code == 400
    assert "Foydalanuvchi nomi 3–32 belgi" in response.text
    assert "Email manzili noto&#39;g&#39;ri" in response.text
    assert "Parol 8–128" in response.text
    assert 'value="a b"' in response.text  # the form keeps what was typed


def test_register_duplicate(aziza: TestClient, db_client: TestClient) -> None:
    db_client.cookies.clear()

    response = register(db_client, "aziza")

    assert response.status_code == 409
    assert "band" in response.text


def test_login_and_logout(aziza: TestClient) -> None:
    aziza.post("/logout")
    assert aziza.get("/groups").url.path == "/login"

    response = aziza.post("/login", data={"username": "aziza", "password": "secret123"})

    assert response.url.path == "/groups"
    assert "Umumiy holat" in response.text


def test_login_with_email(aziza: TestClient) -> None:
    aziza.post("/logout")

    response = aziza.post(
        "/login", data={"username": "aziza@example.com", "password": "secret123"}
    )

    assert response.url.path == "/groups"


def test_wrong_password(aziza: TestClient) -> None:
    aziza.post("/logout")

    response = aziza.post("/login", data={"username": "aziza", "password": "nope1234"})

    assert response.status_code == 400
    assert "Login yoki parol noto" in response.text
    assert COOKIE_NAME not in aziza.cookies


def test_logout_removes_cookie(aziza: TestClient) -> None:
    response = aziza.post("/logout")

    assert "Tizimdan chiqdingiz" in response.text
    assert COOKIE_NAME not in aziza.cookies


def test_pages_require_login_and_return_after(db_client: TestClient) -> None:
    response = db_client.get("/groups/5")

    assert response.url.path == "/login"
    assert "Davom etish uchun tizimga kiring" in response.text
    assert 'name="next" value="/groups/5"' in response.text


def test_invalid_cookie_is_cleared(db_client: TestClient) -> None:
    db_client.cookies.set(COOKIE_NAME, "garbage")

    response = db_client.get("/groups", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")
    assert f'{COOKIE_NAME}=""' in response.headers["set-cookie"]


def test_logged_in_user_skips_login_page(aziza: TestClient) -> None:
    assert aziza.get("/login").url.path == "/groups"
    assert aziza.get("/register").url.path == "/groups"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("/groups/3", "/groups/3"),
        ("https://evil.example", "/groups"),
        ("//evil.example", "/groups"),
        ("/\\evil.example", "/groups"),
        ("", "/groups"),
        (None, "/groups"),
    ],
)
def test_safe_next_blocks_open_redirect(value, expected) -> None:
    assert safe_next(value) == expected


def test_login_does_not_redirect_to_other_sites(aziza: TestClient) -> None:
    aziza.post("/logout")

    response = aziza.post(
        "/login",
        data={"username": "aziza", "password": "secret123", "next": "//evil.example"},
        follow_redirects=False,
    )

    assert response.headers["location"] == "/groups"


def test_unknown_flash_key_shows_nothing(aziza: TestClient) -> None:
    response = aziza.get("/groups?msg=<script>alert(1)</script>")

    assert "<script>alert(1)" not in response.text
    assert "alert-" not in response.text.split("<main")[1].split("Umumiy holat")[0]


# --- groups ------------------------------------------------------------------


def test_create_group_and_view(aziza: TestClient) -> None:
    group_id = create_group(aziza, "Samarqand")

    page = aziza.get(f"/groups/{group_id}")

    assert page.status_code == 200
    assert "Samarqand" in page.text
    assert (
        "Guruh yaratildi"
        in aziza.post("/groups", data={"name": "Ikkinchi", "currency": "USD"}).text
    )
    listing = aziza.get("/groups").text
    assert "Samarqand" in listing and "Ikkinchi" in listing
    assert "hali xarajat yo'q" in page.text


def test_create_group_validation(aziza: TestClient) -> None:
    response = aziza.post("/groups", data={"name": "   ", "currency": "UZS"})

    assert response.status_code == 400
    assert "Guruh nomi" in response.text


def test_owner_adds_and_removes_member(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)

    added = aziza.post(f"/groups/{group_id}/members", data={"login": "ramazon"})
    assert "A&#39;zo qo&#39;shildi" in added.text
    assert ramazon.get(f"/groups/{group_id}").status_code == 200

    ramazon_id = ramazon.get("/api/auth/me").status_code  # API needs Bearer
    assert ramazon_id == 401

    page = aziza.get(f"/groups/{group_id}").text
    remove_url = page.split(f'action="/groups/{group_id}/members/')[1].split('"')[0]
    removed = aziza.post(f"/groups/{group_id}/members/{remove_url}")
    assert "guruhdan chiqarildi" in removed.text
    assert ramazon.get(f"/groups/{group_id}").status_code == 403


def test_add_member_errors_are_flashed(aziza: TestClient) -> None:
    group_id = create_group(aziza)

    unknown = aziza.post(f"/groups/{group_id}/members", data={"login": "nobody"})
    assert "Bunday foydalanuvchi topilmadi" in unknown.text

    twice = aziza.post(f"/groups/{group_id}/members", data={"login": "aziza"})
    assert "allaqachon guruhda" in twice.text


def test_member_sees_no_owner_controls(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    aziza.post(f"/groups/{group_id}/members", data={"login": "ramazon"})

    page = ramazon.get(f"/groups/{group_id}").text

    assert "Guruhni o'chirish" not in page
    assert "chiqarish</button>" not in page
    forbidden = ramazon.post(f"/groups/{group_id}/members", data={"login": "aziza"})
    assert "faqat guruh egasi" in forbidden.text
    assert ramazon.post(f"/groups/{group_id}/delete").url.path == f"/groups/{group_id}"


def test_non_member_and_missing_group_pages(aziza: TestClient, db_client) -> None:
    stranger = other_client(db_client, "stranger")
    group_id = create_group(aziza)

    forbidden = stranger.get(f"/groups/{group_id}")
    missing = aziza.get("/groups/999")

    assert forbidden.status_code == 403
    assert "a&#39;zosi emassiz" in forbidden.text
    assert "stranger" in forbidden.text  # navbar still shows the user
    assert missing.status_code == 404


def test_owner_deletes_group(aziza: TestClient) -> None:
    group_id = create_group(aziza, "O'chadigan")

    response = aziza.post(f"/groups/{group_id}/delete")

    assert response.url.path == "/groups"
    assert "Guruh o&#39;chirildi" in response.text
    assert aziza.get(f"/groups/{group_id}").status_code == 404


def test_home_page_links_to_login(db_client: TestClient) -> None:
    assert 'href="/login"' in db_client.get("/").text
