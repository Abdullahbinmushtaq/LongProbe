"""A complete reliability workflow against a controlled local HTTP retriever."""

import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock

import pytest
import yaml
from typer.testing import CliRunner

from longprobe.cli.main import app
from longprobe.core.baseline import BaselineStore
from longprobe.core.golden import GoldenSet

pytestmark = pytest.mark.integration


@pytest.fixture
def retrieval_service():
    state = {"calls": 0, "results": [{"chunk_id": "policy-1", "content": "Refunds are allowed within 30 days.", "similarity": 0.9}]}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            assert payload["query"]
            state["calls"] += 1
            body = json.dumps({"data": {"chunks": state["results"]}}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/retrieve", state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_init_capture_review_check_baseline_and_failure_paths(tmp_path, monkeypatch, retrieval_service):
    monkeypatch.chdir(tmp_path)
    url, state = retrieval_service
    runner = CliRunner()

    def invoke(args, **kwargs):
        result = runner.invoke(app, args, **kwargs)
        assert result.exit_code == 0, result.output
        return result

    invoke(["init"])
    config = {
        "retriever": {"type": "http", "http": {"url": url, "response_mapping": {"results_path": "data.chunks", "id_field": "chunk_id", "text_field": "content", "score_field": "similarity"}}},
        "baseline": {"db_path": str(tmp_path / "baselines.db")},
        "generator": {"provider": "ollama", "model": "fixture"},
    }
    (tmp_path / "longprobe.yaml").write_text(yaml.safe_dump(config))
    GoldenSet("fixture-suite", "1", []).to_yaml("goldens.yaml")
    invoke(["capture", "--question", "What is the refund policy?", "--auto"])
    assert GoldenSet.from_yaml("goldens.yaml").questions[0].status == "draft"
    assert runner.invoke(app, ["check"]).exit_code != 0
    invoke(["edit"], input="a\ns\n")
    result = invoke(["check", "--output", "json"])
    assert json.loads(result.output)["overall_recall"] == 1.0
    invoke(["baseline", "save", "--label", "latest"])
    store = BaselineStore(str(tmp_path / "baselines.db"))
    baseline = store.load()
    assert baseline is not None and len(baseline.results) == 1
    invoke(["diff", "--baseline", "latest"])

    calls = state["calls"]
    assert runner.invoke(app, ["check", "--tag", "missing"]).exit_code != 0
    assert state["calls"] == calls
    assert store.load() == baseline

    state["results"] = []
    regression = runner.invoke(app, ["check"])
    assert regression.exit_code == 1
    assert store.load() == baseline

    target = tmp_path / "goldens.yaml"
    target.write_bytes(b"questions: [broken")
    (tmp_path / "document.txt").write_text("Policy text")
    generator = Mock()
    monkeypatch.setattr("longprobe.cli.main.QuestionGenerator", generator)
    result = runner.invoke(app, ["generate", "document.txt", "--auto-capture"])
    assert result.exit_code != 0
    generator.assert_not_called()
    assert state["calls"] == calls + 1
    assert target.read_bytes() == b"questions: [broken"
