# Handoff: the 1991 3S-GTE book now has real words

The user does not want the early 3S-GE workshop manual. They care about 3S-GTE, 5S-FE, and the other manuals already in the app.

The GitHub repo is public. The 1991 3S-GTE repair manual was read from that public file. Its scan pictures are unchanged. The hidden words on that PDF are real steps and specs now. Do not read that book again. Do not ask the user to upload a copy.

## Do this

- Keep `manuals/3SGE-workshop-manual-early.pdf` out of the library. It was removed on this branch. Do not put it back.
- Leave `manuals/Toyota - 3S-GTE - 1991 - Repair Manual (RM266E).pdf` as it is. A rebuild skips pages that already have words, so the new text stays.
- Leave the smaller 3S-GTE and 5S-FE scans, and the electrical scans, on their current rough text unless the user asks for those too.
- Do not use a live Extend workspace. The test reads for this book are already paid for and already on the PDF.

## Where the work lives

- Branch: `cursor/garage-search-and-scans-ad65`
- Draft pull request: https://github.com/living-relation/st185-celica-repair-manual/pull/3
- Do not merge. Do not open a second branch.

## Still true

- A filename that is only a 3S-GE book still gets edition `3sge` in `celica-manual/build/build.py`, so its page codes cannot land on the 1993 shelf.
- The 1991 book is edition `1991`, so its page codes stay off that shelf too.
- After a rebuild, `CH-7` must still point at `Generator` page 2.
- Blank and memo pages in the 1991 book stay short on purpose. Page 144 is only the Toyota Quality Service mark.
