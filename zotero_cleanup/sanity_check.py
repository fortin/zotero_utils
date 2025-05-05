import csv
import sqlite3
from pathlib import Path

from decouple import config
from pyzotero import zotero

# ===== CONFIG =====
zotero_db_path = Path(config("ZOTERO_SQLITE")).expanduser()
zotero_storage = Path(config("ZOTERO_STORAGE")).expanduser()

ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")

zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

log_path = Path("cache/sanity_check_report.csv")

# ===== FETCH ATTACHMENTS =====
print("[✓] Fetching Zotero attachments...")
attachments = zot.everything(zot.items(itemType="attachment"))
print(f"[✓] Attachments fetched: {len(attachments)}")

# ===== CHECK ATTACHMENTS =====
log_rows = []

missing_folder = 0
missing_pdf = 0
ok_count = 0

for att in attachments:
    key = att["key"]
    data = att["data"]

    path = data.get("path")
    linkMode = data.get("linkMode")

    if not path or linkMode != "linked_file":
        continue  # skip non-linked attachments or missing paths

    # Extract expected PDF filename
    filename = Path(path).name

    storage_folder = zotero_storage / key
    expected_pdf = storage_folder / filename

    folder_exists = storage_folder.exists()
    pdf_exists = expected_pdf.exists()

    if not folder_exists:
        missing_folder += 1
    elif not pdf_exists:
        missing_pdf += 1
    else:
        ok_count += 1

    log_rows.append(
        {
            "itemKey": key,
            "filename": filename,
            "storageFolderExists": folder_exists,
            "pdfExists": pdf_exists,
            "fullExpectedPath": str(expected_pdf),
        }
    )

# ===== SAVE REPORT =====
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "itemKey",
            "filename",
            "storageFolderExists",
            "pdfExists",
            "fullExpectedPath",
        ],
    )
    writer.writeheader()
    for row in log_rows:
        writer.writerow(row)

print("\n✅ Sanity check complete.")
print(f"✔ Report saved to {log_path}")
print("\n📊 Summary:")
print(f"✔ PDFs OK: {ok_count}")
print(f"❌ Missing storage folders: {missing_folder}")
print(f"❌ Missing PDFs (folder exists but PDF missing): {missing_pdf}")
