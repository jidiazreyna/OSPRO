import sys
import types
from pathlib import Path

# Ensure project root is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pytest

pytest.importorskip("fastapi")

# Stub external dependencies
sys.modules.setdefault("openai", types.ModuleType("openai"))
sys.modules.setdefault("docx2txt", types.ModuleType("docx2txt"))
pdfminer = types.ModuleType("pdfminer")
pdf_high = types.ModuleType("pdfminer.high_level")
pdf_high.extract_text = lambda *a, **k: ""
pdfminer.high_level = pdf_high
sys.modules["pdfminer"] = pdfminer
sys.modules["pdfminer.high_level"] = pdf_high
import api
import core
from fastapi.testclient import TestClient


def test_chat_endpoint_returns_openai_response(monkeypatch):
    class MockResponse:
        def model_dump(self):
            return {"choices": [{"message": {"content": "Hola"}}]}

    class MockClient:
        def __init__(self):
            completions = types.SimpleNamespace(create=lambda **kwargs: MockResponse())
            self.chat = types.SimpleNamespace(completions=completions)

    monkeypatch.setattr(core, "_get_openai_client", lambda: MockClient())

    client = TestClient(api.app)
    resp = client.post("/chat", json={"messages": [{"role": "user", "content": "Hola"}]})
    assert resp.status_code == 200
    assert resp.json() == {"choices": [{"message": {"content": "Hola"}}]}
