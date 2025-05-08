import os
import re
import subprocess
import sys
import uuid
import json
from pathlib import Path

import pandas as pd
import yaml
from decouple import config

# === Load environment config ===
json_path = Path(config("CSL_JSON_PATH"))
vault_path = Path(config("OBSIDIAN_VAULT"))
source_material = config("SOURCE_MATERIAL")
articles = config("ARTICLES")
books = config("BOOKS")
linked_items_path = Path(os.environ.get("LINKED_ITEMS"))
python_path = Path(os.environ.get("PYTHON_PATH"))

MARKDOWN_IN_DEVONTHINK = (
    config("MARKDOWN_IN_DEVONTHINK", default="False").lower() == "true"
)
PDF_IN_DEVONTHINK = config("PDF_IN_DEVONTHINK", default="True").lower() == "true"

# === Parse citekey from Alfred Script Filter ===
citekey = sys.argv[1].strip()

# === Load CSL JSON ===
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    entries = {e["id"]: e for e in data if "id" in e}

# === Case-insensitive key match ===
lookup = {k.lower(): k for k in entries.keys()}
if citekey.lower() not in lookup:
    print(f"❌ Citation key not found: {citekey}")
    sys.exit(1)

true_key = lookup[citekey.lower()]
entry = entries[true_key]
citekey = true_key

# === Load or initialise linked_items.csv ===
if linked_items_path.exists():
    linked_df = pd.read_csv(linked_items_path)
else:
    linked_df = pd.DataFrame(columns=["CitationKey", "Note_Link", "DEVONthink_Link"])

# === Determine note path ===
type_map = {
    "article-journal": articles,
    "paper-conference": articles,
    "chapter": articles,
    "book": books,
    "thesis": books,
}
entry_type = entry.get("type", "").lower()
folder_name = type_map.get(entry_type, "572 ⺟ Other")

note_dir = vault_path / source_material / folder_name
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


# === Build search string ===
filename = entry.get("note", "")
filename_match = (
    re.search(r"([^/]+\.(pdf|epub))", filename, re.IGNORECASE) if filename else None
)

if filename_match:
    search_term = Path(filename_match.group(1)).stem
    search_term = re.sub(r"[_\-=:.]+", " ", search_term).strip()
else:
    authors = entry.get("author", "")
    if isinstance(authors, list):
        authors = " ".join([a.get("family", "") for a in authors])
    title = entry.get("title", "")
    search_term = f"{authors} {title}".strip()

search_term = re.sub(r"\s+", " ", search_term)
print(f"🔍 DEVONthink search term: {search_term}")

# === DEVONthink or filesystem links ===
devonthink_note_link = (
    find_devonthink_link(Path(note_path).name) if MARKDOWN_IN_DEVONTHINK else ""
)
if devonthink_note_link:
    print(f"✅ Found DEVONthink note link.")
else:
    if MARKDOWN_IN_DEVONTHINK:
        print("⚠ Note not indexed in DEVONthink, falling back to Obsidian link.")
    devonthink_note_link = ""

# PDF search
devonthink_pdf_link = find_devonthink_link(search_term) if PDF_IN_DEVONTHINK else ""
if devonthink_pdf_link:
    print(f"✅ Found DEVONthink PDF link.")
else:
    if PDF_IN_DEVONTHINK:
        print("⚠ PDF not found in DEVONthink. Falling back to Finder link or none.")
    devonthink_pdf_link = ""

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

# === Year handling ===
year = entry.get("issued", {}).get("date-parts", [[None]])[0][0] or "n.d."

# === Authors ===
if "author" in entry:
    author_names = []
    for author in entry["author"]:
        family = author.get("family", "")
        given = author.get("given", "")
        author_names.append(f"{family}, {given}".strip(", "))
    authors = "; ".join(author_names)
else:
    authors = ""

# === DOI ===
doi = entry.get("DOI", "")

# === Update metadata ===
metadata.update(
    {
        "title": entry.get("title", citekey),
        "authors": authors,
        "citation": f"@{citekey}",
        "year": year,
        "DOI": doi,
        "tags": ["literature", "ToRead"],
        "URI": f"zotero://select/items/@{citekey}",
        "uid": metadata["uid"],
    }
)

# === Preferred Note Link ===
if MARKDOWN_IN_DEVONTHINK and devonthink_note_link:
    note_link_display = f"[Open Note in DEVONthink]({devonthink_note_link})"
else:
    note_link_display = f"[Open in Obsidian]({metadata['URI']})"

# === Preferred PDF Link ===
if PDF_IN_DEVONTHINK and devonthink_pdf_link:
    pdf_link_display = f"[Open PDF in DEVONthink]({devonthink_pdf_link})"
else:
    pdf_link_display = "PDF not linked yet"

note_body = f"""---
{yaml.dump(metadata, sort_keys=False).strip()}
---

📎 {note_link_display}

📄 {pdf_link_display}

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
note_uri = (
    devonthink_note_link
    if devonthink_note_link
    else f"hook://file/{note_path.resolve()}"
)
pdf_uri = devonthink_pdf_link if devonthink_pdf_link else ""

if citekey in linked_df["CitationKey"].values:
    linked_df.loc[linked_df["CitationKey"] == citekey, "Note_Link"] = note_uri
    linked_df.loc[linked_df["CitationKey"] == citekey, "DEVONthink_Link"] = pdf_uri
else:
    linked_df = pd.concat(
        [
            linked_df,
            pd.DataFrame(
                [
                    {
                        "CitationKey": citekey,
                        "Note_Link": note_uri,
                        "DEVONthink_Link": pdf_uri,
                    }
                ]
            ),
        ],
        ignore_index=True,
    )

# === Ensure all CSL JSON citekeys are in the cache ===
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

if pdf_uri:
    args.append(pdf_uri)

args.append(metadata["URI"])

subprocess.run(args)

print(f"🔗 Hooked: {note_uri} ⇄ {pdf_uri} ⇄ {metadata['URI']}")
print(f"TITLE_FOR_OMNIFOCUS::{entry.get('title', citekey)}")
print(f"AUTHOR_FOR_OMNIFOCUS::{authors}")
print(f"NOTE_URI::{note_uri}")
print(f"PDF_URI::{pdf_uri}")
print(f"ZOTERO_URI::{metadata['URI']}")
