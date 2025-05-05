import csv
import shutil
import sys
from pathlib import Path

from decouple import config
from tqdm import tqdm

# =========================== CONFIG ===========================

pdf_dir = Path(config("PDF_FOLDER"))
storage_dir = Path(config("ZOTERO_STORAGE"))
log_path = Path("logs/pdf_storage_repair_log.csv")
match_log = Path("logs/pdf_match_log.csv")

dry_run = "--dry-run" in sys.argv


# =========================== LOAD MATCH LOG ===========================

print("[✓] Loading match log...")
rows = []
with open(match_log, newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        rows.append(row)

print(f"[✓] Loaded {len(rows)} entries from match log.")

# =========================== MAIN ===========================

results = []

for row in tqdm(rows, desc="Repairing storage"):
    key = row.get("Key") or row.get("key")
    pdf_name = row.get("PDF") or row.get("pdf")

    if not key or not pdf_name:
        continue  # Skip rows without key or filename

    # Detect if the PDF name contains a corrupt full path
    if "/" in pdf_name or "\\" in pdf_name:
        # Extract just the filename from the corrupt path
        clean_name = Path(pdf_name).name
    else:
        clean_name = pdf_name

    # Sanity: PDF must end with .pdf
    if not clean_name.lower().endswith(".pdf"):
        continue

    source_pdf = pdf_dir / clean_name
    target_folder = storage_dir / key
    target_pdf = target_folder / clean_name

    action = ""
    if not target_folder.exists():
        if dry_run:
            action = "Storage folder missing (dry-run)"
        else:
            target_folder.mkdir(parents=True, exist_ok=True)
            action = "Storage folder created"

    if target_pdf.exists():
        action = "PDF already present"
    elif not source_pdf.exists():
        action = "Source PDF missing"
    else:
        if dry_run:
            action = "Would copy"
        else:
            try:
                shutil.copy2(source_pdf, target_pdf)
                action = "PDF copied"
            except Exception as e:
                action = f"Copy failed: {e}"

    results.append({"Key": key, "PDF": clean_name, "Action": action})

# =========================== SAVE LOG ===========================

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Key", "PDF", "Action"])
    writer.writeheader()
    for r in results:
        writer.writerow(r)

print("\n✅ Repair process complete.")
print(f"✔ Items processed: {len(results)}")
print(f"✔ Log saved to {log_path}")
if dry_run:
    print("⚠ Dry run only. No files were moved.")
