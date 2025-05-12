import argparse
import json
import os
import re
import subprocess
from pathlib import Path

import pandas as pd
from decouple import config

# === CONFIGURATION ===
base_dir = Path(config("BASE_DIR"))
json_path = Path(config("CSL_JSON_PATH"))
log_path = base_dir / "logs/hook_link_log.csv"
debug_path = base_dir / "logs/hook_link_debug.txt"
cache_path = Path(config("LINKED_ITEMS"))
hook_path = config("HOOK_PATH")
python_path = Path(config("PYTHON_PATH"))
vault_path = Path(config("OBSIDIAN_VAULT"))

MARKDOWN_IN_DEVONTHINK = (
    config("MARKDOWN_IN_DEVONTHINK", default="False").lower() == "true"
)
PDF_IN_DEVONTHINK = config("PDF_IN_DEVONTHINK", default="False").lower() == "true"

# === ARGPARSE ===
parser = argparse.ArgumentParser(
    description="Hook Zotero, Obsidian, and DEVONthink PDFs via Hookmark incrementally."
)
parser.add_argument(
    "--dry-run", action="store_true", help="Run without making any changes."
)
parser.add_argument("--citekey", type=str, help="Only process this citation key.")
args = parser.parse_args()


def safe_hook_link(a, b):
    if args.dry_run:
        print(f"[Dry Run] Would link: {a} ⇄ {b}")
    else:
        subprocess.run([hook_path, "link", a, b])
        print(f"🔗 Hooked: {a} ⇄ {b}")


def refresh_cache(citekey):
    subprocess.run(
        [python_path, "create_lit_note.py", citekey],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def find_devonthink_doc_link(entry, citekey):
    authors = entry.get("author", [])
    full_author = " ".join(
        f"{a.get('given','')} {a.get('family','')}".strip()
        for a in authors
        if isinstance(a, dict)
    ).strip()
    title = entry.get("title", "")
    search_1 = f"{full_author} {title}".strip()
    search_1 = re.sub(r"\s+", " ", search_1)

    script_template = """
    tell application id "DNtp"
        set theRecords to search "{query}"
        repeat with theRecord in theRecords
            set theName to name of theRecord
            set theType to type of theRecord
            if theType is not "markdown" then
                return reference URL of theRecord
            end if
        end repeat
    end tell
    """

    # First search: Full author name + title
    result_1 = subprocess.run(
        ["osascript", "-e", script_template.replace("{query}", search_1)],
        capture_output=True,
        text=True,
    )
    out1 = result_1.stdout.strip()
    if out1.startswith("x-devonthink-item://"):
        return out1

    # Fallback: citekey
    fallback_query = citekey
    result_2 = subprocess.run(
        ["osascript", "-e", script_template.replace("{query}", fallback_query)],
        capture_output=True,
        text=True,
    )
    out2 = result_2.stdout.strip()
    return out2 if out2.startswith("x-devonthink-item://") else None


# === PREPARE DEBUG LOG ===
with open(debug_path, "w", encoding="utf-8") as dbg:
    dbg.write("🔍 Hook Linking Debug Log\n\n")

# === LOAD CACHE ===
if cache_path.exists():
    linked_df = pd.read_csv(cache_path)
else:
    linked_df = pd.DataFrame(columns=["CitationKey", "Note_Link", "DEVONthink_Link"])

# === LOAD CSL JSON ===
with open(json_path, "r", encoding="utf-8") as f:
    data = json.load(f)
    entries = {e["id"]: e for e in data if "id" in e}

lookup = {k.lower(): k for k in entries.keys()}

if args.citekey:
    key_lc = args.citekey.lower()
    if key_lc not in lookup:
        print(f"❌ Citation key {args.citekey} not found in CSL JSON.")
        exit(1)
    citekeys = [lookup[key_lc]]
else:
    citekeys = list(entries.keys())

linked, skipped = [], []

# === PROCESS EACH CITEKEY ===
for key in citekeys:
    row = linked_df.loc[linked_df["CitationKey"] == key]

    if (
        row.empty
        or pd.isna(row.iloc[0]["Note_Link"])
        or pd.isna(row.iloc[0]["DEVONthink_Link"])
    ):
        refresh_cache(key)
        linked_df = pd.read_csv(cache_path)
        row = linked_df.loc[linked_df["CitationKey"] == key]

    note_uri = row.iloc[0]["Note_Link"] if not row.empty else ""
    devonthink_link = row.iloc[0]["DEVONthink_Link"] if not row.empty else ""
    zot_uri = f"zotero://select/items/@{key}"

    # Apply MARKDOWN_IN_DEVONTHINK setting
    if MARKDOWN_IN_DEVONTHINK and pd.notna(note_uri):
        md_filename = note_uri.replace("hook://file/", "")
        md_path = Path(md_filename)
        dt_md_link = devonthink_link_for_path(md_path)
        if dt_md_link:
            note_uri = dt_md_link

    # Improved PDF matching
    pdf_link = ""
    entry = entries[key]
    if PDF_IN_DEVONTHINK:
        dt_pdf_link = find_devonthink_doc_link(entry, key)
        if dt_pdf_link:
            pdf_link = dt_pdf_link

    with open(debug_path, "a", encoding="utf-8") as dbg:
        dbg.write(f"== {key} ==\n")
        dbg.write(f"Note URI: {note_uri if pd.notna(note_uri) else '---'}\n")
        dbg.write(
            f"DEVONthink link: {devonthink_link if pd.notna(devonthink_link) else '---'}\n"
        )

    if pd.notna(note_uri) and pd.notna(devonthink_link):
        safe_hook_link(note_uri, devonthink_link)
        safe_hook_link(note_uri, zot_uri)
        safe_hook_link(devonthink_link, zot_uri)
        linked.append((key, note_uri, devonthink_link, "linked"))
        with open(debug_path, "a", encoding="utf-8") as dbg:
            dbg.write("✅ Linked all three.\n\n")
    else:
        skipped.append(
            (
                key,
                note_uri if pd.notna(note_uri) else "",
                devonthink_link if pd.notna(devonthink_link) else "",
                "missing note or DEVONthink link",
            )
        )
        with open(debug_path, "a", encoding="utf-8") as dbg:
            dbg.write("❌ Skipped due to missing note or DEVONthink link.\n\n")

# === SAVE CSV LOG ===
df = pd.DataFrame(
    linked + skipped, columns=["CitationKey", "Note_Link", "DEVONthink_Link", "Status"]
)
df.to_csv(log_path, index=False)

with open(debug_path, "a", encoding="utf-8") as dbg:
    dbg.write(f"\n✅ Linked this run: {len(linked)}\n")
    dbg.write(f"⏭ Skipped (missing data): {len(skipped)}\n")
    dbg.write(f"📄 CSV Log: {log_path}\n")

print(f"✅ Done. {len(linked)} linked, {len(skipped)} skipped.")
