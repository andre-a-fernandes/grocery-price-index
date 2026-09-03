"""analyse_receipt error handling and prompt/request config, with the Gemini client mocked."""

import json

import pytest
from fastapi import HTTPException

import core.parser as parser
from core.parser import PROMPT, analyse_receipt


class _FakeResponse:
    def __init__(self, text):
        self.text = text


class _FakeModels:
    def __init__(self, response=None, error: Exception | None = None):
        self._response = response
        self._error = error
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


def _patch_client(monkeypatch, response=None, init_error=None, gen_error=None):
    models = _FakeModels(response=response, error=gen_error)

    def factory():
        if init_error is not None:
            raise init_error
        return type("FakeClient", (), {"models": models})()

    monkeypatch.setattr(parser, "Client", factory)
    return models


class TestAnalyseReceiptErrors:
    def test_client_init_failure_raises_502(self, monkeypatch):
        _patch_client(monkeypatch, init_error=RuntimeError("no API key"))
        with pytest.raises(HTTPException) as exc:
            analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        assert exc.value.status_code == 502
        assert "Failed to initialize Gemini client" in exc.value.detail

    def test_gemini_call_failure_raises_502(self, monkeypatch):
        _patch_client(monkeypatch, gen_error=RuntimeError("quota exceeded"))
        with pytest.raises(HTTPException) as exc:
            analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        assert exc.value.status_code == 502
        assert "Gemini request failed" in exc.value.detail

    def test_unparseable_json_raises_502(self, monkeypatch):
        _patch_client(monkeypatch, response=_FakeResponse("not json at all"))
        with pytest.raises(HTTPException) as exc:
            analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        assert exc.value.status_code == 502
        assert "unparseable" in exc.value.detail

    def test_empty_response_raises_502(self, monkeypatch):
        _patch_client(monkeypatch, response=_FakeResponse(""))
        with pytest.raises(HTTPException) as exc:
            analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        assert exc.value.status_code == 502

    def test_valid_json_is_returned_as_dict(self, monkeypatch):
        payload = {"store_name": "Jumbo", "items": []}
        _patch_client(monkeypatch, response=_FakeResponse(json.dumps(payload)))
        result = analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        assert result == payload


class TestPromptAndConfig:
    def test_prompt_formats_without_key_error(self):
        rendered = PROMPT.format(today="2026-03-09")
        assert "2026-03-09" in rendered

    def test_request_uses_configured_model_and_json_output(self, monkeypatch):
        payload = {"store_name": "Jumbo", "items": []}
        models = _patch_client(monkeypatch, response=_FakeResponse(json.dumps(payload)))
        analyse_receipt(b"img", type("F", (), {"content_type": "image/png"})())
        call = models.calls[0]
        assert call["model"] == parser.MODEL_NAME
        assert call["config"].response_mime_type == "application/json"
        assert call["config"].response_schema is parser.ParsedReceipt
