from pathlib import Path

from sigexport import utils


def test_root_is_refused() -> None:
    assert utils.is_dangerous_overwrite_target(Path("/")) == "the filesystem root"


def test_home_is_refused() -> None:
    assert utils.is_dangerous_overwrite_target(Path.home()) == "your home directory"


def test_cwd_is_refused() -> None:
    assert (
        utils.is_dangerous_overwrite_target(Path.cwd())
        == "the current working directory"
    )


def test_parent_of_cwd_is_refused() -> None:
    reason = utils.is_dangerous_overwrite_target(Path.cwd().parent)
    assert reason == "a parent of the current working directory"


def test_var_itself_is_refused() -> None:
    assert utils.is_dangerous_overwrite_target(Path("/var")) == "a system directory (/var)"


def test_var_subdir_is_allowed() -> None:
    """We only block /var itself, not sensible sub-paths like /var/backups."""
    assert utils.is_dangerous_overwrite_target(Path("/var/backups/signal")) is None


def test_normal_target_is_allowed(tmp_path: Path) -> None:
    assert utils.is_dangerous_overwrite_target(tmp_path / "export") is None


def test_empty_dir_looks_like_export(tmp_path: Path) -> None:
    assert utils.looks_like_export_dir(tmp_path) is True


def test_dir_with_stylesheet_looks_like_export(tmp_path: Path) -> None:
    (tmp_path / "style.css").write_text("body {}")
    assert utils.looks_like_export_dir(tmp_path) is True


def test_dir_with_chat_folder_looks_like_export(tmp_path: Path) -> None:
    chat = tmp_path / "Alice"
    chat.mkdir()
    (chat / "chat.md").write_text("hi")
    assert utils.looks_like_export_dir(tmp_path) is True


def test_json_only_export_is_recognised(tmp_path: Path) -> None:
    """A --no-html export has no style.css, but data.json still marks it."""
    chat = tmp_path / "Alice"
    chat.mkdir()
    (chat / "data.json").write_text("{}")
    assert not (tmp_path / "style.css").exists()
    assert utils.looks_like_export_dir(tmp_path) is True


def test_unrelated_dir_is_not_an_export(tmp_path: Path) -> None:
    (tmp_path / "taxes.pdf").write_text("important")
    (tmp_path / "photos").mkdir()
    assert utils.looks_like_export_dir(tmp_path) is False
