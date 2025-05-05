import csv
import argparse
from pyzotero import zotero
from decouple import config
from pathlib import Path

# --- CONFIG ---
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
ZOTERO_LIBRARY = zotero.Zotero(ZOTERO_USER_ID, 'user', ZOTERO_API_KEY)

LOG_FILE = Path("bad_attachments_log.csv")

# --- ARGPARSE ---
parser = argparse.ArgumentParser(description="Delete broken Zotero attachments")
parser.add_argument("--dry-run", action="store_true", help="Simulate deletions without making changes.")
args = parser.parse_args()

def is_broken_attachment(attachment):
    """Detects if an attachment is a broken local file."""
    data = attachment.get("data", {})
    if data.get("linkMode") != "imported_file":
        return False
    path = data.get("path", "")
    return path.startswith("Users/") or path.startswith("/Users/")

def delete_attachment(item_key):
    """Deletes an attachment by key."""
    print(f"[DELETE] {item_key}")
    ZOTERO_LIBRARY.delete([item_key])

# --- MAIN ---

print("Fetching attachments...")
attachments = ZOTERO_LIBRARY.everything(ZOTERO_LIBRARY.items(itemType="attachment"))
print(f"Total attachments found: {len(attachments)}")

broken = []
for att in attachments:
    if is_broken_attachment(att):
        broken.append(att)

print(f"Broken attachments identified: {len(broken)}")

# Log CSV
with open(LOG_FILE, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["key", "path", "deleted"])
    writer.writeheader()

    for att in broken:
        key = att["key"]
        path = att["data"].get("path", "")

        if args.dry_run:
            print(f"[DRY-RUN] Would delete: {key} ({path})")
            deleted = False
        else:
            try:
                delete_attachment(key)
                deleted = True
            except Exception as e:
                print(f"[ERROR] Failed to delete {key}: {e}")
                deleted = False

        writer.writerow({"key": key, "path": path, "deleted": deleted})

print(f"Log saved to {LOG_FILE}")
print("✅ Cleanup complete.")