# Handoff: the 3S-GE manual is out

The user does not want the early 3S-GE workshop manual. They care about 3S-GTE, 5S-FE, and the other manuals already in the app.

## Do this

- Keep `manuals/3SGE-workshop-manual-early.pdf` out of the library. It was removed on this branch. Do not put it back.
- Leave the 1991 3S-GTE repair manual (`Toyota - 3S-GTE - 1991 - Repair Manual (RM266E).pdf`) and the 5S-FE sections that are already here.
- Do not ask the user to drop files into Extend. Those manuals are already in the repo, and Extend cannot read this private repo on its own.

## Where the work lives

- Branch: `cursor/garage-search-and-scans-ad65`
- Draft pull request: https://github.com/living-relation/st185-celica-repair-manual/pull/3
- Do not merge. Do not open a second branch.

## Still true after the book is gone

- A filename that is only a 3S-GE book still gets edition `3sge` in `celica-manual/build/build.py`, so its page codes cannot land on the 1993 shelf. After a rebuild, `CH-7` must still point at `Generator`.
- Search text comes from the words already stored on each PDF. Rebuilds skip pages that already have words.
