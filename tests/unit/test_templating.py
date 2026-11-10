import pytest

from app.web.templating import AVATAR_HUES, avatar_hue, initials


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Ali Valiyev", "AV"),
        ("aziza_anvarovna", "AA"),
        ("ramazon.s", "RS"),
        ("Ali", "AL"),
        ("", "?"),
    ],
)
def test_initials(name: str, expected: str) -> None:
    assert initials(name) == expected


def test_avatar_hue_is_stable_and_from_palette() -> None:
    # static/app.js uses the same hash: "Ali" must get the same colour there.
    assert avatar_hue("Ali") == avatar_hue("Ali")
    assert avatar_hue("Ali") in AVATAR_HUES
    assert len({avatar_hue(n) for n in ["Ali", "Vali", "Sardor", "Dilshod"]}) > 1
