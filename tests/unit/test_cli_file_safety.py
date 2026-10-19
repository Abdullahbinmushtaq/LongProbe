"""CLI preflight must prevent paid work and preserve trusted destinations."""

from unittest.mock import Mock

import pytest
import yaml
from typer.testing import CliRunner

from longprobe.cli.main import app
from longprobe.core.golden import GoldenQuestion, GoldenSet


@pytest.fixture
def project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "longprobe.yaml").write_text(yaml.safe_dump({"retriever": {"type": "http", "http": {"url": "http://localhost/retrieve"}}, "generator": {"provider": "ollama", "model": "test"}}))
    (tmp_path / "document.txt").write_text("A policy document")
    generator = Mock()
    generator.return_value.generate.return_value = ["What is the policy?"]
    retriever = Mock()
    retriever.return_value.retrieve.return_value = [{"id": "c1", "text": "The policy"}]
    monkeypatch.setattr("longprobe.cli.main.QuestionGenerator", generator)
    monkeypatch.setattr("longprobe.cli.main._create_adapter_from_config", retriever)
    return tmp_path, generator, retriever


@pytest.mark.parametrize("content", [b"questions: [broken", b"name: test\nversion: '1'\nquestions: [{}]", b"- not a golden set"])
def test_invalid_existing_goldens_fail_before_generation(project, content):
    root, generator, retriever = project
    target = root / "goldens.yaml"
    target.write_bytes(content)
    result = CliRunner().invoke(app, ["generate", "document.txt", "--auto-capture"])
    assert result.exit_code != 0
    assert target.read_bytes() == content
    generator.assert_not_called()
    retriever.assert_not_called()


def test_read_only_existing_goldens_fail_before_generation(project):
    root, generator, retriever = project
    target = root / "goldens.yaml"
    GoldenSet("test", "1", []).to_yaml(str(target))
    original = target.read_bytes()
    target.chmod(0o400)
    result = CliRunner().invoke(app, ["generate", "document.txt", "--auto-capture"])
    assert result.exit_code != 0
    assert target.read_bytes() == original
    generator.assert_not_called()
    retriever.assert_not_called()


def test_auto_capture_preserves_old_questions_and_adds_drafts(project):
    root, _, _ = project
    target = root / "goldens.yaml"
    old = GoldenQuestion("trusted", "Old question?", ["old evidence"], match_mode="text", tags=["critical"], metadata={"source": "manual"})
    GoldenSet("trusted-suite", "2", [old]).to_yaml(str(target))
    result = CliRunner().invoke(app, ["generate", "document.txt", "--auto-capture"])
    assert result.exit_code == 0, result.output
    suite = GoldenSet.from_yaml(str(target))
    assert suite.name == "trusted-suite" and suite.version == "2"
    assert suite.questions[0] == old
    assert suite.questions[1].status == "draft"


def test_zero_captures_preserve_original_bytes(project):
    root, _, retriever = project
    target = root / "goldens.yaml"
    GoldenSet("trusted", "1", []).to_yaml(str(target))
    original = target.read_bytes()
    retriever.return_value.retrieve.return_value = []
    result = CliRunner().invoke(app, ["generate", "document.txt", "--auto-capture"])
    assert result.exit_code == 0, result.output
    assert "unchanged" in result.output
    assert target.read_bytes() == original


@pytest.mark.parametrize("args", [["--overwrite"], ["--auto-capture", "--overwrite"], ["--auto-capture", "--output", "out.yaml"]])
def test_incompatible_flags_fail_before_paid_work(project, args):
    _, generator, retriever = project
    result = CliRunner().invoke(app, ["generate", "document.txt", *args])
    assert result.exit_code != 0
    generator.assert_not_called()
    retriever.assert_not_called()


def test_question_export_requires_explicit_overwrite(project):
    root, generator, _ = project
    target = root / "questions.yaml"
    target.write_bytes(b"trusted")
    result = CliRunner().invoke(app, ["generate", "document.txt", "--output", str(target)])
    assert result.exit_code != 0
    assert "--overwrite" in result.output
    generator.assert_not_called()
    assert target.read_bytes() == b"trusted"
    result = CliRunner().invoke(app, ["generate", "document.txt", "--output", str(target), "--overwrite"])
    assert result.exit_code == 0, result.output
    assert yaml.safe_load(target.read_text())["questions"] == ["What is the policy?"]


def test_init_preserves_existing_files_unless_forced(project):
    root, _, _ = project
    (root / "goldens.yaml").write_bytes(b"trusted golden")
    config = (root / "longprobe.yaml").read_bytes()
    result = CliRunner().invoke(app, ["init"])
    assert result.exit_code == 0
    assert (root / "goldens.yaml").read_bytes() == b"trusted golden"
    assert (root / "longprobe.yaml").read_bytes() == config
    result = CliRunner().invoke(app, ["init", "--force"])
    assert result.exit_code == 0, result.output
    assert GoldenSet.from_yaml("goldens.yaml").questions


def test_edit_failed_save_preserves_original(project, monkeypatch):
    root, _, _ = project
    GoldenSet("test", "1", []).to_yaml("goldens.yaml")
    original = (root / "goldens.yaml").read_bytes()
    monkeypatch.setattr("longprobe._files.os.replace", Mock(side_effect=OSError("injected")))
    result = CliRunner().invoke(app, ["edit"], input="s\n")
    assert result.exit_code != 0
    assert (root / "goldens.yaml").read_bytes() == original
    assert "Saved golden" not in result.output


def test_empty_authoring_set_can_be_captured(project):
    root, _, _ = project
    GoldenSet("test", "1", []).to_yaml("goldens.yaml")
    result = CliRunner().invoke(app, ["capture", "--question", "Q?", "--auto"])
    assert result.exit_code == 0, result.output
    assert GoldenSet.from_yaml(str(root / "goldens.yaml")).questions[0].status == "draft"
