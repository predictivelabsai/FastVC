# Build Product Tour

Generate the FastVC product tour deck as landscape PDF and editable PPTX.

## What it does

Builds a slide-deck-style product tour with embedded screenshots, using FastVC branding (light neutral background with cobalt and violet accents).

## Run

```bash
python -m scripts.make_pdf       # → docs/fastvc-product-tour.pdf
python -m scripts.make_pptx      # → docs/fastvc-product-tour.pptx
```

## Output

- `docs/fastvc-product-tour.pdf` (~2 MB, landscape 16:9)
- `docs/fastvc-product-tour.pptx` (~1.5 MB, editable deck)

## Notes

- Uses `reportlab` for PDF and `python-pptx` for PPTX (both in requirements.txt)
- Screenshots pulled from `screenshots/` directory
- Different from the user guide: this is a marketing/sales deck, not a how-to guide
