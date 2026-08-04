# Receipt Tracker API

A FastAPI backend that turns a photo of a shopping receipt into structured JSON
using Google Gemini's multimodal input. A single endpoint handles OCR, line-item
extraction, product name generalization, and price-per-unit computation in one
request.

## Architecture

Instead of chaining a separate OCR API with a second LLM call, the receipt
photo goes directly to Gemini, which reads the image, extracts line items,
generalizes product names, and computes price-per-unit in a single request.
This keeps the backend to one API call, one dependency, and one credential.

The backend is **stateless** — it only does `image in → structured JSON out`.
The receipt ledger lives entirely in the PWA client's `localStorage`.

## API Endpoints

### `GET /`

Health check / liveness probe.

**Response:**

```json
{"status": "ok", "model": "gemini-2.5-flash"}
```

### `POST /ocr/parse-receipt`

Accept a receipt photo and return structured, generalized line items.

**Headers:**

| Header         | Required                  | Description                    |
|----------------|---------------------------|--------------------------------|
| `X-App-Secret` | If `APP_SECRET` is set    | Shared secret for authentication |

**Body:** `multipart/form-data` with a single `file` field
(`image/jpeg`, `image/png`, `image/webp`, or `image/heic`).

**Response:** `ParsedReceipt` JSON object:

```json
{
  "store_name": "Albert Heijn",
  "receipt_date": "2026-08-04",
  "currency": "EUR",
  "items": [
    {
      "raw_name": "AH Halfvolle Melk 1L",
      "generalized_name": "Semi-skimmed Milk",
      "category": "dairy",
      "quantity": 1,
      "unit": "l",
      "total_price": 1.29,
      "unit_price": 1.29,
      "unit_price_uom": "per l"
    }
  ],
  "total": 12.34
}
```

**Error responses:**

| Status | Meaning                                                |
|--------|--------------------------------------------------------|
| 400    | Unsupported image type or empty file                   |
| 401    | Missing or invalid `X-App-Secret` header               |
| 413    | Image exceeds `MAX_UPLOAD_MB` limit                    |
| 429    | Rate limit exceeded                                    |
| 502    | Gemini request failed or returned unparseable output   |

## Configuration

All configuration is via environment variables. See [`.env.example`](.env.example)
for a complete template.

| Variable                        | Default              | Description                              |
|---------------------------------|----------------------|------------------------------------------|
| `GEMINI_API_KEY`                | —                    | Gemini Developer API key (Option A)     |
| `GOOGLE_GENAI_USE_VERTEXAI`     | —                    | Set to `true` to use Vertex AI (Option B) |
| `GOOGLE_CLOUD_PROJECT`          | —                    | GCP project ID (Vertex AI)              |
| `GOOGLE_CLOUD_LOCATION`         | `us-central1`        | GCP region (Vertex AI)                  |
| `GOOGLE_APPLICATION_CREDENTIALS` | —                    | Path to service account JSON (Vertex AI) |
| `GEMINI_MODEL`                  | `gemini-2.5-flash`   | Gemini model to use                      |
| `APP_SECRET`                    | — (unauthenticated)  | Shared secret for API authentication     |
| `RATE_LIMIT_MAX_REQUESTS`       | `20`                 | Max requests per IP per window           |
| `RATE_LIMIT_WINDOW_SECONDS`     | `3600`               | Rate limit window duration (seconds)     |
| `MAX_UPLOAD_MB`                 | `8`                  | Max upload size in MB                    |
| `PORT`                          | `8000`               | Port to listen on (set by Cloud Run / HF Spaces) |

## Local Development

```bash
# Install dependencies using uv (or pip install -e .)
uv pip install -e .

# Set your Gemini API key
export GEMINI_API_KEY=your-key-here

# Run the server
python main.py
```

Visit `http://localhost:8000` to confirm the server is running.

## Local Testing with Docker

If you prefer to test the API in a containerized environment (closer to how it
runs in production), you can build and run the Docker image locally:

```bash
# Build the image
docker build -t receipt-tracker .

# Run the container
docker run --rm -p 8000:7860 -e GEMINI_API_KEY=your-key-here receipt-tracker
```

Then test the endpoints:

```bash
# Health check
curl http://localhost:8000/

# Parse a receipt (replace receipt.jpg with your own image)
curl -X POST http://localhost:8000/ocr/parse-receipt \
  -F "file=@receipt.jpg"
```

> **Note:** The container listens on port 7860 (the Hugging Face Spaces
> default). The `-p 8000:7860` flag maps it to `localhost:8000` so it matches
> the local development setup. If `APP_SECRET` is set, add the
> `-H "X-App-Secret: your-secret"` header to the `curl` command.

## Deployment

### Hugging Face Spaces (recommended — free, no card required)

1. Create a new Space at <https://huggingface.co/new-space>, SDK = **Docker**,
   hardware = free **CPU basic**.
2. Push the contents of `backend/` to the Space's git repo.
3. In **Settings → Variables and secrets**, add `GEMINI_API_KEY` as a secret.
4. Your API will be available at `https://<user>-<space>.hf.space`.

Free CPU Spaces sleep after inactivity and take ~30–60s to wake on the next
request.

### Google Cloud Run

```bash
gcloud run deploy receipt-ledger \
  --source . \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your-key-here"
```

Cloud Run's free tier (2M requests/month) covers personal use. A billing
account is required to deploy — set a budget alert to be notified before
any charges.

## Security Model

This is a personal, single-user tool with no login system. Three independent
layers protect the endpoint:

1. **Shared secret (`APP_SECRET`)** — Requests without a matching
   `X-App-Secret` header get `401`. Not real auth, but stops anyone from
   calling the API just by finding the URL.
2. **Per-IP rate limiting** — Independent of the secret, caps the blast
   radius if the secret leaks.
3. **Upload size cap + output token cap** — Bounds the cost of any single
   call.

See the [main README](../README.md#security-keeping-strangers-off-your-backend)
for a full discussion of the threat model and limitations.