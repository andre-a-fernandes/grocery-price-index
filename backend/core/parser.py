import json
from datetime import date
from typing import Optional

from fastapi import HTTPException, UploadFile
from google.genai import Client, types
from pydantic import BaseModel, Field, field_validator

from config.settings import MODEL_NAME

# Cacth-all prompt for the Gemini model to extract structured data from a receipt image.
PROMPT = """You are given a photo of a shopping receipt. Extract every purchased
line item and return it according to the provided schema.

Rules:
- Ignore non-item lines: subtotals, tax, payment method, loyalty point noise,
  store addresses, barcodes.
- If a quantity or unit isn't printed, assume quantity=1 and unit="piece".
  Examples of units: stuk (piece), kg, g, l/L, ml.
- Compute unit_price (per kg or per l) only when the item is naturally sold by
  weight or volume (produce, meat, dairy, drinks). Leave it null for
  count-based items (e.g. a single can, a box of pasta) unless the receipt
  gives you both a weight (g/ml or kg/L) and a total, in which case compute it.
- generalized_name should be short (1-4 words), store-agnostic, and written in
  Title Case for display (every word capitalised), e.g. "Semi-Skimmed Milk" or
  "Whole Wheat Bread", so the same product bought at two different stores gets
  the same generalized_name. The API normalises it into a lowercase comparison
  key automatically.
- If the date is missing or unreadable, use {today}.
"""


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
    quantity: float = Field(
        description=(
            "Number of units or amount purchased, default 1 if not printed/can't be inferred."
            + "Should match the unit, e.g. 1.5 kg, 2 L, 3 pieces, etc."
        )
    )
    unit: str = Field(description="Unit the quantity is measured in: piece, kg, g, l, ml, etc.")
    total_price: float = Field(
        description="Total price paid for this line item, in the receipt's currency"
    )
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

    @field_validator("generalized_name")
    @classmethod
    def normalize_generalized_name(cls, v: str) -> str:
        """Normalize generalized_name to a lowercase, canonical comparison id.

        The displayed label is Title Case (e.g. "Semi-Skimmed Milk"), but the
        frontend groups/sorts by this id — so a case difference must never
        split one product into two comparison buckets. Lowercase, strip, and
        collapse internal whitespace so the same product always maps to the
        same comparison id.
        """
        return " ".join(v.split()).lower()


class ParsedReceipt(BaseModel):
    store_name: str = Field(description="Store/merchant name as printed on the receipt")
    receipt_date: str = Field(
        description="Date on the receipt in YYYY-MM-DD format; use today's date if illegible"
    )
    currency: str = Field(description="Currency symbol or code, e.g. EUR, USD, $, \u20ac")
    items: list[ReceiptItem]
    total: Optional[float] = Field(
        default=None, description="Total amount on the receipt, if printed"
    )


def analyse_receipt(image_bytes: bytes, file: UploadFile) -> dict:
    """
    Run the receipt image through the Gemini model and return structured data.

    Raises HTTPException on any error.
    """
    # TODO: will use a single client instance for multiple calls
    try:
        client = Client()
    except Exception as exc:
        raise HTTPException(502, f"Failed to initialize Gemini client: {exc}") from exc

    try:
        prompt = PROMPT.format(today=date.today().isoformat())
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type=file.content_type),
                prompt,
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
        text = response.text
        if not text:
            raise HTTPException(502, "Model returned an empty response.")
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError) as exc:
        raise HTTPException(502, f"Model returned unparseable output: {exc}") from exc

    return data
