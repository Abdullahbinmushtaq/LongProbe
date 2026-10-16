"""Verify v0.1.3 artifacts using a base-only wheel installation outside the checkout.

Run with the clean wheel environment's Python and -I. Starts a local HTTP fixture.
"""

import hashlib
import importlib.metadata as metadata
import importlib.util
import json
import os
import socket
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

import yaml

repo = Path(__file__).resolve().parents[1]
cli = str(Path(sys.executable).parent / 'longprobe')
wheel = repo / 'dist/longprobe-0.1.3-py3-none-any.whl'
sdist = repo / 'dist/longprobe-0.1.3.tar.gz'
with tempfile.TemporaryDirectory() as tmp:
    os.chdir(tmp)
    connect = socket.socket.connect
    def denied(*args, **kwargs):
        raise AssertionError('startup network access')
    socket.socket.connect = denied
    from typer.testing import CliRunner

    import longprobe
    from longprobe.cli.main import app
    result = CliRunner().invoke(app, ['--help'])
    assert result.exit_code == 0, result.output
    assert not list(Path(tmp).iterdir())
    assert metadata.version('longprobe') == longprobe.__version__ == '0.1.3'
    assert not str(longprobe.__file__).startswith(str(repo))
    for module in ['chromadb', 'pinecone', 'qdrant_client', 'langchain_core', 'llama_index', 'litellm', 'pytest']:
        assert importlib.util.find_spec(module) is None, module
    socket.socket.connect = connect

    process = subprocess.Popen([sys.executable, '-u', str(repo / 'examples/http_retriever.py'), '--port', '0'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        line = process.stdout.readline().strip()
        assert line.startswith('Development retriever:'), line
        endpoint = line.split(' ', 2)[-1]
        Path('longprobe.yaml').write_text(yaml.safe_dump({'retriever': {'type': 'http', 'http': {'url': endpoint, 'response_mapping': {'results_path': 'data.chunks', 'id_field': 'chunk_id', 'text_field': 'content', 'score_field': 'similarity'}}}, 'baseline': {'db_path': '.longprobe/baselines.db'}}))
        Path('goldens.yaml').write_text(yaml.safe_dump({'name': 'artifact-smoke', 'version': '1', 'questions': [{'id': 'refund', 'question': 'What is the refund policy?', 'required_chunks': ['Refunds are allowed within 30 days.'], 'match_mode': 'text'}]}))
        for args in [['check'], ['baseline','save','--label','latest'], ['diff','--baseline','latest']]:
            run = subprocess.run([cli, *args], capture_output=True, text=True)
            assert run.returncode == 0, run.stdout + run.stderr
        run = subprocess.run([cli, 'check', '--tag', 'missing'], capture_output=True, text=True)
        assert run.returncode != 0
    finally:
        process.terminate()
        process.communicate(timeout=10)

with tarfile.open(sdist) as archive:
    info = archive.extractfile('longprobe-0.1.3/PKG-INFO').read().decode()
    assert 'Version: 0.1.3' in info
record = {'python': sys.version.split()[0], 'runtime_version': longprobe.__version__, 'import_path': longprobe.__file__, 'base_only': True, 'startup_no_network_or_project_writes': True, 'installed_cli_http_workflow': 'passed', 'sdist_metadata': '0.1.3', 'artifacts': {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in [wheel, sdist]}}
print(json.dumps(record, indent=2))
