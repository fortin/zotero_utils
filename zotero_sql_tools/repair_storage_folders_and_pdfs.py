import csv
import os
import shutil
import sqlite3
from pathlib import Path

from decouple import config
from tqdm import tqdm

# ===== CONFIG =====
zotero_db_path = Path(config("ZOTERO_SQLITE")).expanduser()
storage_path = Path(config("ZOTERO_STORAGE")).expanduser()
pdf_source_folder = Path(config("PDF_FOLDER")).expanduser()

log_path = Path("logs/final_storage_repair_log.csv")

dry_run = "--dry-run" in os.sys.argv

# ===== CONNECT TO SQLITE =====
conn = sqlite3.connect(zotero_db_path)
cur = conn.cursor()

print("[✓] Fetching attachments and their paths...")
cur.execute(
    """
    SELECT itemID, path
    FROM itemAttachments
    WHERE path LIKE 'storage/%'
    """
)
rows = cur.fetchall()

print(f"[✓] Attachments to process: {len(rows)}")

# ===== PROCESS ATTACHMENTS =====
log_rows = []

for itemID, path in tqdm(rows, desc="Repairing storage"):
    try:
        parts = Path(path).parts
        key = parts[1] if len(parts) > 1 else None
        filename = parts[-1] if len(parts) > 0 else None

        if not key or not filename:
            log_rows.append(
                {
                    "itemID": itemID,
                    "status": "Invalid path structure",
                    "source_pdf": "",
                    "storage_folder": "",
                }
            )
            continue

        storage_folder = storage_path / key
        dest_pdf = storage_folder / filename
        source_pdf = pdf_source_folder / filename

        if not storage_folder.exists():
            if dry_run:
                status = "Missing storage folder — would create"
            else:
                storage_folder.mkdir(parents=True, exist_ok=True)
                status = "Storage folder created"
        else:
            status = "Storage folder exists"

        if dest_pdf.exists():
            final_status = "PDF already present"
        elif source_pdf.exists():
            if dry_run:
                final_status = f"Would copy {source_pdf.name} to {storage_folder}"
            else:
                shutil.copy2(source_pdf, dest_pdf)
                final_status = f"Copied {source_pdf.name} to {storage_folder}"
        else:
            final_status = f"Source PDF missing: {source_pdf.name}"

        log_rows.append(
            {
                "itemID": itemID,
                "status": status,
                "source_pdf": str(source_pdf),
                "storage_folder": str(storage_folder),
                "final_status": final_status,
            }
        )

    except Exception as e:
        log_rows.append(
            {
                "itemID": itemID,
                "status": f"Error: {e}",
                "source_pdf": "",
                "storage_folder": "",
                "final_status": "Failed",
            }
        )

conn.close()

# ===== SAVE LOG =====
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=["itemID", "status", "source_pdf", "storage_folder", "final_status"],
    )
    writer.writeheader()
    for row in log_rows:
        writer.writerow(row)

print("\n✅ Repair complete.")
print(f"✔ Log saved to {log_path}")
if dry_run:
    print("⚠ Dry run only. No files were moved.")
