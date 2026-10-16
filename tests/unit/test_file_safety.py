"""File failures must preserve trusted golden data byte-for-byte."""

import errno
import os
from unittest.mock import Mock

import pytest

from longprobe._files import atomic_write_text
from longprobe.core.golden import GoldenQuestion, GoldenSet


@pytest.mark.parametrize("stage", ["replace", "flush"])
@pytest.mark.parametrize("existing", [True, False])
def test_write_failure_preserves_original(tmp_path, monkeypatch, stage, existing):
    target = tmp_path / "goldens.yaml"
    if existing:
        target.write_bytes(b"trusted original\n")
    hook = "os.replace" if stage == "replace" else "os.fsync"
    monkeypatch.setattr(f"longprobe._files.{hook}", Mock(side_effect=OSError(errno.EIO, "injected")))
    with pytest.raises(OSError):
        atomic_write_text(target, "new content", overwrite=True)
    assert target.read_bytes() == b"trusted original\n" if existing else not target.exists()
    assert not list(tmp_path.glob(".*.tmp"))


def test_safe_unicode_and_nested_writes(tmp_path):
    target = tmp_path / "nested" / "goldens.yaml"
    suite = GoldenSet("Unicode", "1", [GoldenQuestion("q1", "سوال؟", ["جواب"])])
    suite.to_yaml(str(target))
    assert GoldenSet.from_yaml(str(target)) == suite
    target.chmod(0o600)
    suite.to_yaml(str(target))
    assert target.stat().st_mode & 0o777 == 0o600


def test_invalid_candidate_and_serialization_preserve_file(tmp_path, monkeypatch):
    target = tmp_path / "goldens.yaml"
    target.write_bytes(b"original")
    bad = GoldenSet("test", "1", [GoldenQuestion("q", "Q?", [])])
    with pytest.raises(ValueError):
        bad.to_yaml(str(target))
    good = GoldenSet("test", "1", [])
    monkeypatch.setattr("longprobe.core.golden.yaml.safe_dump", Mock(side_effect=ValueError("injected")))
    with pytest.raises(ValueError):
        good.to_yaml(str(target))
    assert target.read_bytes() == b"original"


def test_read_only_and_symlink_targets_are_preserved(tmp_path):
    original = tmp_path / "original.yaml"
    original.write_bytes(b"original")
    original.chmod(0o400)
    with pytest.raises(PermissionError):
        atomic_write_text(original, "changed", overwrite=True)
    link = tmp_path / "link.yaml"
    link.symlink_to(original)
    with pytest.raises(OSError):
        atomic_write_text(link, "changed", overwrite=True)
    assert original.read_bytes() == b"original"


def test_replacement_requires_authorization(tmp_path):
    target = tmp_path / "export.yaml"
    target.write_bytes(b"original")
    with pytest.raises(FileExistsError):
        atomic_write_text(target, "new", overwrite=False)
    assert target.read_bytes() == b"original"


def test_empty_authoring_set_can_be_saved(tmp_path):
    target = tmp_path / "goldens.yaml"
    suite = GoldenSet("test", "1", [])
    suite.to_yaml(str(target))
    assert GoldenSet.from_yaml(str(target)) == suite


def test_unwritable_destination_is_not_bypassed(tmp_path, monkeypatch):
    target = tmp_path / "goldens.yaml"
    target.write_text("original")
    real_open = os.open

    def deny(path, flags, *args, **kwargs):
        if path == target:
            raise PermissionError(errno.EACCES, "injected", str(path))
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr("longprobe._files.os.open", deny)
    with pytest.raises(PermissionError):
        atomic_write_text(target, "new", overwrite=True)
    assert target.read_text() == "original"
