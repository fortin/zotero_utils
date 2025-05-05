import os
import re
import subprocess
import sys
import uuid
from datetime import datetime
from pathlib import Path

import bibtexparser
import pandas as pd
import yaml
from decouple import config

# === Load environment config ===
bib_path = Path(config("BIB_PATH"))
vault_path = Path(config("OBSIDIAN_VAULT"))
linked_items_path = Path(os.environ.get("LINKED_ITEMS"))
python_path = Path(os.environ.get("PYTHON_PATH"))

# === RUN PRE-SCRIPT IF CONFIGURED ===
SCRIPT_PATH = config("SCRIPT_PATH", default=None)
if SCRIPT_PATH:
    print("Standardising item types...")
    os.system(f"{python_path} '{SCRIPT_PATH}'")

# === Parse citekey from Alfred Script Filter ===
citekey = sys.argv[1].strip()

# === Load .bib file ===
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)
    entries = {e["ID"]: e for e in bib_db.entries}

if citekey not in entries:
    print(f"❌ Citation key not found: {citekey}")
    sys.exit(1)

entry = entries[citekey]

# === Load or initialise linked_items.csv ===
if linked_items_path.exists():
    linked_df = pd.read_csv(linked_items_path)
else:
    linked_df = pd.DataFrame(columns=["CitationKey", "Note_Link", "DEVONthink_Link"])

# === Determine note path ===
bib_type = entry.get("ENTRYTYPE", "").lower()
if bib_type in {
    "article",
    "conference",
    "inbook",
    "incollection",
    "inproceedings",
    "manuscript",
}:
    note_dir = (
        vault_path
        / "📁 500 📒 Notes/📁 520 🗒 Zettelkasten/522 📚 Source Material/532 📄 Articles"
    )
elif bib_type in {"book", "booklet", "masterthesis", "phdthesis", "proceedings"}:
    note_dir = (
        vault_path
        / "📁 500 📒 Notes/📁 520 🗒 Zettelkasten/522 📚 Source Material/542 📖 Books"
    )
else:
    note_dir = (
        vault_path
        / "📁 500 📒 Notes/📁 520 🗒 Zettelkasten/522 📚 Source Material/572 ⺟ Other"
    )

note_path = note_dir / f"@{citekey}.md"


# === DEVONthink link discovery ===
def find_devonthink_link(search_string):
    script = f"""
    tell application id "DNtp"
        set theRecords to search "{search_string}"
        if theRecords is not {{}} then
            return reference URL of (item 1 of theRecords)
        end if
    end tell
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True
        )
        link = result.stdout.strip()
        return link if link.startswith("x-devonthink-item://") else None
    except Exception:
        return None


filename = ""
if "file" in entry:
    m = re.search(r"([^:]+\.pdf)", entry["file"], re.IGNORECASE)
    if m:
        filename = m.group(1)

if filename:
    search_term = Path(filename).stem
    search_term = re.sub(r"[_\-=:.]+", " ", search_term).strip()
    search_term = re.sub(r"\s+", " ", search_term).strip()
    print(f"🔍 DEVONthink search term (filename): {search_term}")
else:
    authors = entry.get("author", "")
    title = entry.get("title", "")
    search_term = f"{authors} {title}".strip()
    search_term = re.sub(r"[_\-:=]+", " ", search_term)
    print(f"🔍 DEVONthink search term (author/title): {search_term}")

devonthink_link = find_devonthink_link(search_term) or ""

if devonthink_link:
    print(f"✅ Found DEVONthink link: {devonthink_link}")
else:
    print("⚠ DEVONthink link not found.")

# === Read or create YAML frontmatter ===
if note_path.exists():
    with open(note_path, "r", encoding="utf-8") as f:
        content = f.read()
    if content.startswith("---"):
        parts = content.split("---")
        metadata = yaml.safe_load(parts[1])
    else:
        metadata = {}
else:
    metadata = {}

if "uid" not in metadata:
    metadata["uid"] = str(uuid.uuid4())
    print(f"🆕 Generating new UID: {metadata['uid']}")

# === Year handling (proper fallback to 'date' field if needed) ===
year = entry.get("year", "").strip()
if not year:
    date_field = entry.get("date", "").strip()
    year_match = re.search(r"\d{4}", date_field)
    year = year_match.group(0) if year_match else "n.d."

# === Update metadata ===
metadata.update(
    {
        "title": f"@{citekey}",
        "authors": entry.get("author", ""),
        "citation": f"@{citekey}",
        "year": year,
        "DOI": entry.get("doi", ""),
        "tags": ["literature", "ToRead"],
        "URI": f"zotero://select/items/@{citekey}",
        "uid": metadata["uid"],
    }
)

note_body = f"""---
{yaml.dump(metadata, sort_keys=False).strip()}
---

📎 [Open in Zotero]({metadata['URI']})

📄 {"[Open PDF in DEVONthink](" + devonthink_link + ")" if devonthink_link else "PDF not linked yet"}

## Summary
-

## Key Points
-

## Quotes & Highlights
> “”

## My Thoughts
-

## Related Notes
-
"""

note_path.parent.mkdir(parents=True, exist_ok=True)
with open(note_path, "w", encoding="utf-8") as f:
    f.write(note_body)

print(f"✅ Note created/updated: {note_path}")

# === Update linked_items.csv for this citekey ===
note_uri = f"hook://file/{note_path.resolve()}"

if citekey in linked_df["CitationKey"].values:
    linked_df.loc[linked_df["CitationKey"] == citekey, "Note_Link"] = note_uri
    linked_df.loc[linked_df["CitationKey"] == citekey, "DEVONthink_Link"] = (
        devonthink_link
    )
else:
    linked_df = pd.concat(
        [
            linked_df,
            pd.DataFrame(
                [
                    {
                        "CitationKey": citekey,
                        "Note_Link": note_uri,
                        "DEVONthink_Link": devonthink_link,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

# === NEW: Ensure all BibTeX citekeys are in the cache, even if no note/link ===
for other_key in entries:
    if other_key not in linked_df["CitationKey"].values:
        linked_df = pd.concat(
            [
                linked_df,
                pd.DataFrame(
                    [{"CitationKey": other_key, "Note_Link": "", "DEVONthink_Link": ""}]
                ),
            ],
            ignore_index=True,
        )

linked_df.to_csv(linked_items_path, index=False)
print("🔄 linked_items.csv updated.")

# === Hookmark linking ===
hook = "/usr/local/bin/hook"
args = [hook, "link", note_uri]

if devonthink_link:
    args.append(devonthink_link)

args.append(metadata["URI"])

subprocess.run(args)

print(f"🔗 Hooked: {note_uri} ⇄ {devonthink_link} ⇄ {metadata['URI']}")
