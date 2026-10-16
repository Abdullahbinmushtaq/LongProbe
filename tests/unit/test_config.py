"""Strict configuration must fail before using a service or exposing secrets."""

from dataclasses import replace
from unittest.mock import Mock

import pytest
from typer.testing import CliRunner

from longprobe import LongProbe
from longprobe.cli.main import app
from longprobe.config import ConfigurationError, ProbeConfig
from longprobe.core.golden import GoldenQuestion, GoldenSet


@pytest.mark.parametrize("section,value", [
    ("scoring", []), ("retriever", None), ("baseline", "wrong"),
    ("generator", 1), ("embedder", False),
])
def test_sections_must_be_mappings(section, value):
    with pytest.raises(ConfigurationError, match=section):
        ProbeConfig.from_dict({section: value})


@pytest.mark.parametrize("section,key,value", [
    ("scoring", "recall_threshold", float("nan")),
    ("scoring", "recall_threshold", float("inf")),
    ("scoring", "recall_threshold", 1.1),
    ("scoring", "recall_threshold", True),
    ("scoring", "fail_on_regression", "sometimes"),
    ("scoring", "fail_on_regression", []),
    ("retriever", "port", 65536), ("retriever", "port", 0),
    ("retriever", "port", 1.2), ("retriever", "port", True),
    ("embedder", "dimensions", -1), ("embedder", "batch_size", 0),
    ("generator", "num_questions", None), ("generator", "max_tokens", -1),
])
def test_invalid_scalar_values_are_not_defaulted(section, key, value):
    with pytest.raises(ConfigurationError, match=f"{section}.{key}"):
        ProbeConfig.from_dict({section: {key: value}})


def test_documented_strings_and_extra_settings_are_preserved():
    cfg = ProbeConfig.from_dict({"scoring": {"fail_on_regression": "NO", "recall_threshold": "0.9"}, "retriever": {"port": "6333", "custom": 5, "extra": {"a": 1}}})
    assert cfg.scoring.recall_threshold == 0.9
    assert cfg.scoring.fail_on_regression is False
    assert cfg.retriever.extra == {"a": 1, "custom": 5}


@pytest.mark.parametrize("data", [{"retriever": {"http": []}}, {"retriever": {"http": {"headers": []}}}, {"retriever": {"extra": None}}])
def test_nested_mappings_are_validated(data):
    with pytest.raises(ConfigurationError, match="retriever"):
        ProbeConfig.from_dict(data)


def test_credentials_are_operation_specific(monkeypatch):
    monkeypatch.delenv("MISSING_LONGPROBE_TOKEN", raising=False)
    cfg = ProbeConfig.from_dict({"retriever": {"type": "http", "http": {"url": "http://localhost/retrieve"}}, "generator": {"api_key": "${MISSING_LONGPROBE_TOKEN}"}})
    cfg.validate_for("evaluate")
    with pytest.raises(ConfigurationError, match="MISSING_LONGPROBE_TOKEN"):
        cfg.validate_for("generate")


def test_active_header_variable_is_required(monkeypatch):
    monkeypatch.delenv("MISSING_LONGPROBE_TOKEN", raising=False)
    cfg = ProbeConfig.from_dict({"retriever": {"type": "http", "http": {"url": "http://localhost/retrieve", "headers": {"Authorization": "Bearer ${MISSING_LONGPROBE_TOKEN}"}}}})
    with pytest.raises(ConfigurationError, match="MISSING_LONGPROBE_TOKEN"):
        cfg.validate_for("evaluate")
    monkeypatch.setenv("MISSING_LONGPROBE_TOKEN", "test-token")
    cfg.validate_for("evaluate")
    assert cfg.retriever.http.headers["Authorization"] == "Bearer test-token"


def test_provider_environment_auth_and_local_services(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-token")
    ProbeConfig.defaults().validate_for("generate")
    cfg = ProbeConfig.defaults()
    cfg.generator = replace(cfg.generator, provider="ollama")
    monkeypatch.delenv("OPENAI_API_KEY")
    cfg.validate_for("generate")
    cfg.retriever = replace(cfg.retriever, type="qdrant", collection="docs", host="localhost")
    cfg.validate_for("evaluate")


def test_typed_objects_cannot_bypass_numeric_validation():
    cfg = ProbeConfig.defaults()
    cfg.scoring.recall_threshold = "not-a-score"
    with pytest.raises(ConfigurationError, match=r"scoring\.recall_threshold"):
        cfg.validate_for("evaluate", owns_retriever=False)


def test_python_defaults_and_explicit_missing_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    gs = GoldenSet("test", "1", [GoldenQuestion("q1", "Question?", ["c1"])])
    probe = LongProbe(Mock(), golden_set=gs)
    assert probe.config.scoring.recall_threshold == 0.8
    with pytest.raises(FileNotFoundError):
        LongProbe(Mock(), golden_set=gs, config_path="missing.yaml")


@pytest.mark.parametrize("content", ["generator:\n  api_key: [SECRET_SENTINEL", "scoring:\n  recall_threshold: SECRET_SENTINEL", "[]"])
def test_cli_config_errors_never_leak_values(tmp_path, content):
    config = tmp_path / "config.yaml"
    config.write_text(content)
    result = CliRunner().invoke(app, ["diff", "--config", str(config)])
    assert result.exit_code != 0
    assert "SECRET_SENTINEL" not in result.output
    assert not (tmp_path / ".longprobe").exists()


def test_missing_cli_config_fails_with_recovery(tmp_path):
    result = CliRunner().invoke(app, ["diff", "--config", str(tmp_path / "missing.yaml")])
    assert result.exit_code != 0
    assert "init" in result.output
