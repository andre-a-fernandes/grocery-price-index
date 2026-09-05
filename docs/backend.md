# Backend API Documentation

The backend is a FastAPI application (`backend/main.py`) that uses Google Gemini's multimodal capabilities to extract structured line-item data from grocery receipt photos.

---

## Architecture

Instead of chaining separate OCR and LLM pipelines, receipt photos go directly to Gemini, which reads the image, extracts line items, generalizes product names, and computes unit prices in a single request.

The backend is completely **stateless**: it accepts an image request and returns structured JSON. It does not connect to or maintain any server database.

---

## API Endpoints

### `GET /`

Health check / liveness probe.

**Response:**
```json
{
  "status": "ok",
  "model": "gemini-2.5-flash"
}
```

---

### `POST /ocr/parse-receipt`

Accept a receipt photo and return structured, generalized line items.

**Headers:**

| Header | Required | Description |
|---|---|---|
| `X-App-Secret` | If `APP_SECRET` is set | Shared secret for client authentication |

**Request Body:** `multipart/form-data` with a single `file` field (`image/jpeg`, `image/png`, `image/webp`, or `image/heic`).

**Response Schema (`ParsedReceipt`):**

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

**HTTP Status Codes:**

| Status | Description |
|---|---|
| `200` | Successful parsing |
| `400` | Unsupported image type or empty file |
| `401` | Missing or invalid `X-App-Secret` header |
| `413` | Upload file exceeds `MAX_UPLOAD_MB` limit |
| `429` | Rate limit exceeded |
| `502` | Gemini request failed or returned unparseable output |

---

## Configuration Reference

All settings are configured via environment variables:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | — | Gemini Developer API key (Option A) |
| `GOOGLE_GENAI_USE_VERTEXAI` | — | Set to `true` to use Vertex AI (Option B) |
| `GOOGLE_CLOUD_PROJECT` | — | GCP project ID for Vertex AI |
| `GOOGLE_CLOUD_LOCATION` | `us-central1` | GCP region for Vertex AI |
| `GOOGLE_APPLICATION_CREDENTIALS` | — | Path to service account JSON for Vertex AI |
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model name |
| `APP_SECRET` | — (unauthenticated) | Shared secret required in `X-App-Secret` header |
| `RATE_LIMIT_MAX_REQUESTS` | `20` | Maximum requests per IP per window |
| `RATE_LIMIT_WINDOW_SECONDS` | `3600` | Rate limit window duration (in seconds) |
| `MAX_UPLOAD_MB` | `8` | Maximum file upload size in MB |
| `PORT` | `8000` | Server listening port |

---

## Local Development & Testing

### Running Locally

```bash
cd backend
uv pip install -e .
export GEMINI_API_KEY=your-key-here
python main.py
```

### Running with Docker

```bash
# Build image from root
docker build -f .docker/backend.Dockerfile -t backend .

# Run container
docker run --rm -p 8000:7860 -e GEMINI_API_KEY=your-key-here backend
```

---

## Deployment Options

### Hugging Face Spaces (Free CPU Docker Space)
1. Create a Space on Hugging Face (SDK: **Docker**).
2. Copy `.docker/backend.Dockerfile` to `Dockerfile` at root.
3. Set secret `GEMINI_API_KEY` in HF Space settings.

### Google Cloud Run
```bash
gcloud run deploy receipt-ledger \
  --source . \
  --dockerfile .docker/backend.Dockerfile \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your-key-here"
```
