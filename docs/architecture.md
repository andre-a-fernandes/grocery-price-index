# System Architecture

The **Grocery Price Index** is designed as a privacy-first, serverless-style Progressive Web App (PWA) with a single-purpose stateless backend.

```
┌────────────────────────────────┐                 ┌──────────────────────────────┐
│  📱 Mobile PWA (frontend/)     │ ── photo ─────> │ ☁️ FastAPI Backend           │
│  - Camera input                │                 │    (backend/main.py)         │
│  - Review & ledger table       │ <── JSON ────── │  - Validates request & secret│
│  - Local storage persistence   │                 │  - Calls Google Gemini API   │
│  - JSON export / import        │                 └──────────────────────────────┘
└────────────────────────────────┘
```

---

## Key Architectural Decisions

### 1. One Backend Call, Not Two
Instead of chaining a separate OCR service (e.g. Document AI / Vision API) with an LLM call to structure the text, receipt photos go straight into **Google Gemini**. Gemini is multimodal: it reads the receipt image, extracts line items, generalizes product names, and computes unit prices in a single API call. This minimizes latency, infrastructure complexity, operational costs, and debugging surface area.

### 2. No Server-Side Database
The backend is completely **stateless** — it only exposes `image in -> structured JSON out`. All parsed receipt history resides in the user's browser via `localStorage`.

**Benefits:**
- **Zero server data storage costs:** No database instance to run, host, or back up.
- **Privacy by default:** Personal financial data and shopping habits never leave the user's local device.
- **Data safety via JSON export/import:** Users can backup, migrate, or restore their history across devices or version updates.

### 3. Build-Free Static PWA
The frontend is a single static HTML document (`frontend/index.html`) with no build steps, no npm dependencies, and no bundlers.
- Installed on mobile devices by tapping "Add to Home Screen".
- Offline-enabled app-shell caching via `frontend/sw.js`.

---

## Security & Protection Model

Since the app is single-user without an account system, backend security focuses on preventing unauthorized access to the Gemini API endpoint:

1. **Shared Secret (`APP_SECRET`):**
   - Configured on the backend deploy and saved in the PWA's local settings.
   - Sent via the `X-App-Secret` request header.
   - Rejects unauthenticated requests with `401 Unauthorized`.

2. **Per-IP Rate Limiting:**
   - Limits incoming requests per IP (default: 20 requests per hour).
   - Protects API quota from exhaustion.

3. **Upload Caps & Token Safeguards:**
   - Maximum upload size capped at `MAX_UPLOAD_MB` (default 8MB).
   - Maximum model output tokens capped at 4096 tokens in Gemini configuration.
