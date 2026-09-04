"""HTTP tests for the API endpoints: auth, input validation, and the happy path.

No Gemini calls — the parser is stubbed or mocked entirely.
"""

from fastapi import HTTPException

import main


def _png_bytes(size: int = 10) -> bytes:
    """Minimal bytes served as an image/png — content is never inspected."""
    return b"\x89PNG\r\n\x1a\n" + b"0" * size


class TestHealthCheck:
    def test_root_returns_ok_and_model(self, client):
        res = client.get("/")
        assert res.status_code == 200
        body = res.json()
        assert body["status"] == "ok"
        assert body["model"] == main.MODEL_NAME


class TestParseReceiptAuth:
    def test_rejected_without_secret_when_auth_enabled(self, client, monkeypatch):
        monkeypatch.setattr(main, "APP_SECRET", "s3cret")
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", _png_bytes(), "image/png")},
        )
        assert res.status_code == 401

    def test_rejected_with_wrong_secret(self, client, monkeypatch):
        monkeypatch.setattr(main, "APP_SECRET", "s3cret")
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", _png_bytes(), "image/png")},
            headers={"X-App-Secret": "nope"},
        )
        assert res.status_code == 401


class TestParseReceiptInputValidation:
    def test_unsupported_content_type_rejected(self, client):
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("notes.txt", b"hello", "text/plain")},
        )
        assert res.status_code == 400
        assert "Unsupported image type" in res.json()["detail"]

    def test_empty_upload_rejected(self, client):
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", b"", "image/png")},
        )
        assert res.status_code == 400

    def test_oversize_upload_rejected(self, client):
        too_big = b"0" * (main.MAX_UPLOAD_BYTES + 1)
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", too_big, "image/png")},
        )
        assert res.status_code == 413


class TestParseReceiptHappyPath:
    def _stub_receipt(self):
        return {
            "store_name": "Albert Heijn",
            "receipt_date": "2026-03-09",
            "currency": "EUR",
            "items": [
                {
                    "raw_name": "AH Halfvolle Melk 1L",
                    "generalized_name": "Semi-Skimmed Milk",
                    "category": "dairy",
                    "quantity": 1,
                    "unit": "piece",
                    "total_price": 1.19,
                    "unit_price": 1.19,
                    "unit_price_uom": "per l",
                }
            ],
            "total": 1.19,
        }

    def test_valid_upload_returns_parsed_receipt(self, client, monkeypatch):
        monkeypatch.setattr(main, "analyse_receipt", lambda data, file: self._stub_receipt())
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", _png_bytes(), "image/png")},
        )
        assert res.status_code == 200
        body = res.json()
        assert body["store_name"] == "Albert Heijn"
        # generalised name must come back as the normalized lowercase key
        assert body["items"][0]["generalized_name"] == "semi-skimmed milk"

    def test_parser_failure_returns_502(self, client, monkeypatch):
        def boom(data, file):
            raise HTTPException(502, "Gemini request failed: simulated outage")

        monkeypatch.setattr(main, "analyse_receipt", boom)
        res = client.post(
            "/ocr/parse-receipt",
            files={"file": ("r.png", _png_bytes(), "image/png")},
        )
        assert res.status_code == 502
