import csv
import shutil
import sys
from pathlib import Path

from decouple import config
from tqdm import tqdm

# ==================== CONFIG ====================
# Change these to match your environment
PDF_SOURCE_FOLDER = Path(config("PDF_FOLDER"))
ZOTERO_STORAGE = Path(config("ZOTERO_STORAGE"))

CSV_REPORT = Path("cache/sqlite_broken_links_report.csv")
DRY_RUN = "--dry-run" in sys.argv

# ==================== LOAD CSV ====================
print("[✓] Loading broken links report...")
with CSV_REPORT.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"[✓] Loaded {len(rows)} entries from sqlite_broken_links_report.csv")

# ==================== PREP LOG ====================
log_rows = []

# ==================== PROCESS ====================
for row in tqdm(rows, desc="Repairing attachments"):
    itemKey = row["itemKey"]
    expectedFilename = row["expectedFilename"]
    action = row["actionNeeded"]  # FIXED KEY NAME

    if action != "Move PDF to storage folder":
        log_rows.append(
            {"itemKey": itemKey, "Action": "No action needed", "Result": ""}
        )
        continue

    source_file = PDF_SOURCE_FOLDER / expectedFilename
    dest_folder = ZOTERO_STORAGE / itemKey
    dest_file = dest_folder / expectedFilename

    if not source_file.exists():
        log_rows.append(
            {
                "itemKey": itemKey,
                "Action": "Move PDF to storage folder",
                "Result": f"Source PDF missing: {source_file}",
            }
        )
        continue

    if not dest_folder.exists():
        if not DRY_RUN:
            dest_folder.mkdir(parents=True)
        log_msg = "Destination folder created"
    else:
        log_msg = "Destination folder existed"

    if dest_file.exists():
        log_rows.append(
            {
                "itemKey": itemKey,
                "Action": "Move PDF to storage folder",
                "Result": "PDF already present",
            }
        )
        continue

    if DRY_RUN:
        log_rows.append(
            {
                "itemKey": itemKey,
                "Action": "Move PDF to storage folder",
                "Result": f"Would move {source_file} to {dest_file}",
            }
        )
    else:
        shutil.copy2(source_file, dest_file)
        log_rows.append(
            {
                "itemKey": itemKey,
                "Action": "Move PDF to storage folder",
                "Result": f"Copied {expectedFilename} to storage",
            }
        )

# ==================== SAVE LOG ====================
log_path = Path("logs/repair_broken_links_log.csv")
with log_path.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["itemKey", "Action", "Result"])
    writer.writeheader()
    for row in log_rows:
        writer.writerow(row)

print("\n✅ Repair process complete.")
print(f"✔ Log saved to {log_path}")
if DRY_RUN:
    print("⚠ Dry run only. No files were moved.")
