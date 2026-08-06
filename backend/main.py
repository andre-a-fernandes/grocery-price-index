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
import os
import time
from collections import defaultdict, deque
from typing import Optional
from dotenv import load_dotenv

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from core.parser import analyse_receipt, ParsedReceipt
from config.settings import MODEL_NAME

# Load .env file before reading any environment variables
load_dotenv()


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
    print("[receipt-ledger] WARNING: APP_SECRET is not set — /ocr/parse-receipt is UNAUTHENTICATED.")

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
        data = analyse_receipt(image_bytes, file)  # parser.parse_receipt(image_bytes)
    except Exception as e:
        raise e

    return ParsedReceipt.model_validate(data)


if __name__ == "__main__":
    import uvicorn

    # Cloud Run and Hugging Face Spaces inject the port via $PORT.
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)