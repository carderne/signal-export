import json
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from sigexport import data, main, models


def make_source(tmp_path: Path) -> Path:
    source = tmp_path / "source"
    source.mkdir()
    (source / "config.json").write_text(json.dumps({}))
    return source


def contacts() -> models.Contacts:
    return {
        "c1": models.Contact(
            id="c1",
            serviceId="sid1",
            name="Alice",
            number="",
            profile_name="",
            is_group=False,
            members=None,
        )
    }


def run_main(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    convos: models.Convos,
) -> Path:
    """Run main() with the Signal DB layer stubbed out, returning the dest path."""
    monkeypatch.setattr(data, "get_signal_database", lambda *a, **k: None)
    monkeypatch.setattr(data, "fetch_data", lambda *a, **k: (convos, contacts(), None))

    dest = tmp_path / "output"
    app = typer.Typer()
    app.command()(main.main)
    CliRunner().invoke(
        app,
        [
            str(dest),
            "--source",
            str(make_source(tmp_path)),
            "--no-stickers",
            "--no-attachments",
        ],
    )
    return dest


def test_dest_not_created_when_no_chats_exported(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """No chats to export must leave the filesystem untouched, so the command
    can be rerun without manually deleting a half-made output folder."""
    dest = run_main(monkeypatch, tmp_path, {})
    assert not dest.exists()
