import csv
import os
import sys
from pathlib import Path

from decouple import config
from pyzotero import zotero
from tqdm import tqdm

# ===== CONFIG =====
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
storage_dir = Path(config("ZOTERO_STORAGE"))
dry_run = "--dry-run" in sys.argv

log_path = Path("logs/final_relink_log.csv")

# ===== CONNECT =====
zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

# ===== FETCH ITEMS =====
print("[✓] Fetching all Zotero items...")
all_items = zot.everything(zot.items())
print(f"[✓] Items fetched: {len(all_items)}")

# ===== FETCH ATTACHMENTS =====
print("[✓] Fetching all attachments...")
attachments = zot.everything(zot.items(itemType="attachment"))
print(f"[✓] Attachments fetched: {len(attachments)}")

# Map itemKey -> set of filenames already attached
attached = {}
for att in attachments:
    parent = att["data"].get("parentItem")
    if parent:
        path = att["data"].get("path", "")
        attached.setdefault(parent, set()).add(path)

# ===== PROCESS =====
log_rows = []

for item in tqdm(all_items, desc="Processing items"):
    data = item["data"]
    key = item["key"]

    # Only look at items that can have attachments
    if data["itemType"] not in {
        "journalArticle",
        "book",
        "conferencePaper",
        "presentation",
    }:
        continue

    # Skip if it already has an attachment
    if key in attached:
        log_rows.append(
            {
                "itemKey": key,
                "Title": data.get("title", ""),
                "Action": "Attachment exists, skipping.",
            }
        )
        continue

    # Look for a PDF in the corresponding storage folder
    folder = storage_dir / key
    if not folder.exists():
        log_rows.append(
            {
                "itemKey": key,
                "Title": data.get("title", ""),
                "Action": "Storage folder missing.",
            }
        )
        continue

    pdfs = list(folder.glob("*.pdf"))
    if not pdfs:
        log_rows.append(
            {
                "itemKey": key,
                "Title": data.get("title", ""),
                "Action": "No PDF found in folder.",
            }
        )
        continue

    pdf = pdfs[0]  # Take first PDF found
    filename = pdf.name

    if dry_run:
        log_rows.append(
            {
                "itemKey": key,
                "Title": data.get("title", ""),
                "PDF": filename,
                "Action": "Would create attachment [DRY RUN]",
            }
        )
    else:
        try:
            zot.attachment_import(str(pdf), key)
            log_rows.append(
                {
                    "itemKey": key,
                    "Title": data.get("title", ""),
                    "PDF": filename,
                    "Action": "Attachment created.",
                }
            )
        except Exception as e:
            log_rows.append(
                {
                    "itemKey": key,
                    "Title": data.get("title", ""),
                    "PDF": filename,
                    "Action": f"Failed to create attachment: {e}",
                }
            )

# ===== SAVE LOG =====
fields = ["itemKey", "Title", "PDF", "Action"]

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in log_rows:
        for field in fields:
            if field not in row:
                row[field] = ""
        writer.writerow(row)

print("\n✅ Process complete.")
print(f"✔ Log saved to {log_path}")
if dry_run:
    print("⚠ Dry run only. No attachments were created.")
