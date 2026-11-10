from pathlib import Path

from app.infrastructure.config import load_env_file


def test_env_file_values_are_loaded(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "# comment\n"
        "\n"
        "SPLITEASY_SECRET_KEY=abc=123\n"
        'SPLITEASY_DATABASE_URL="sqlite:///./other.db"\n'
        "not a variable line\n",
        encoding="utf-8",
    )
    environ: dict[str, str] = {}

    load_env_file(env_file, environ)

    assert environ == {
        "SPLITEASY_SECRET_KEY": "abc=123",
        "SPLITEASY_DATABASE_URL": "sqlite:///./other.db",
    }


def test_shell_variables_win_over_env_file(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("SPLITEASY_SECRET_KEY=from-file\n", encoding="utf-8")
    environ = {"SPLITEASY_SECRET_KEY": "from-shell"}

    load_env_file(env_file, environ)

    assert environ["SPLITEASY_SECRET_KEY"] == "from-shell"


def test_missing_env_file_is_ignored(tmp_path: Path) -> None:
    environ: dict[str, str] = {}

    load_env_file(tmp_path / "missing.env", environ)

    assert environ == {}
