import argparse
import csv
import re
from pathlib import Path

import pandas as pd
from decouple import config
from pyzotero import zotero

# ----------------- CONFIGURATION -----------------
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
LIBRARY_TYPE = "user"

PDF_FOLDER = Path(config("PDF_FOLDER"))

# ----------------- ARGPARSE -----------------
parser = argparse.ArgumentParser(
    description="Clean broken Zotero attachments and relink PDFs by citation key."
)
parser.add_argument(
    "--dry-run", action="store_true", help="Run without making any changes."
)
args = parser.parse_args()

# ----------------- CONNECT -----------------
zot = zotero.Zotero(ZOTERO_USER_ID, LIBRARY_TYPE, ZOTERO_API_KEY)

# ----------------- LOAD PDF FILENAMES -----------------
with open("pdfs.txt", "r", encoding="utf-8") as f:
    raw_pdf_lines = [line.strip() for line in f if line.strip()]

# Clean filenames (remove tree symbols and whitespace)
cleaned_pdf_filenames = set()
for line in raw_pdf_lines:
    name = Path(line).name
    name = re.sub(r"^[^a-zA-Z0-9]*", "", name).strip()
    cleaned_pdf_filenames.add(name)

# ----------------- LOAD ZOTERO MAPPING -----------------
zotero_csv = pd.read_csv("zoterojs.txt")
zotero_mapping = zotero_csv.set_index("key")["citationKey"].to_dict()

# ----------------- STEP 1: FIND BROKEN ATTACHMENTS -----------------
try:
    # Use existing CSV if available
    broken = pd.read_csv("cache/broken_attachments.csv")
    print("Loaded broken_attachments.csv from disk.")
except FileNotFoundError:
    print(
        "broken_attachments.csv not found. Querying Zotero live for broken attachments..."
    )

    items = zot.everything(zot.items())
    broken_data = []

    for item in items:
        data = item["data"]
        if data["itemType"] != "attachment":
            continue

        parent = data.get("parentItem")
        path = data.get("path")
        key = item["key"]

        broken = False
        if path:
            if path.startswith("storage:"):
                storage_path = (
                    Path.home() / "Zotero" / path.replace("storage:", "storage/")
                )
                if not storage_path.exists():
                    broken = True
            elif path.startswith("file:"):
                file_path = Path(path.replace("file://", ""))
                if not file_path.exists():
                    broken = True
            else:
                broken = True
        else:
            broken = True

        if broken:
            broken_data.append(
                {
                    "attachment_key": key,
                    "title": data.get("title"),
                    "parentItem": parent,
                    "path": path,
                }
            )

    broken = pd.DataFrame(broken_data)
    broken.to_csv("cache/broken_attachments.csv", index=False)
    print(f"Found {len(broken)} broken attachments. Saved to broken_attachments.csv.")

# ----------------- STEP 2: FIND MATCHES -----------------
matches = []

for _, row in broken.iterrows():
    parent = row["parentItem"]
    citation_key = zotero_mapping.get(parent)

    if pd.isna(citation_key) or not citation_key:
        continue

    expected_pdf = f"{citation_key}.pdf"

    if expected_pdf in cleaned_pdf_filenames:
        matches.append(
            {
                "item_key": parent,
                "citation_key": citation_key,
                "title": row["title"],
                "pdf_filename": expected_pdf,
            }
        )

df_matches = pd.DataFrame(matches)
df_matches.to_csv("cache/new_attachments.csv", index=False)

# ----------------- SUMMARY -----------------
print("\nSUMMARY")
print("-------")
print(f"Broken attachments found: {len(broken)}")
print(f"Items with matching PDFs: {len(df_matches)}")
print("Dry run mode:", args.dry_run)
print("Logs saved: broken_attachments.csv and new_attachments.csv")
print()

# ----------------- DELETE BROKEN ATTACHMENTS -----------------
if args.dry_run:
    print(f"[Dry Run] Would delete {len(broken)} broken attachments.")
# else:
#     for att_key in broken["attachment_key"]:
#         zot.delete_item(
#             {"key": att_key}
#         )  # Will still require version to actually work!
#     print(f"Deleted {len(broken)} broken attachments.")

# ----------------- ADD NEW ATTACHMENTS -----------------
if args.dry_run:
    print(f"[Dry Run] Would attach {len(df_matches)} PDFs.")
else:
    for _, row in df_matches.iterrows():
        full_pdf_path = PDF_FOLDER / row["pdf_filename"]
        zot.attachment_simple(
            [str(full_pdf_path)], row["item_key"], title=row["pdf_filename"]
        )
    print(f"Added {len(df_matches)} new linked-file attachments.")

# ----------------- FINAL REPORT -----------------
print("\nProcess complete.")
print(
    f"Broken attachments {'would be' if args.dry_run else 'were'} removed: {len(broken)}"
)
print(
    f"New attachments {'would be' if args.dry_run else 'were'} added: {len(df_matches)}"
)
