import csv
import re
from pathlib import Path

from decouple import config
from pyzotero import zotero
from tqdm import tqdm

# =========================== CONFIGURATION ===========================
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

storage_dir = Path("/Users/antonio/Zotero/storage")
bad_path_prefix = "/Users/antonio/Dropbox/Documents/DocumentLibrary/BibDesk"

log_rows = []

# =========================== FETCH ATTACHMENTS ===========================
print("Fetching all Zotero attachments...")
attachments = zot.everything(zot.items(itemType="attachment"))
print(f"[✓] Attachments fetched: {len(attachments)}")

updated_count = 0

for att in tqdm(attachments, desc="Checking attachments"):
    data = att["data"]
    key = att["key"]
    path = data.get("path", "")

    if data.get("linkMode") != "linked_file":
        continue
    if bad_path_prefix not in path:
        continue

    # 🔥 Correct way to get just the filename
    if path.startswith(bad_path_prefix):
        filename = Path(path).name
    else:
        filename = Path(path).name  # Fallback, just in case

    # Get storage key
    match = re.search(r"/storage/([^/]+)/", path)
    if not match:
        log_rows.append(
            {
                "key": key,
                "old_path": path,
                "new_path": "",
                "status": "❌ No storage key found",
            }
        )
        continue

    storage_key = match.group(1)
    new_path = str(storage_dir / storage_key / filename)

    # If already correct, skip
    if new_path == path:
        log_rows.append(
            {
                "key": key,
                "old_path": path,
                "new_path": new_path,
                "status": "⚠ Already correct",
            }
        )
        continue

    # Update only if the new path exists
    if Path(new_path).exists():
        try:
            zot.update_item({"data": {**data, "path": new_path}})
            updated_count += 1
            status = "✅ Updated"
        except Exception as e:
            status = f"❌ Update failed: {e}"
    else:
        status = "❗ New path does not exist yet"

    log_rows.append(
        {"key": key, "old_path": path, "new_path": new_path, "status": status}
    )

# =========================== SAVE LOG ===========================
log_file = "logs/fix_links_log.csv"
with open(log_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["key", "old_path", "new_path", "status"])
    writer.writeheader()
    for row in log_rows:
        writer.writerow(row)

print(f"\n✅ Update complete. Attachments updated: {updated_count}")
print(f"✔ Log saved to {log_file}")
