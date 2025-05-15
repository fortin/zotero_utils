import json
import os
import re
import subprocess
import sys
import uuid
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
other = config("OTHER")
linked_items_path = Path(config("LINKED_ITEMS"))
vault_name = vault_path.name

MARKDOWN_IN_DEVONTHINK = (
    config("MARKDOWN_IN_DEVONTHINK", default="False").lower() == "true"
)
PDF_IN_DEVONTHINK = config("PDF_IN_DEVONTHINK", default="True").lower() == "true"


def strip_surrogates(val):
    if isinstance(val, str):
        return val.encode("utf-8", "surrogatepass").decode("utf-8", "ignore")
    elif isinstance(val, list):
        return [strip_surrogates(x) for x in val]
    elif isinstance(val, dict):
        return {k: strip_surrogates(v) for k, v in val.items()}
    return val


# === Parse citekey ===
citekey = sys.argv[1].strip()

# === Load CSL JSON ===
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    entries = {e["id"]: e for e in data if "id" in e}

lookup = {k.lower(): k for k in entries}
if citekey.lower() not in lookup:
    print(f"❌ Citation key not found: {citekey}")
    sys.exit(1)

citekey = lookup[citekey.lower()]
entry = entries[citekey]

# === Load or initialize CSV ===
linked_df = (
    pd.read_csv(linked_items_path)
    if linked_items_path.exists()
    else pd.DataFrame(columns=["CitationKey", "Note_Link", "DEVONthink_Link"])
)

# === Determine note path ===
type_map = {
    "article-journal": articles,
    "paper-conference": articles,
    "manuscript": articles,
    "chapter": articles,
    "book": books,
    "thesis": books,
}
entry_type = entry.get("type", "").lower()
folder_name = type_map.get(entry_type, other)
note_dir = vault_path / source_material / folder_name
note_path = note_dir / f"@{citekey}.md"


# === DEVONthink search helpers ===
def find_devonthink_link(search_term):
    script = f"""
    tell application id "DNtp"
        set theRecords to search "{search_term}"
        repeat with theRecord in theRecords
            set theType to type of theRecord as string
            if theType is not "markdown" then
                return reference URL of theRecord
            end if
        end repeat
    end tell
    """
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True
        )
        output = result.stdout.strip()
        return output if output.startswith("x-devonthink-item://") else None
    except Exception as e:
        print(f"⚠️ DEVONthink search error: {e}")
        return None


# === Build DEVONthink search strings ===
title = entry.get("title", "")
authors = entry.get("author", [])
full_author = (
    " ".join([a.get("given", "") + " " + a.get("family", "") for a in authors])
    if authors
    else ""
)
fallback_term = citekey
primary_term = f"{full_author} {title}".strip()

print(f"🔍 DEVONthink primary search: {primary_term}")
devonthink_pdf_link = find_devonthink_link(primary_term)

if not devonthink_pdf_link:
    print(f"🔁 Fallback search: {fallback_term}")
    devonthink_pdf_link = find_devonthink_link(fallback_term)

# === DEVONthink note link (if markdown in DT)
devonthink_note_link = (
    find_devonthink_link(Path(note_path).name) if MARKDOWN_IN_DEVONTHINK else ""
)

# === Read/Create YAML frontmatter ===
if note_path.exists():
    content = note_path.read_text(encoding="utf-8")
    metadata = (
        yaml.safe_load(content.split("---")[1]) if content.startswith("---") else {}
    )
else:
    metadata = {}

if "uid" not in metadata:
    metadata["uid"] = str(uuid.uuid4())
    print(f"🆕 Generating new UID: {metadata['uid']}")

obsidian_adv_uri = (
    f"obsidian://adv-uri?vault={vault_name.replace(' ', '%20')}&uid={metadata['uid']}"
)

# === DEVONthink backlink injection ===
if devonthink_pdf_link:
    backlink_text = f"Linked note: {obsidian_adv_uri}"
    script = f"""
    tell application id "DNtp"
        set theRecords to lookup records with URL "{devonthink_pdf_link}"
        if theRecords ≠ {{}} then
            set comment of (item 1 of theRecords) to "{backlink_text}"
        end if
    end tell
    """
    subprocess.run(["osascript", "-e", script])
    print(f"📝 Added backlink to DEVONthink PDF.")

# === Populate metadata ===
year = entry.get("issued", {}).get("date-parts", [[None]])[0][0] or "n.d."
author_names = [
    f"{a.get('family','')}, {a.get('given','')}".strip(", ") for a in authors
]
authors_str = "; ".join(author_names)

metadata.update(
    {
        "title": title,
        "authors": authors_str,
        "citation": f"@{citekey}",
        "year": year,
        "DOI": entry.get("DOI", ""),
        "tags": ["literature", "ToRead"],
        "URI": f"zotero://select/items/@{citekey}",
        "uid": metadata["uid"],
    }
)

metadata = strip_surrogates(metadata)

# === Markdown body ===
pdf_backlink_md = (
    f"[View PDF in DEVONthink]({devonthink_pdf_link})"
    if devonthink_pdf_link
    else "PDF not linked yet"
)
note_link = (
    f"[Open Note in DEVONthink]({devonthink_note_link})"
    if devonthink_note_link
    else f"[Open in Zotero]({metadata['URI']})"
)

note_body = f"""---
{yaml.dump(metadata, sort_keys=False).strip()}
---
📌 {note_link}
📄 {pdf_backlink_md}
<!-- OMNIFOCUS_LINK_PLACEHOLDER -->

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
note_path.write_text(note_body, encoding="utf-8")
print(f"✅ Note created: {note_path}")

# === Final URIs ===
note_uri = obsidian_adv_uri
pdf_uri = devonthink_pdf_link or ""
zotero_uri = metadata["URI"]

# === Update linked_items.csv ===
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

linked_df.to_csv(linked_items_path, index=False)
print("🔄 linked_items.csv updated.")

# === Hookmark linking ===
hook = config("HOOK_PATH")
note_path_uri = f"hook://file/{note_path.resolve()}"
abs_note_path = note_path.resolve()

if pdf_uri:
    subprocess.run([hook, "link", note_uri, pdf_uri])
    subprocess.run([hook, "link", pdf_uri, zotero_uri])
    subprocess.run([hook, "link", note_uri, zotero_uri])

# === Final output
print(f"🔗 Hooked: {note_uri} ⇔ {pdf_uri} ⇔ {zotero_uri}")
print(f"TITLE_FOR_OMNIFOCUS::{title}")
print(f"AUTHOR_FOR_OMNIFOCUS::{authors_str}")
print(f"NOTE_PATH::{abs_note_path}")
print(f"NOTE_URI::hook://file/{abs_note_path}")
print(f"OBSIDIAN_URI::{obsidian_adv_uri}")
print(f"PDF_URI::{pdf_uri}")
print(f"ZOTERO_URI::{zotero_uri}")
