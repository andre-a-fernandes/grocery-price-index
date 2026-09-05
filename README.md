# Grocery Price Index (Receipt analysis)

Photograph a grocery receipt on your phone → a Gemini-powered backend turns it
into structured line items (name, quantity, price, generalized product name,
price-per-kg/l) → you keep an editable, comparable price ledger stored
entirely on your phone.

```
📱 PWA (frontend/)  --photo-->  ☁️ FastAPI + Gemini (backend/)  --JSON-->  📱 localStorage
```

<div align="center">

## 📱 [Launch Grocery Price Index](https://andre-a-fernandes.github.io/grocery-price-index/frontend/)

**Quick Start:** Open the link on your phone, tap your browser options (Share or ⋮), and select **"Add to Home Screen"** to install the app.

</div>

## Why it's built this way

- **One backend call, not two.** Instead of OCR (Vision/Document AI) feeding
  a second LLM call, the receipt photo goes straight into Gemini, which is
  multimodal: it reads the image, extracts line items, generalizes product
  names, and computes price-per-unit in a single request. Less to deploy,
  less to pay for, less to debug.
- **No server-side database.** The backend is stateless — it only ever does
  `image in -> structured JSON out`. Your ledger lives in the browser's
  `localStorage` on your phone. Nothing to host, back up, or pay for beyond
  the Gemini calls themselves.
- **No app store, no build step.** The frontend is a single static HTML
  file — a installable Progressive Web App (PWA). "Installing" it is just
  opening a URL and tapping "Add to Home Screen."

## What you get

- **Scan tab** — take a photo → Gemini parses it → review/edit the table →
  save.
- **History tab** — every saved receipt, itemized, with a delete option.
- **Compare tab** — pick a generalized item (e.g. "milk") and see it ranked
  cheapest-first across every store/date you've scanned, using price-per-kg/l
  where applicable.
- **Export to Markdown** — one tap copies your whole ledger as a Markdown
  table, ready to paste into a Notion page.

---

## 1. Backend setup (~10 min)

The backend is a ~200 line FastAPI app in `backend/main.py`.

### Get a Gemini API key (fastest option)

1. Go to <https://aistudio.google.com/apikey> and create a free API key.
2. That's it — no GCP project, no service account, no billing setup needed
   for light personal use.

> **Already have GCP credentials and want to use Vertex AI instead?** See
> [Using Vertex AI instead of an API key](#using-vertex-ai-instead-of-an-api-key)
> below. Functionally identical, just swaps which env vars you set.

### Run it locally first (sanity check)

```bash
cd backend
uv pip install -e .
export GEMINI_API_KEY=your-key-here
python main.py
```

Visit `http://localhost:8000` — you should see `{"status": "ok", ...}`.

### Deploy for free

#### Hugging Face Spaces — recommended, genuinely free, no card

The Dockerfile lives at `.docker/backend.Dockerfile` and expects the
**repository root** as its build context (it copies from `backend/`).
HF Spaces looks for a `Dockerfile` at the Space repo root, so:

1. Create a new Space at <https://huggingface.co/new-space>, SDK = **Docker**,
   hardware = free **CPU basic**.
2. Clone your Space's git repo. From the project root:
   ```bash
   cp .docker/backend.Dockerfile Dockerfile
   ```
3. Push `backend/`, `uv.lock`, and the `Dockerfile` to the Space.
4. In the Space's **Settings → Variables and secrets**, add a secret:
   `GEMINI_API_KEY = your-key-here`.
5. Wait for the build to finish. Your API is now at
   `https://<your-username>-<space-name>.hf.space`.

Free CPU Spaces go to sleep after a period of inactivity and take ~30-60s to
wake up on the next request — a non-issue for scanning a few receipts a
week, just don't expect an instant response on the very first scan of the
day.

#### Alternative — Google Cloud Run (one-command deploy, but requires a card on file)

Run from the **repository root** (not `backend/`):

```bash
gcloud run deploy receipt-ledger \
  --source . \
  --dockerfile .docker/backend.Dockerfile \
  --region=us-central1 \
  --allow-unauthenticated \
  --set-env-vars="GEMINI_API_KEY=your-key-here"
```

`gcloud` builds the Docker image, pushes it, and deploys it in one step.
Cloud Run's Always Free tier (2M requests/month) comfortably covers personal
use and this will cost $0/month — but Google requires a billing account
(card) attached to the project to deploy at all. If you go this route,
set a budget alert immediately: **Billing → Budgets & alerts → Create
Budget → target $1** so you're notified before anything is ever charged.

### Using Vertex AI instead of an API key

If you'd rather use your existing GCP project's credentials:

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT=your-gcp-project-id
export GOOGLE_CLOUD_LOCATION=us-central1
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

Or, on Cloud Run, skip `GOOGLE_APPLICATION_CREDENTIALS` entirely and just
grant the Cloud Run service account the **Vertex AI User** role — it'll
authenticate automatically. See `.env.example` for the full list of options.

**Higher-accuracy OCR alternative:** for messy/faded receipts, Google
Document AI's pretrained **Expense Parser** processor is purpose-built for
receipts and more robust than asking Gemini to read pixels directly. It's a
5-minute addition if accuracy becomes an issue: create the processor in the
GCP Console, call it first to get raw line items, then still use Gemini (or
even a plain prompt) for the generalization/price-per-unit step. Not
included here to keep the initial setup to one API.

---

## 2. Frontend setup (~5 min)

The frontend is fully static — `frontend/index.html`, `manifest.json`,
`sw.js`, `icon.png`. No build step, no npm install.

### Host it somewhere reachable over HTTPS

PWAs (and camera access, and clipboard access) require HTTPS. Easiest free
options:

- **GitHub Pages** — push `frontend/` to a repo, enable Pages on it. Free,
  HTTPS by default.
- **Cloudflare Pages / Netlify / Vercel** — drag-and-drop the `frontend/`
  folder in their web UI, done in under a minute.

### Install it on your phone

1. Open your deployed frontend URL in **Safari** (iOS) or **Chrome**
   (Android).
2. **iOS:** tap the Share icon → **Add to Home Screen**.
   **Android:** tap the ⋮ menu → **Add to Home screen** / **Install app**.
3. Open the app from your home screen — it now runs full-screen, no browser
   chrome, like a native app.
4. On first use, tap **backend settings** on the Scan tab and paste in your
   backend URL from step 1 (e.g. `https://receipt-ledger-xxxx.run.app`) and,
   if you set `APP_SECRET` on the backend, the matching secret. Both are
   saved locally and you won't need to re-enter them.

---

## 3. Using it

1. **Scan tab** → tap the capture zone → take a photo of a receipt → tap
   **Parse receipt**.
2. Review the extracted items (edit any field Gemini got wrong) → **Save to
   ledger**.
3. **Compare tab** → pick a product → see every store/date you've bought it,
   cheapest first (by price-per-kg/l when available).
4. **Export full ledger as Markdown** → paste directly into a Notion page.

---

## Project structure

```
grocery-price-index/
├── .docker/
│   └── backend.Dockerfile # works for both HF Spaces and Cloud Run (build from repo root)
├── backend/
│   ├── main.py            # FastAPI app: POST /ocr/parse-receipt
│   ├── pyproject.toml     # Python project config & dependencies
│   └── .env.example       # environment variable template
├── frontend/
│   ├── index.html         # entire UI + logic, no build step
│   ├── manifest.json      # PWA install metadata
│   ├── sw.js              # offline app-shell cache
│   └── icon.png
├── pyproject.toml         # workspace root (uv)
├── uv.lock                # workspace lock file
├── .dockerignore          # exclude useless files from context
├── README.md
└── LICENSE
```

## Data model

Each saved receipt in `localStorage["receipts_v1"]`:

```json
{
  "id": "uuid",
  "store_name": "Albert Heijn",
  "receipt_date": "2026-08-04",
  "saved_at": "2026-08-04T10:03:00.000Z",
  "items": [
    {
      "generalized_name": "milk",
      "quantity_label": "1 l",
      "total_price": 1.29,
      "category": "dairy",
      "unit_price": 1.29,
      "unit_price_uom": "per l"
    }
  ]
}
```

`generalized_name` is what the Compare tab groups on — it's what lets "AH
Halfvolle Melk 1L" and "Jumbo Verse Melk 1L" both roll up under "milk" for
comparison, and it's editable per-item if Gemini's generalization is too
broad or too narrow for your taste.

## Security: keeping strangers off your backend

This is a personal, single-user tool with no login system, so "securing"
it means something narrower than usual: make it hard for a stranger to
find and call your API, and cap the damage if they do anyway. Three
independent layers, none of which require a database or user accounts:

1. **Shared secret (`APP_SECRET`).** Set it as an env var on your backend
   deploy, and enter the identical value into the PWA's settings panel
   (stored in `localStorage`, never committed to git). Requests without a
   matching `X-App-Secret` header get `401`. This isn't "real" auth — a
   secret that a client-side app sends can theoretically be intercepted —
   but it stops anyone from calling your API just by finding the URL,
   which is the realistic threat for a hobby deploy.
2. **Per-IP rate limiting** (`RATE_LIMIT_MAX_REQUESTS` / `_WINDOW_SECONDS`,
   default 20/hour) — independent of the secret, so even a leaked secret
   or a misbehaving client can't run unbounded requests.
3. **Upload size cap** (`MAX_UPLOAD_MB`, default 8) and a **capped Gemini
   output size** (`max_output_tokens=4096` in `main.py`) — bounds the cost
   of any single call, successful or not.

**Worth knowing:** if you're on the free Gemini Developer API tier (an
AI Studio key, no billing account attached), none of this actually
protects against *cost* — going over quota just returns errors, it can't
generate a bill. It protects your own daily quota from being exhausted by
someone else. If you switch to a paid/Vertex AI key, these same
protections start being your actual cost defense, so it's worth keeping
them on either way.

**What this setup deliberately doesn't do:** stop a determined attacker
who's willing to inspect network requests from your own phone to extract
the secret. That level of protection would need per-user auth (e.g. a
real OAuth flow), which is out of scope for a weekend personal tool —
if you ever share this with other people rather than using it solo,
that's the point to revisit.

## Known limitations / next steps if you want to extend this

- No cross-device sync — the ledger is per-browser `localStorage`. If you
  want it on multiple devices, swap the storage layer for a small hosted
  DB (e.g. a free Supabase/Turso tier) — the frontend's `loadReceipts` /
  `saveReceipts` functions are the only two places that would need to
  change.
- Currency is assumed from the receipt; there's no conversion between
  currencies in the Compare view.

---

## License

This project is licensed under the terms specified in the [LICENSE](LICENSE) file.

## Contributing

This is a personal project, but suggestions and improvements are welcome.
Feel free to open an issue or submit a pull request.
