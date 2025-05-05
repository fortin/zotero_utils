import csv
import re
import sys
from pathlib import Path

from decouple import config
from pyzotero import zotero
from tqdm import tqdm

# ---------- CONFIG ----------

ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")

log_path = Path("logs/type_remap_log.csv")
dry_run = "--dry-run" in sys.argv

# Match the BibTeX remap:
remap = {
    "report": "presentation",
    "thesis": "presentation",
    "online": "presentation",
    "electronic": "presentation",
}

# ---------- INIT ----------

zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

print("Fetching Zotero items...")
items = zot.everything(zot.items())
print(f"[✓] Total items fetched: {len(items)}")

changes = 0
errors = 0
log_rows = []

# ---------- MAIN ----------

for item in tqdm(items, desc="Processing items"):
    data = item["data"]
    key = item["key"]
    old_type = data.get("itemType", "").lower()

    if old_type not in remap:
        continue

    new_type = remap[old_type]

    if old_type == new_type:
        continue

    print(f"[{key}] Changing type '{old_type}' → '{new_type}'")

    # Prepare data for update
    version = item["version"]
    new_data = {k: v for k, v in data.items()}

    # Change type
    new_data["itemType"] = new_type

    # Remove invalid fields for the new type
    valid_fields = zot.item_fields()  # No argument → returns all fields
    invalid_fields = []
    for field in list(new_data.keys()):
        if field not in valid_fields and field not in ["itemType", "key"]:
            invalid_fields.append(field)
            del new_data[field]

    log_rows.append(
        {
            "key": key,
            "old_type": old_type,
            "new_type": new_type,
            "removed_fields": ", ".join(invalid_fields) if invalid_fields else "",
            "status": "Dry run" if dry_run else "Updated",
        }
    )

    if dry_run:
        continue

    try:
        zot.update_item(new_data, last_modified=version)
        changes += 1
    except Exception as e:
        errors += 1
        print(f"❌ [{key}] Error: {e}")
        log_rows[-1]["status"] = f"Error: {e}"

# ---------- LOG ----------

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["key", "old_type", "new_type", "removed_fields", "status"]
    )
    writer.writeheader()
    writer.writerows(log_rows)

print("\n✅ Script complete.")
print(f"✔ Changes applied: {changes}")
print(f"❌ Errors: {errors}")
print(f"Log saved to {log_path}")
