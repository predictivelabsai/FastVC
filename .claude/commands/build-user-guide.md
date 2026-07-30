# Build User Guide

Rebuild the FastVC user guide as A4 landscape PDF and 16:9 PPTX.

## What it does

1. Runs `bash scripts/build_user_guide.sh` which:
   - Converts `docs/user_guide.md` to standalone HTML via **pandoc**
   - Applies `docs/assets/guide.css` (FastVC branding, landscape layout)
   - Renders to PDF via **WeasyPrint** → `docs/fastvc-user-guide.pdf`
   - Builds PPTX via `scripts/build_guide_pptx.py` → `docs/fastvc-user-guide.pptx`
2. Reports file sizes and slide count

## Run

```bash
bash scripts/build_user_guide.sh
```

## Prerequisites

- `pandoc` (system package)
- `weasyprint` (pip or system)
- `python-pptx` (in requirements.txt)

## Source files

- `docs/user_guide.md` — markdown source (edit this to update content)
- `docs/assets/guide.css` — CSS for PDF rendering (landscape A4, FastVC palette)
- `scripts/build_guide_pptx.py` — PPTX builder (FastVC-branded 16:9 slides)
- `screenshots/` — product screenshots referenced by the markdown (symlinked at `docs/screenshots`)

## Output

- `docs/fastvc-user-guide.pdf` (~1.6 MB, A4 landscape)
- `docs/fastvc-user-guide.pptx` (~1.5 MB, 24 slides)

## Notes

- Screenshots are referenced as `screenshots/*.png` in the markdown. The `docs/screenshots` symlink points to the repo-root `screenshots/` directory.
- The CSS footer date is auto-stamped on each build.
- To add a new slide, add a `---` separator and an `## H2 Title` in `docs/user_guide.md`. Optionally include `![alt](screenshots/XX-name.png)` for a right-floated screenshot.
