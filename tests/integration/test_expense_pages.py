"""HTML pages: guest mode, group expenses, settlements and notifications."""

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_pages import create_group, other_client, register


@pytest.fixture
def aziza(db_client: TestClient) -> TestClient:
    register(db_client, "aziza")
    return db_client


def user_id(client: TestClient) -> int:
    from app.web.pages import COOKIE_NAME

    token = client.cookies.get(COOKIE_NAME)
    return client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    ).json()["id"]


def add_member(client: TestClient, group_id: int, login: str) -> None:
    response = client.post(f"/groups/{group_id}/members", data={"login": login})
    assert response.status_code == 200


# --- guest mode -------------------------------------------------------------------


def test_guest_sees_not_saved_banner(db_client: TestClient) -> None:
    html = db_client.get("/").text

    assert "Mehmon rejimi" in html
    assert "ma'lumotlar saqlanmaydi" in html
    assert 'data-signed-in="0"' in html
    assert "carry.js" not in html


def test_signed_in_user_page_is_saved(aziza: TestClient) -> None:
    html = aziza.get("/").text

    assert "Mehmon rejimi" not in html
    assert 'data-signed-in="1"' in html
    assert 'id="saveStatus"' in html


def test_carry_script_on_signed_in_pages(aziza: TestClient) -> None:
    assert "carry.js" in aziza.get("/groups").text
    assert aziza.get("/static/carry.js").status_code == 200


# --- expenses on the group page -------------------------------------------------------


def test_add_expense_from_form(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me, other = user_id(aziza), user_id(ramazon)

    response = aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Mehmonxona",
            "amount": "400000",
            "paid_by": str(me),
            "split_type": "equal",
            "category": "accommodation",
            "expense_date": "2026-11-10",
            "participants": [str(me), str(other)],
        },
    )

    assert response.status_code == 200
    assert "Xarajat saqlandi" in response.text
    assert "Mehmonxona" in response.text
    # the plan shows the debt and offers "To'landi" to the parties
    page = ramazon.get(f"/groups/{group_id}").text
    assert "ramazon" in page
    assert "To&#39;landi" in page or "To'landi" in page
    assert "200 000" in page


def test_form_errors_keep_values(aziza: TestClient) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)

    response = aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Taksi",
            "amount": "1000",
            "paid_by": str(me),
            "split_type": "exact",
            "participants": [str(me)],
            f"value_{me}": "999",
        },
    )

    assert response.status_code == 400
    assert "Aniq summalar yig&#39;indisi" in response.text
    assert 'value="Taksi"' in response.text
    assert 'value="999"' in response.text


@pytest.mark.parametrize(
    ("data", "message"),
    [
        ({"amount": "abc"}, "musbat butun son"),
        ({"amount": "0"}, "musbat butun son"),
        ({"paid_by": ""}, "Kim to"),
        ({"expense_date": "11/10/2026"}, "Sana"),
        ({"split_type": "shares", "value": ""}, "qiymat kiriting"),
        ({"participants": []}, "Kamida bitta"),
    ],
)
def test_form_validation(aziza: TestClient, data, message) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)
    form = {
        "description": "Taksi",
        "amount": "1000",
        "paid_by": str(me),
        "split_type": "equal",
        "participants": [str(me)],
        f"value_{me}": data.pop("value", ""),
    }
    form.update(data)

    response = aziza.post(f"/groups/{group_id}/expenses", data=form)

    assert response.status_code == 400
    assert message in response.text.replace("&#39;", "'")


def test_delete_expense_from_page(aziza: TestClient, db_client) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)
    aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Non",
            "amount": "5000",
            "paid_by": str(me),
            "participants": [str(me)],
        },
    )
    expense_id = aziza.get(
        f"/api/groups/{group_id}/expenses",
        headers={"Authorization": f"Bearer {aziza.cookies.get('spliteasy_token')}"},
    ).json()["items"][0]["id"]

    stranger = other_client(db_client, "begona")
    response = stranger.post(f"/groups/{group_id}/expenses/{expense_id}/delete")
    assert response.status_code == 403  # not a member: error page

    response = aziza.post(f"/groups/{group_id}/expenses/{expense_id}/delete")
    assert "Xarajat o&#39;chirildi" in response.text
    response = aziza.post(f"/groups/{group_id}/expenses/{expense_id}/delete")
    assert "Xarajat topilmadi" in response.text


def test_member_cannot_delete_others_expense(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me = user_id(aziza)
    aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Non",
            "amount": "5000",
            "paid_by": str(me),
            "participants": [str(me)],
        },
    )
    page = ramazon.get(f"/groups/{group_id}").text
    assert '/delete"' not in page.split('id="expenses"')[1].split("Hisobotlar")[0]

    expense_id = 1
    response = ramazon.post(f"/groups/{group_id}/expenses/{expense_id}/delete")
    assert "faqat uni qo&#39;shgan" in response.text


def test_settle_from_page(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me, other = user_id(aziza), user_id(ramazon)
    aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Ovqat",
            "amount": "100000",
            "paid_by": str(me),
            "participants": [str(me), str(other)],
        },
    )

    response = ramazon.post(
        f"/groups/{group_id}/settlements",
        data={"from_user_id": other, "to_user_id": me, "amount": 50000},
    )

    assert "To&#39;lov saqlandi" in response.text
    assert "Hamma hisob teng" in response.text
    bad = ramazon.post(
        f"/groups/{group_id}/settlements",
        data={"from_user_id": other, "to_user_id": other, "amount": 5},
    )
    assert "To&#39;lov saqlanmadi" in bad.text
    # a second click on the same "To'landi" is refused: nothing is owed now
    again = ramazon.post(
        f"/groups/{group_id}/settlements",
        data={"from_user_id": other, "to_user_id": me, "amount": 50000},
    )
    assert "To&#39;lov saqlanmadi" in again.text


def test_settlement_by_outsider_party_is_forbidden(
    aziza: TestClient, db_client
) -> None:
    ramazon = other_client(db_client, "ramazon")
    bobur = other_client(db_client, "bobur")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    add_member(aziza, group_id, "bobur")

    response = bobur.post(
        f"/groups/{group_id}/settlements",
        data={
            "from_user_id": user_id(ramazon),
            "to_user_id": user_id(aziza),
            "amount": 5,
        },
    )
    assert "faqat uning ishtirokchisi" in response.text


def test_expense_list_is_paginated(aziza: TestClient) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)
    for i in range(21):
        aziza.post(
            f"/groups/{group_id}/expenses",
            data={
                "description": f"X{i}",
                "amount": "100",
                "paid_by": str(me),
                "participants": [str(me)],
                "expense_date": "2026-11-01",
            },
        )

    first = aziza.get(f"/groups/{group_id}").text
    second = aziza.get(f"/groups/{group_id}?page=2").text
    assert "1 / 2" in first and "21 ta xarajat" in first
    assert ">X0<" in second and ">X0<" not in first


# --- notifications ---------------------------------------------------------------------


def test_notifications_page_and_badge(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me, other = user_id(aziza), user_id(ramazon)
    aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Kino",
            "amount": "80000",
            "paid_by": str(me),
            "participants": [str(me), str(other)],
        },
    )

    groups_page = ramazon.get("/groups").text
    assert 'class="bell-count">1<' in groups_page
    page = ramazon.get("/notifications").text
    assert "Kino" in page and "1 ta o'qilmagan" in page

    response = ramazon.post("/notifications/read-all")
    assert "Barcha bildirishnomalar o&#39;qildi" in response.text
    assert "bell-count" not in ramazon.get("/groups").text


def test_notifications_page_requires_login(db_client: TestClient) -> None:
    response = db_client.get("/notifications", follow_redirects=False)
    assert response.status_code == 303


# --- edit (FR-12), filter (FR-14), export (FR-24), FR-7 on the pages ---------------


def _one_expense(client: TestClient, group_id: int, me: int, **extra: str) -> int:
    client.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Non",
            "amount": "6000",
            "paid_by": str(me),
            "participants": [str(me)],
            **extra,
        },
    )
    token = client.cookies.get("spliteasy_token")
    return client.get(
        f"/api/groups/{group_id}/expenses",
        headers={"Authorization": f"Bearer {token}"},
    ).json()["items"][0]["id"]


def test_edit_expense_page(aziza: TestClient) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)
    expense_id = _one_expense(aziza, group_id, me)

    form = aziza.get(f"/groups/{group_id}/expenses/{expense_id}/edit")
    assert form.status_code == 200
    assert 'value="Non"' in form.text and 'value="6000"' in form.text

    saved = aziza.post(
        f"/groups/{group_id}/expenses/{expense_id}/edit",
        data={
            "description": "Non va choy",
            "amount": "9000",
            "paid_by": str(me),
            "split_type": "equal",
            "participants": [str(me)],
        },
    )
    assert "Xarajat yangilandi" in saved.text
    assert "Non va choy" in saved.text

    bad = aziza.post(
        f"/groups/{group_id}/expenses/{expense_id}/edit",
        data={"description": "X", "amount": "0", "paid_by": str(me)},
    )
    assert bad.status_code == 400
    missing = aziza.get(f"/groups/{group_id}/expenses/999/edit")
    assert "Xarajat topilmadi" in missing.text


def test_member_cannot_edit_others_expense(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me = user_id(aziza)
    expense_id = _one_expense(aziza, group_id, me)

    response = ramazon.post(
        f"/groups/{group_id}/expenses/{expense_id}/edit",
        data={
            "description": "X",
            "amount": "1",
            "paid_by": str(me),
            "participants": [str(me)],
        },
    )
    assert "faqat uni qo&#39;shgan" in response.text


def test_category_filter_on_the_page(aziza: TestClient) -> None:
    group_id = create_group(aziza)
    me = user_id(aziza)
    _one_expense(aziza, group_id, me, category="food", description="Palov")
    _one_expense(aziza, group_id, me, category="transport", description="Taksi")

    page = aziza.get(f"/groups/{group_id}?category=transport").text
    unknown = aziza.get(f"/groups/{group_id}?category=cars")

    expenses_part = page.split('id="expenses"')[1].split("Hisobotlar")[0]
    assert ">Taksi<" in expenses_part and ">Palov<" not in expenses_part
    assert unknown.status_code == 200  # falls back to all categories


def test_export_from_the_page(aziza: TestClient) -> None:
    group_id = create_group(aziza)
    _one_expense(aziza, group_id, user_id(aziza))

    csv_file = aziza.get(f"/groups/{group_id}/export?format=csv")
    fallback = aziza.get(f"/groups/{group_id}/export?format=xml")

    assert csv_file.headers["content-type"].startswith("text/csv")
    assert "Non" in csv_file.text
    assert fallback.headers["content-type"].startswith("text/csv")


def test_remove_member_with_debt_shows_message(aziza: TestClient, db_client) -> None:
    ramazon = other_client(db_client, "ramazon")
    group_id = create_group(aziza)
    add_member(aziza, group_id, "ramazon")
    me, other = user_id(aziza), user_id(ramazon)
    aziza.post(
        f"/groups/{group_id}/expenses",
        data={
            "description": "Ovqat",
            "amount": "1000",
            "paid_by": str(me),
            "participants": [str(me), str(other)],
        },
    )

    response = aziza.post(f"/groups/{group_id}/members/{other}/remove")

    assert "balansi 0 emas" in response.text
