#!/Users/antonio/micromamba/envs/zotero/bin/python3

import sys
from bibtexparser import loads
from decouple import config

STANDARD_TYPES = {
    "article", "book", "incollection", "inproceedings",
    "manual", "misc", "unpublished", "conference",
    "phdthesis", "mastersthesis", "techreport"
}

with open(config("BIB_PATH"), "r", encoding="utf-8") as f:
    bib_db = loads(f.read())

nonstandard = set()
for entry in bib_db.entries:
    typ = entry["ENTRYTYPE"].lower()
    if typ not in STANDARD_TYPES:
        nonstandard.add(typ)

if nonstandard:
    print("⚠ Non-standard types found:", ", ".join(nonstandard))
    sys.exit(1)
else:
    print("✅ All entry types are standard.")
    sys.exit(0)