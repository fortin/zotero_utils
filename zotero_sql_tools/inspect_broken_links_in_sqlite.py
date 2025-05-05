import csv
import sqlite3
from pathlib import Path

from decouple import config
from tqdm import tqdm

# ====== CONFIG ======
zotero_sqlite = Path(config("ZOTERO_SQLITE"))
pdf_folder = Path(config("PDF_FOLDER"))
storage_folder = Path(config("ZOTERO_STORAGE"))
bad_prefix = config("PDF_FOLDER")

output_csv = Path("logs/sqlite_broken_links_report.csv")

# ====== LOAD SQLITE ======
print("[✓] Connecting to Zotero database...")
conn = sqlite3.connect(zotero_sqlite)
cursor = conn.cursor()

print("[✓] Querying broken attachment links...")
cursor.execute(
    """
    SELECT itemAttachments.itemID, itemAttachments.path, items.key
    FROM itemAttachments
    JOIN items ON itemAttachments.itemID = items.itemID
    WHERE itemAttachments.path LIKE ?
""",
    (f"%{bad_prefix}%",),
)

rows = cursor.fetchall()
print(f"[✓] Broken attachments found: {len(rows)}")

# ====== PROCESS ======
log_rows = []

for itemID, path, itemKey in tqdm(rows, desc="Inspecting attachments"):
    full_path = Path(path)
    expected_filename = full_path.name

    # Expected storage folder and path
    storage_subfolder = storage_folder / itemKey
    expected_storage_pdf = storage_subfolder / expected_filename

    # Does storage folder exist?
    folder_exists = storage_subfolder.exists()

    # Does PDF exist in storage?
    pdf_in_storage = expected_storage_pdf.exists()

    # Does PDF exist in source PDF folder?
    pdf_in_source = (pdf_folder / expected_filename).exists()

    # Decide action needed
    if pdf_in_storage:
        action = "Already in storage"
    elif not pdf_in_source:
        action = "Missing PDF in source folder"
    else:
        action = "Needs copy to storage"

    log_rows.append(
        {
            "itemKey": itemKey,
            "badPath": path,
            "expectedFilename": expected_filename,
            "storageFolderExists": folder_exists,
            "pdfInStorage": pdf_in_storage,
            "pdfInSourceFolder": pdf_in_source,
            "actionNeeded": action,
        }
    )

# ====== SAVE REPORT ======
with open(output_csv, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=log_rows[0].keys())
    writer.writeheader()
    writer.writerows(log_rows)

print(f"\n✅ Inspection complete.")
print(f"✔ Report saved to {output_csv}")
