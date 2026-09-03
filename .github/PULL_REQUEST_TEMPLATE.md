## Summary

<!-- One or two sentences: what and why. Closes #issue -->

## Changes

<!-- Bullet list of the key changes, grouped by area -->

## Why

<!-- Brief rationale for the approach taken -->

## Testing

<!-- How you verified: commands run, expected vs actual, screenshots -->

#################

## Summary

Normalize `generalized_name` so equivalent products (`"Bread"` vs `"bread"`) collide into the same comparison bucket. Closes [#2](https://github.com/andre-a-fernandes/grocery-price-index/issues/2).

## Changes

- **Backend**: Pydantic `field_validator` lowercases + trims + collapses whitespace on `generalized_name`; prompt updated to emit Title Case for display.
- **Frontend**: `normalizeName()` for comparison, `titleCase()` for display; applied across input, history, compare dropdown, and markdown export.

## Why

Lowercase is a lossless canonical id; Title Case is display-only, avoiding backend/frontend edge-case disagreement.

## Testing

- Backend: `Bread`/`bread` → `bread` (collide)
- Frontend: `bread` → `Bread` (display), comparison collide: `true`