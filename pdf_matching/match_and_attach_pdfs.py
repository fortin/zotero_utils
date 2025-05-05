import argparse
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
    description="Link PDFs to Zotero items using the 'file' entry in the extra field."
)
parser.add_argument(
    "--dry-run", action="store_true", help="Run without making any changes."
)
args = parser.parse_args()

# ----------------- CONNECT -----------------
zot = zotero.Zotero(ZOTERO_USER_ID, LIBRARY_TYPE, ZOTERO_API_KEY)

# ----------------- FETCH ITEMS -----------------
print("Fetching items from Zotero...")
items = zot.everything(zot.items())

attached = []
skipped = []
missing = []

# ----------------- PROCESS ITEMS -----------------
for item in items:
    data = item["data"]

    # Skip attachments themselves
    if data["itemType"] == "attachment":
        continue

    key = item["key"]
    title = data.get("title", "Untitled")

    # Look for 'file' entry in extra field
    extra = data.get("extra", "")
    match = re.search(r"file\s*[:=]\s*([^:/\\\|]+\.pdf)", extra, re.I)

    if not match:
        missing.append({"key": key, "title": title, "reason": "No file entry in extra"})
        continue

    filename = match.group(1).strip()

    # Check if file exists in PDF_FOLDER
    pdf_path = PDF_FOLDER / filename
    if not pdf_path.exists():
        missing.append(
            {
                "key": key,
                "title": title,
                "filename": filename,
                "reason": "File not found",
            }
        )
        continue

    # Check for existing linked attachments
    has_linked = False
    for child in zot.children(item["key"]):
        c_data = child["data"]
        if (
            c_data["itemType"] == "attachment"
            and c_data.get("linkMode") == "linked_file"
        ):
            has_linked = True
            break

    if has_linked:
        skipped.append(
            {
                "key": key,
                "title": title,
                "filename": filename,
                "reason": "Linked attachment already exists",
            }
        )
        continue

    # Dry-run or attach
    if args.dry_run:
        attached.append(
            {"key": key, "title": title, "filename": filename, "action": "Would attach"}
        )
        print(f"[Dry Run] Would attach: {filename} to {title}")
    else:
        try:
            zot.attachment_simple([str(pdf_path)], parentid=item["key"], title=filename)
            attached.append(
                {"key": key, "title": title, "filename": filename, "action": "Attached"}
            )
            print(f"✔ Attached: {filename} to {title}")
        except Exception as e:
            missing.append(
                {
                    "key": key,
                    "title": title,
                    "filename": filename,
                    "reason": f"Failed to attach: {e}",
                }
            )
            print(f"⚠ Failed to attach {filename}: {e}")

# ----------------- LOG RESULTS -----------------
print("\nSUMMARY")
print(
    f"Would attach: {len(attached)}" if args.dry_run else f"Attached: {len(attached)}"
)
print(f"Skipped (already linked): {len(skipped)}")
print(f"Missing or failed: {len(missing)}")

pd.DataFrame(attached).to_csv("attached_links.csv", index=False)
pd.DataFrame(skipped).to_csv("skipped_links.csv", index=False)
pd.DataFrame(missing).to_csv("missing_links.csv", index=False)

print("Logs saved: attached_links.csv, skipped_links.csv, missing_links.csv")
