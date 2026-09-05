"""Pydantic validation of ReceiptItem and ParsedReceipt, including the
generalized_name normalization that keeps one product in one comparison bucket."""

import pytest
from pydantic import ValidationError

from core.parser import ParsedReceipt, ReceiptItem


def _item_kwargs(**overrides):
    """A minimal valid ReceiptItem payload; tests override single fields."""
    kwargs = {
        "raw_name": "AH Halfvolle Melk 1L",
        "generalized_name": "Semi-Skimmed Milk",
        "category": "dairy",
        "quantity": 1,
        "unit": "piece",
        "total_price": 1.19,
        "unit_price": None,
        "unit_price_uom": None,
    }
    kwargs.update(overrides)
    return kwargs


class TestGeneralizedNameNormalization:
    """The lowercase comparison key — same product must never split into
    two buckets because of case or whitespace (case-sensitivity bugfix)."""

    def test_title_case_is_lowercased(self):
        item = ReceiptItem(**_item_kwargs(generalized_name="Semi-Skimmed Milk"))
        assert item.generalized_name == "semi-skimmed milk"

    def test_uppercase_is_lowercased(self):
        item = ReceiptItem(**_item_kwargs(generalized_name="MILK"))
        assert item.generalized_name == "milk"

    def test_internal_whitespace_is_collapsed(self):
        item = ReceiptItem(**_item_kwargs(generalized_name="  whole   wheat \t bread "))
        assert item.generalized_name == "whole wheat bread"

    def test_different_spellings_map_to_same_key(self):
        a = ReceiptItem(**_item_kwargs(generalized_name="Semi-Skimmed Milk"))
        b = ReceiptItem(**_item_kwargs(generalized_name="semi-skimmed MILK"))
        assert a.generalized_name == b.generalized_name


class TestReceiptItemDefaults:
    def test_optional_price_fields_default_to_none(self):
        item = ReceiptItem(**_item_kwargs())
        assert item.unit_price is None
        assert item.unit_price_uom is None

    def test_unit_price_is_kept_when_given(self):
        item = ReceiptItem(**_item_kwargs(unit_price=1.59, unit_price_uom="per l"))
        assert item.unit_price == 1.59
        assert item.unit_price_uom == "per l"

    @pytest.mark.parametrize("missing", ["raw_name", "generalized_name", "total_price"])
    def test_required_fields_are_required(self, missing):
        kwargs = _item_kwargs()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            ReceiptItem(**kwargs)


class TestParsedReceipt:
    def _receipt_kwargs(self, **overrides):
        kwargs = {
            "store_name": "Albert Heijn",
            "receipt_date": "2026-03-09",
            "currency": "EUR",
            "items": [_item_kwargs()],
        }
        kwargs.update(overrides)
        return kwargs

    def test_valid_receipt_parses(self):
        receipt = ParsedReceipt(**self._receipt_kwargs())
        assert receipt.store_name == "Albert Heijn"
        assert len(receipt.items) == 1

    def test_total_defaults_to_none(self):
        receipt = ParsedReceipt(**self._receipt_kwargs())
        assert receipt.total is None

    def test_empty_items_list_is_allowed(self):
        receipt = ParsedReceipt(**self._receipt_kwargs(items=[]))
        assert receipt.items == []

    def test_item_is_normalized_inside_receipt(self):
        receipt = ParsedReceipt(**self._receipt_kwargs())
        assert receipt.items[0].generalized_name == "semi-skimmed milk"

    @pytest.mark.parametrize("missing", ["store_name", "receipt_date", "currency", "items"])
    def test_required_fields_are_required(self, missing):
        kwargs = self._receipt_kwargs()
        del kwargs[missing]
        with pytest.raises(ValidationError):
            ParsedReceipt(**kwargs)
