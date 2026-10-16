"""A zero-question run is a failure, while empty authoring remains valid."""

from unittest.mock import Mock

import pytest
import yaml
from typer.testing import CliRunner

from longprobe import LongProbe
from longprobe.cli.main import app
from longprobe.core.golden import GoldenQuestion, GoldenSet
from longprobe.core.scorer import RecallScorer


def test_direct_empty_scorer_never_calls_retriever():
    retrieve = Mock()
    with pytest.raises(ValueError, match="No questions"):
        RecallScorer().score_all(GoldenSet("empty", "1", []), retrieve)
    retrieve.assert_not_called()


def test_failed_rerun_invalidates_previous_report(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = Mock()
    adapter.retrieve.return_value = [{"id": "c1", "text": "evidence"}]
    probe = LongProbe(adapter, golden_set=GoldenSet("suite", "1", [GoldenQuestion("q1", "Question?", ["c1"])]))
    assert probe.run().overall_recall == 1
    probe.golden_set.questions.clear()
    with pytest.raises(ValueError, match="No questions"):
        probe.run()
    with pytest.raises(RuntimeError, match="No report"):
        probe.save_baseline()
    assert probe.baseline_store.load() is None


@pytest.mark.parametrize("args,selection", [(args, selection) for args in [["check"], ["baseline", "save"], ["diff"], ["explain", "q1"]] for selection in ["empty", "draft", "tag"] if not (args[0] == "explain" and selection == "tag")])
def test_empty_cli_selection_fails_without_retrieval(tmp_path, monkeypatch, args, selection):
    monkeypatch.chdir(tmp_path)
    questions = [] if selection == "empty" else [GoldenQuestion("q1", "Q?", ["c1"], status="draft" if selection == "draft" else "approved")]
    GoldenSet("test", "1", questions).to_yaml("goldens.yaml")
    (tmp_path / "longprobe.yaml").write_text(yaml.safe_dump({"retriever": {"type": "http", "http": {"url": "http://localhost/retrieve"}}}))
    factory = Mock()
    monkeypatch.setattr("longprobe.cli.main._create_adapter_from_config", factory)
    if selection == "tag":
        args = [*args, "--tag", "missing"]
    result = CliRunner().invoke(app, args)
    assert result.exit_code != 0, result.output
    assert "questions" in result.output.lower()
    factory.assert_not_called()


def test_draft_only_python_suite_is_not_evaluated_by_default(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    adapter = Mock()
    adapter.retrieve.return_value = [{"id": "c1"}]
    suite = GoldenSet("test", "1", [GoldenQuestion("q1", "Q?", ["c1"], status="draft")])
    with pytest.raises(ValueError):
        LongProbe(adapter, golden_set=suite).run()
    adapter.retrieve.assert_not_called()
    assert LongProbe(adapter, golden_set=suite, include_drafts=True).run().pass_rate == 1
