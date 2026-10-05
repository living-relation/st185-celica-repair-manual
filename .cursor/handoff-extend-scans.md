# Handoff: read two scanned manuals with Extend

Another agent should finish this. Do not merge the pull request. Stay on this branch.

## The two jobs

1. Read `manuals/3SGE-workshop-manual-early.pdf` with Extend and replace the rough hidden text with the words Extend returns.
2. Do the same for `manuals/Toyota - 3S-GTE - 1991 - Repair Manual (RM266E).pdf`.

Both books are picture scans. A first pass already stored hidden words with Tesseract. Those words are good enough to search, but they are broken up, stuck together, and missing pieces of tables. Extend should turn each page into normal sentences and tables. The pictures stay. Search and the PDF viewer should then work like the manuals that were never scans.

## Where the work lives

- Branch: `cursor/garage-search-and-scans-ad65`
- Draft pull request: https://github.com/living-relation/st185-celica-repair-manual/pull/3
- Base branch: `main`
- Commit and push on this same branch. Do not open a second branch.
- Talk to the user in short, plain sentences.

## The books

| Book | Path | Pages | Size | Pages that are still almost empty |
| --- | --- | --- | --- | --- |
| Early 3S-GE workshop manual | `manuals/3SGE-workshop-manual-early.pdf` | 495 | 32 MB | 4 |
| 1991 3S-GTE repair manual (RM266E) | `manuals/Toyota - 3S-GTE - 1991 - Repair Manual (RM266E).pdf` | 144 | 14 MB | 14 |

Checked on 2026-10-05. "Almost empty" means fewer than 40 real characters after removing the `OCR-BLANK` marker. Those pages were marked so the next Tesseract run skips them.

The other 24 PDFs that got a Tesseract pass are out of scope unless the user asks. Do not send the whole library to Extend.

## What is already true

- `celica-manual/build/ocr_pages.py` reads a page with Tesseract when it has a picture and fewer than 40 real characters. It stores the words invisibly (`render_mode=3`). Empty pages get the marker `OCR-BLANK`.
- `celica-manual/build/build.py` calls `ocr_pages.convert_tree` first, then strips `OCR-BLANK` before search text is saved. It adds `===== PAGE n of N =====` itself. Do not put those banners inside the PDF.
- A filename that is only a 3S-GE book gets edition `3sge` (`build.py`, around the `edition = "3sge"` check). That keeps its page codes off the main 1993 index. After any rebuild, code `CH-7` must still point at `Generator`, not at the 3S-GE book.
- The catalog and the PDF viewer both read the text layer. Replacing that layer is what makes search and in-PDF find use the new words.
- Because these pages already have words, `page_needs_ocr` will skip them. A new run must replace the old hidden text on purpose. Do not expect `convert_pdf` to do that.

## Extend access

- Call `get_me` first. If a call returns unauthorized or not found, call `get_me` again.
- Workspace: `ws_JUPllPMvQuLwEHE9IWeAk` (Spark Robotic).
- Environment: `TEST` only. This connection cannot use production.
- Account: `research@sparkrobotic.com`.
- On 2026-10-05 the test workspace had no files. These upload links were never used and are expired: `upl_xf2vdoxkTkoYnqPQsEoiv`, `upl_a8p7vDSYpPMUcj6lREjQt`.
- The repo is private. A GitHub file URL will not work as a public `https://` file for Extend.
- `upload_file` only makes a dashboard link. The user must open it, sign in, drop the PDFs, and click Done. The link dies in about 15 minutes. A direct upload with only the link token returns 401. Make a new link if the old one expires, then wait with `get_file_upload` (`wait: true`) using the new `uploadId`.
- Parse with `parse_document`. If the status is `running`, resume with `get_parse_run` and `wait: true`. Use the same workspace and environment. Do not submit the file again.

## Read three pages before the whole books

The careful parser (`parse_performance`) costs about 2 credits a page. These two books are 639 pages, so the full job is on the order of 1,300 credits before extras. Read a sample first.

Use `config.advancedOptions.pageRanges` so only those pages are billed. The `pageRange` argument on the tool only cuts the reply after the whole file has been read and billed. Do not use that argument alone on these books.

Suggested sample from the 3S-GE book:

- Page 6. Intro text. The current words are split and noisy.
- Page 151. Spec table for the cylinder block main journal. This is the before-and-after check.
- Page 471. A short equipment list. The current text is only a few words.

Parse config for that sample:

```json
{
  "engine": "parse_performance",
  "chunkingStrategy": { "type": "page" },
  "blockOptions": {
    "tables": { "targetFormat": "markdown" }
  },
  "advancedOptions": {
    "pageRanges": [
      { "start": 6, "end": 6 },
      { "start": 151, "end": 151 },
      { "start": 471, "end": 471 }
    ]
  }
}
```

For one extra sample page, turn on `blockOptions.text.agentic.enabled`. That asks a vision model to fix weak words. It can add about 1 credit for each page where it runs. If the plain parse is already clean, leave it off for the full books.

Turn on figure reading for one diagram page only if the plain text misses words that exist only inside a drawing. Do not turn on figure image clipping. The pictures must stay in the PDF.

Show the user a short before-and-after for those pages. Do not paste long stretches of the manual. If the new text is not clearly better, stop and say so. Do not spend the full-book credits.

## If the sample is better

1. Tell the user you are about to read the rest of these two books, and the rough credit size.
2. Parse each book with `advancedOptions.pageRanges` in chunks (for example 40 pages at a time) so a failure does not re-bill finished pages. `chunkingStrategy.type` of `page` keeps the text tied to a page number.
3. On each page, remove the old hidden text and keep the picture. In PyMuPDF, redact the text and call `apply_redactions` with images kept (`images=0` / image none). Then insert the new words invisibly (`render_mode=3`), in reading order, as plain lines. Drop markdown marks such as `#` and table pipes so search does not look for them. Keep the numbers and the labels.
4. Do not change page count or page order. Save through a temp file, then replace the PDF, the same way `ocr_pages.py` uses `*.ocr-tmp`.
5. Rebuild and check:
   - `python3 celica-manual/build/build.py`
   - `python3 electrical/build/build_ewd.py`
   - `python3 celica-manual/build/validate.py`
   - `python3 electrical/build/validate_ewd.py`
6. Confirm `CH-7` still resolves to `Generator`. Confirm the 3S-GE book still has edition `3sge` and is not `image_only`.
7. Commit the PDFs, the regenerated catalogs, and any small code change on this branch. Push. Update the draft pull request. Leave it a draft.

## Do not

- Do not merge.
- Do not start a second feature branch.
- Do not parse every PDF in `manuals/` or `manuals-electrical/`.
- Do not put the manuals on a public file host.
- Do not use the production Extend environment.
- Do not let a rebuild send page codes from the 3S-GE book into the main 1993 index.
