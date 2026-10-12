# Receipt Tracker (Frontend)

A static, build-free Progressive Web App (PWA) for photographing, editing, and comparing grocery receipt line items.

> 📄 **Full Documentation:** Data schemas, `localStorage` persistence, and the **JSON Export & Import Specification** are documented in [**`docs/frontend.md`**](../docs/frontend.md).

## Quick Start

1. Open `index.html` in any modern web browser or serve static files locally:
   ```bash
   python -m http.server 8080 --directory frontend
   ```
2. Open on mobile devices and tap **"Add to Home Screen"** to install as a standalone PWA.

## Testing

Frontend tests use Node's built-in test runner (zero external dependencies required):

```bash
node frontend/tests/test_collapsible_receipts.js
# or
node --test frontend/tests/test_collapsible_receipts.js
```

These tests automatically run in CI on pull requests, pushes, and release tags affecting the frontend.

For complete data model definitions, supported JSON import/export formats, and offline service worker caching details, see [**`docs/frontend.md`**](../docs/frontend.md).
