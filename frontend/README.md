# Receipt Tracker (Frontend)

A static, build-free Progressive Web App (PWA) for photographing, editing, and comparing grocery receipt line items.

> 📄 **Full Documentation:** Data schemas, `localStorage` persistence, and the **JSON Export & Import Specification** are documented in [**`docs/frontend.md`**](../docs/frontend.md).

## Quick Start

1. Open `index.html` in any modern web browser or serve static files locally:
   ```bash
   python -m http.server 8080 --directory frontend
   ```
2. Open on mobile devices and tap **"Add to Home Screen"** to install as a standalone PWA.

## App secret (why it's memory-only)

If your backend sets `APP_SECRET`, enter the same value in the settings panel.
It's kept in a plain in-memory variable — deliberately **not** in `localStorage`
or a cookie — so it can't be recovered later by reading the browser's stored
data or a dumped profile. Trade-off: it's gone on every reload, so re-enter it
after reloading the app.

For complete data model definitions, supported JSON import/export formats, and offline service worker caching details, see [**`docs/frontend.md`**](../docs/frontend.md).
