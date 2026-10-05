#!/usr/bin/env python3
"""
Give scanned PDF pages a hidden text layer so they search, copy, and
link like the manuals that already contain real text.

A page is a scan when it has a picture and almost no letters. Tesseract
reads the picture and the words are stored invisibly on that page. The
picture still looks the same. Running this again skips pages that
already have text.

Needs the Tesseract program and its English data. If Tesseract is
missing, the catalog build still finishes and the scans stay pictures.
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    import fitz  # PyMuPDF
except ImportError:
    sys.exit("PyMuPDF not installed. Run: python -m pip install pymupdf")

# Dropped into an otherwise empty scan so the next build does not spend
# minutes reading the same picture again. Catalog builders strip it out
# of the searchable text.
SENTINEL = "OCR-BLANK"
MIN_CHARS = 40
DPI = 200

_tesseract_missing = False


def real_chars(text: str) -> int:
    cleaned = text.replace(SENTINEL, "")
    return len("".join(cleaned.split()))


def strip_sentinel(text: str) -> str:
    return text.replace(SENTINEL, "")


def page_needs_ocr(page) -> bool:
    text = page.get_text("text")
    if SENTINEL in text:
        return False
    if real_chars(text) >= MIN_CHARS:
        return False
    return bool(page.get_images(full=False))


def _embed(page) -> int:
    """Read one scanned page and lay invisible words on top of the picture."""
    tp = page.get_textpage_ocr(language="eng", dpi=DPI, full=True)
    data = page.get_text("dict", textpage=tp)
    placed = 0
    for block in data.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                word = span.get("text") or ""
                if not word.strip():
                    continue
                size = float(span.get("size") or 8)
                if size < 4 or size > 36:
                    size = 8
                x0, _y0, _x1, y1 = span["bbox"]
                if x0 < -20 or y1 < -20:
                    continue
                page.insert_text(
                    (x0, y1 - 0.4),
                    word,
                    fontsize=size,
                    fontname="helv",
                    render_mode=3,  # invisible: the picture stays, the words search
                )
                placed += 1
    if real_chars(page.get_text("text")) < MIN_CHARS:
        page.insert_text((2, 6), SENTINEL, fontsize=1, fontname="helv",
                         render_mode=3)
    return placed


def convert_pdf(path: Path) -> bool:
    """Convert scanned pages inside one PDF. Returns True if the file changed."""
    global _tesseract_missing
    if _tesseract_missing:
        return False
    doc = fitz.open(path)
    tmp = path.with_suffix(path.suffix + ".ocr-tmp")
    changed = False
    try:
        todo = [i for i in range(doc.page_count) if page_needs_ocr(doc[i])]
        if not todo:
            return False
        print(f"OCR {path.name}: {len(todo)} scanned page(s)", flush=True)
        for n, i in enumerate(todo, 1):
            if _tesseract_missing:
                break
            try:
                _embed(doc[i])
                changed = True
            except Exception as exc:
                message = str(exc).lower()
                if "tesseract" in message or "tessdata" in message:
                    _tesseract_missing = True
                    print("Tesseract is not available, so scanned pages "
                          "stay pictures.", flush=True)
                    break
                print(f"  skip {path.name} page {i + 1}: {exc}", flush=True)
            if n % 25 == 0 or n == len(todo):
                print(f"  {path.name} {n}/{len(todo)}", flush=True)
        if changed:
            doc.save(tmp, garbage=3, deflate=True)
    finally:
        doc.close()
    if changed and tmp.is_file():
        tmp.replace(path)
        return True
    tmp.unlink(missing_ok=True)
    return False


def convert_tree(folder: Path) -> int:
    """Convert every PDF in a manuals folder. Returns how many files changed."""
    if not folder.is_dir():
        return 0
    changed = 0
    for path in sorted(folder.glob("*.pdf"), key=lambda p: p.name.lower()):
        try:
            if convert_pdf(path):
                changed += 1
        except Exception as exc:
            print(f"OCR failed {path.name}: {exc}", flush=True)
    if changed:
        print(f"OCR updated {changed} file(s) in {folder}", flush=True)
    return changed


def main() -> None:
    here = Path(__file__).resolve().parents[2]
    roots = [Path(a) for a in sys.argv[1:]] or [
        here / "manuals", here / "manuals-electrical"]
    total = 0
    for root in roots:
        total += convert_tree(root)
    print(f"Done. {total} PDF(s) now have text on their scanned pages.")


if __name__ == "__main__":
    main()
