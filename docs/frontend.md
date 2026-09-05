# Frontend & Data Specification

The frontend is a static, installable Progressive Web App (PWA) located in `frontend/`. It handles photo capture, user review and editing, local ledger persistence, comparison grouping, and JSON/Markdown data export and import.

---

## File Structure

- `frontend/index.html` — Complete UI layout, styles, and application logic.
- `frontend/manifest.json` — PWA metadata (icons, display mode, theme colors).
- `frontend/sw.js` — Service worker providing offline app-shell caching.
- `frontend/icon.png` — App icon for mobile home screens.

---

## Data Model & Local Storage

Receipts are persisted locally in `localStorage` under the key `"receipts_v1"`.

### Data Types & Schema

#### `Receipt` Object
```typescript
interface Receipt {
  id: string;              // Unique identifier (UUID or generated fallback)
  store_name: string;      // Merchant / store name (e.g. "Albert Heijn")
  receipt_date: string;    // Receipt date in YYYY-MM-DD format
  saved_at: string;        // ISO 8601 timestamp when saved locally
  currency?: string;       // Currency symbol or ISO code (default "EUR")
  items: ReceiptItem[];    // Itemized list of purchased products
}
```

#### `ReceiptItem` Object
```typescript
interface ReceiptItem {
  generalized_name: string; // Standardized product name for price comparison (e.g. "semi-skimmed milk")
  quantity_label: string;  // Product volume / weight label (e.g. "1 l", "500 g")
  total_price: number;     // Total price paid for the line item
  category?: string;       // Product category (e.g. "dairy", "bakery")
  unit_price?: number;     // Computed price per unit (e.g. 1.29)
  unit_price_uom?: string; // Unit of measure (e.g. "per l", "per kg")
}
```

---

## Exportable / Importable JSON Receipt History

To preserve history across browser updates, schema migrations, or device transfers, users can export and import their ledger as a JSON file.

### Supported Root Structures

The importer supports two root JSON formats:

1. **Top-Level Array Format (Default Export):**
```json
[
  {
    "id": "c1f7b80a-9d8e-4a62-b98a-1a3b4c5d6e7f",
    "store_name": "Albert Heijn",
    "receipt_date": "2026-08-04",
    "saved_at": "2026-08-04T10:03:00.000Z",
    "currency": "EUR",
    "items": [
      {
        "generalized_name": "semi-skimmed milk",
        "quantity_label": "1 l",
        "total_price": 1.29,
        "category": "dairy",
        "unit_price": 1.29,
        "unit_price_uom": "per l"
      }
    ]
  }
]
```

2. **Wrapped Object Format:**
```json
{
  "receipts": [
    {
      "id": "c1f7b80a-9d8e-4a62-b98a-1a3b4c5d6e7f",
      "store_name": "Albert Heijn",
      "receipt_date": "2026-08-04",
      "saved_at": "2026-08-04T10:03:00.000Z",
      "currency": "EUR",
      "items": [
        {
          "generalized_name": "semi-skimmed milk",
          "quantity_label": "1 l",
          "total_price": 1.29,
          "category": "dairy",
          "unit_price": 1.29,
          "unit_price_uom": "per l"
        }
      ]
    }
  ]
}
```

---

## Exporting & Importing Logic

### Exporting JSON (`Export JSON` button)
1. Reads all saved receipts from `localStorage["receipts_v1"]`.
2. Serializes data using `JSON.stringify(receipts, null, 2)`.
3. Creates a downloadable Blob (`application/json`) with the filename format `receipts-ledger-YYYY-MM-DD.json`.

### Importing JSON (`Import JSON` button)
1. Prompts file selection (`.json`).
2. Reads and parses the file via `FileReader`.
3. **Validation Rules:**
   - Verifies the root payload is an array or contains a `.receipts` array.
   - Filters entries to ensure each item is an object with an `items` array.
4. **ID Generation & Merging Rules:**
   - If an imported receipt lacks an `id`, a unique ID is automatically assigned (`crypto.randomUUID()` or timestamp fallback).
   - Merges entries into local storage by `id`:
     - **Existing ID:** Updates the stored receipt entry with imported data.
     - **New ID:** Appends the imported receipt.
5. Re-renders the **History** and **Compare** views and notifies the user with a summary toast (e.g. `"Imported 2 new, 0 updated"`).

---

## Markdown Export

The Compare view also includes an **Export full ledger as Markdown** option:
- Copies a Markdown table to the clipboard, formatted for easy pasting into Notion or note-taking apps:

```markdown
| Item | Store | Date | Qty | Price | Unit price |
|---|---|---|---|---|---|
| Semi-Skimmed Milk | Albert Heijn | 2026-08-04 | 1 l | EUR1.29 | EUR1.29 per l |
```
