"""
Receipt Tracker API
===================
A single-endpoint FastAPI backend that turns a photo of a shopping receipt
into structured JSON: store name, date, and a list of line items with
quantity, price, a generalized item name/category, and a normalized
price-per-unit (e.g. price per kg or per liter) for cross-store comparison.

Uses Gemini's native multimodal input to perform OCR, structuring, and
product-name generalization in a single request — no separate OCR API
or second LLM call needed. This keeps the backend to one API call, one
dependency, and one credential.

Authentication is handled by google-genai, which supports two interchangeable
backends controlled entirely by environment variables:

  1. Gemini Developer API:
       GEMINI_API_KEY=<key from https://aistudio.google.com/apikey>

  2. Vertex AI:
       GOOGLE_GENAI_USE_VERTEXAI=true
       GOOGLE_CLOUD_PROJECT=<your-gcp-project-id>
       GOOGLE_CLOUD_LOCATION=us-central1
       GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json

See README.md for setup instructions.
"""

import hmac
import json
import os
import time
from collections import defaultdict, deque
from datetime import date
from typing import Optional

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# --------------------------------------------------------------------------
# Gemini client
# --------------------------------------------------------------------------
# google-genai automatically reads GEMINI_API_KEY or the Vertex AI env vars.
client = genai.Client()
MODEL_NAME = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


# --------------------------------------------------------------------------
# Response schema
# --------------------------------------------------------------------------
# Passed to Gemini as a controlled-generation schema so the model returns
# valid, predictable JSON instead of free text.
class ReceiptItem(BaseModel):
    raw_name: str = Field(description="Item name exactly as printed on the receipt")
    generalized_name: str = Field(
        description=(
            "A short, generic name for this product with brand/size noise "
            "removed, so the same product from different stores maps to the "
            "same label, e.g. 'AH Halfvolle Melk 1L' -> 'Semi-skimmed Milk'."
        )
    )
    category: str = Field(
        description="Broad grocery category, e.g. dairy, produce, meat, bakery, household"
    )
    quantity: float = Field(description="Number of units purchased, default 1 if not printed")
    unit: str = Field(
        description="Unit the quantity is measured in: piece, kg, g, l, ml, etc."
    )
    total_price: float = Field(description="Total price paid for this line item, in the receipt's currency")
    unit_price: Optional[float] = Field(
        default=None,
        description=(
            "Price normalized to a standard unit (per kg or per l) when the "
            "item is sold by weight/volume, to allow comparison across "
            "package sizes and stores. Null for count-based items like 'piece'/'stuk'."
        ),
    )
    unit_price_uom: Optional[str] = Field(
        default=None, description="Unit the unit_price is expressed in, e.g. 'per kg', 'per l'"
    )


class ParsedReceipt(BaseModel):
    store_name: str = Field(description="Store/merchant name as printed on the receipt")
    receipt_date: str = Field(description="Date on the receipt in YYYY-MM-DD format; use today's date if illegible")
    currency: str = Field(description="Currency symbol or code, e.g. EUR, USD, $, \u20ac")
    items: list[ReceiptItem]
    total: Optional[float] = Field(default=None, description="Total amount on the receipt, if printed")


# --------------------------------------------------------------------------
# Security
# --------------------------------------------------------------------------
# APP_SECRET is a shared secret between this backend and the PWA client.
# It is not a substitute for real auth — it prevents anyone who finds the
# URL from calling the API. Set it as an env var on your deploy platform
# and enter the same value in the PWA's settings panel (stored in the
# browser's localStorage, never committed to the repo).
#
# If APP_SECRET is unset, auth is skipped (useful for local dev). The
# startup log warns loudly so this isn't accidental in production.
APP_SECRET = os.environ.get("APP_SECRET", "")
if not APP_SECRET:
    print("[receipt-ledger] WARNING: APP_SECRET is not set — /api/parse-receipt is UNAUTHENTICATED.")

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_MB", "8")) * 1024 * 1024

# In-memory sliding-window rate limit, per client IP. Not backed by Redis
# or a DB — this is a single personal-use instance. Resets on every
# redeploy/cold start.
RATE_LIMIT_MAX_REQUESTS = int(os.environ.get("RATE_LIMIT_MAX_REQUESTS", "20"))
RATE_LIMIT_WINDOW_SECONDS = int(os.environ.get("RATE_LIMIT_WINDOW_SECONDS", "3600"))  # 1 hour
_request_log: dict[str, deque] = defaultdict(deque)


def check_rate_limit(client_id: str) -> None:
    """Raise 429 if client_id has exceeded RATE_LIMIT_MAX_REQUESTS in the window."""
    now = time.time()
    log = _request_log[client_id]
    while log and now - log[0] > RATE_LIMIT_WINDOW_SECONDS:
        log.popleft()
    if len(log) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(429, "Rate limit exceeded — try again later.")
    log.append(now)


def check_app_secret(x_app_secret: Optional[str]) -> None:
    """Constant-time comparison so response timing can't leak the secret."""
    if not APP_SECRET:
        return  # auth disabled (local dev only — see warning above)
    if not x_app_secret or not hmac.compare_digest(x_app_secret, APP_SECRET):
        raise HTTPException(401, "Invalid or missing X-App-Secret header.")


# --------------------------------------------------------------------------
# App
# --------------------------------------------------------------------------
app = FastAPI(title="Receipt Tracker API", version="1.0.0")

# Wide-open CORS: CORS only constrains browser JS running on other
# origins — it does nothing against direct API calls (curl/scripts),
# which is the threat the secret + rate limit above address.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

PROMPT = f"""You are given a photo of a shopping receipt. Extract every purchased
line item and return it according to the provided schema.

Rules:
- Ignore non-item lines: subtotals, tax, payment method, loyalty point noise,
  store addresses, barcodes.
- If a quantity or unit isn't printed, assume quantity=1 and unit="piece".
- Compute unit_price (per kg or per l) only when the item is naturally sold by
  weight or volume (produce, meat, dairy, drinks). Leave it null for
  count-based items (e.g. a single can, a box of pasta) unless the receipt
  gives you both a weight and a total, in which case compute it.
- generalized_name should be short (1-4 words) and store-agnostic so the same
  product bought at two different stores gets the same generalized_name.
- If the date is missing or unreadable, use {date.today().isoformat()}.
"""


@app.get("/")
def health_check():
    """Liveness check — also useful for confirming the deploy worked."""
    return {"status": "ok", "model": MODEL_NAME}


@app.post("/ocr/parse-receipt", response_model=ParsedReceipt)
async def parse_receipt(
    request: Request,
    file: UploadFile = File(...),
    x_app_secret: Optional[str] = Header(default=None, alias="X-App-Secret"),
) -> ParsedReceipt:
    """
    Accept a receipt photo (jpeg/png/webp/heic) and return structured,
    generalized line items.

    Protected by a shared-secret header, per-IP rate limit, and upload
    size cap. See the security config section above for details.
    """
    check_app_secret(x_app_secret)
    client_ip = request.client.host if request.client else "unknown"
    check_rate_limit(client_ip)

    if file.content_type not in ("image/jpeg", "image/png", "image/webp", "image/heic"):
        raise HTTPException(400, f"Unsupported image type: {file.content_type}")

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(400, "Empty file upload")
    if len(image_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Image exceeds {MAX_UPLOAD_BYTES // (1024*1024)}MB limit")

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=file.content_type),
                PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=ParsedReceipt,
                temperature=0.1,
                # Cap output tokens to bound the cost of any single call,
                # even from an authenticated user. A typical receipt's
                # structured JSON fits well under this limit.
                max_output_tokens=4096,
            ),
        )
    except Exception as exc:  # Surface upstream errors clearly to the client
        raise HTTPException(502, f"Gemini request failed: {exc}") from exc

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(502, f"Model returned unparseable output: {exc}") from exc

    return ParsedReceipt.model_validate(data)


if __name__ == "__main__":
    import uvicorn

    # Cloud Run and Hugging Face Spaces inject the port via $PORT.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)