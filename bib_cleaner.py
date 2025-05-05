import re
import sys
from pathlib import Path

import bibtexparser
from decouple import config

bib_path = Path(config("BIB_PATH"))
changes = 0
unfixable = 0

# Remapping
remap = {
    "report": "techreport",
    "thesis": "phdthesis",
    "online": "misc",
    "electronic": "misc",
}

# Standard types to validate against
STANDARD_TYPES = {
    "article",
    "book",
    "inbook",
    "incollection",
    "inproceedings",
    "conference",
    "manual",
    "mastersthesis",
    "phdthesis",
    "misc",
    "proceedings",
    "techreport",
    "unpublished",
    "presentation",
}

print(f"Reading BibTeX file: {bib_path}")
with open(bib_path, encoding="utf-8") as bibfile:
    bib_db = bibtexparser.load(bibfile)

for entry in bib_db.entries:
    original_type = entry["ENTRYTYPE"].lower()

    # Apply remap if needed
    if original_type in remap:
        new_type = remap[original_type]
        if new_type != original_type:
            print(f"[{entry.get('ID')}] Changing '{original_type}' → '{new_type}'")
            entry["ENTRYTYPE"] = new_type
            changes += 1

# After remapping, check for any remaining non-standard types
for entry in bib_db.entries:
    entry_type = entry["ENTRYTYPE"].lower()
    if entry_type not in STANDARD_TYPES:
        print(f"❌ [{entry.get('ID')}] Still non-standard: {entry_type}")
        unfixable += 1

# Save if changes
if changes > 0:
    with open(bib_path, "w", encoding="utf-8") as outbib:
        bibtexparser.dump(bib_db, outbib)
    print(f"✅ Updated .bib file saved: {bib_path}")

print(f"\nSummary:")
print(f"✔ Types changed: {changes}")
print(f"❗ Remaining unfixable types: {unfixable}")

# Exit codes for Hazel:
# 0 = no changes, 1 = changes applied, 2 = unfixable types remain
if unfixable > 0:
    sys.exit(2)
elif changes > 0:
    sys.exit(1)
else:
    sys.exit(0)
