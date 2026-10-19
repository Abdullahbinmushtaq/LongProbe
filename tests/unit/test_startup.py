"""Base-install startup must not use optional services or project data."""

import importlib.metadata
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

import longprobe
from longprobe.adapters import (
    ChromaAdapter,
    LangChainRetrieverAdapter,
    LlamaIndexRetrieverAdapter,
    PineconeAdapter,
    QdrantAdapter,
)


def test_installed_version_matches_runtime():
    assert longprobe.__version__ == importlib.metadata.version("longprobe")


def test_import_and_help_without_side_effects(tmp_path):
    code = '''
import socket
from pathlib import Path

def forbidden(*args, **kwargs):
    raise AssertionError("startup attempted a network or data write")

socket.socket.connect = forbidden
Path.write_text = forbidden
import longprobe
from longprobe import LongProbe
from typer.testing import CliRunner
from longprobe.cli.main import app
result = CliRunner().invoke(app, ["--help"])
assert result.exit_code == 0, result.output
'''
    result = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("adapter,module", [(PineconeAdapter("test"), "pinecone"), (QdrantAdapter("test"), "qdrant_client")])
def test_missing_optional_sdk_has_install_guidance(adapter, module, monkeypatch):
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ImportError, match=r"[Ii]nstall"):
        adapter.retrieve(query_embedding=[0.1, 0.2])


@pytest.mark.parametrize("adapter,module", [(ChromaAdapter("test"), "chromadb"), (LangChainRetrieverAdapter(Mock()), "langchain_core"), (LlamaIndexRetrieverAdapter(Mock()), "llama_index")])
def test_text_adapter_missing_sdk_has_install_guidance(adapter, module, monkeypatch):
    monkeypatch.setitem(sys.modules, module, None)
    with pytest.raises(ImportError, match=r"[Ii]nstall"):
        adapter.retrieve("test question")


def test_all_source_modules_parse():
    import ast

    for path in Path(longprobe.__file__).parent.rglob("*.py"):
        ast.parse(path.read_text(), filename=str(path))
