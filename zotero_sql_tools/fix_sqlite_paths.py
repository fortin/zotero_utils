import csv
import shutil
import sqlite3
from pathlib import Path

from decouple import config

# ===== CONFIG =====
zotero_db_path = Path(config("ZOTERO_SQLITE")).expanduser()
backup_path = zotero_db_path.with_name("zotero_backup_before_path_fix.sqlite")
log_path = Path("logs/sqlite_path_fix_log.csv")

prefix_to_remove = str(config("PDF_FOLDER")).rstrip("/")

# ===== BACKUP =====
print(f"[✓] Backing up database to: {backup_path}")
shutil.copy2(zotero_db_path, backup_path)

# ===== CONNECT =====
conn = sqlite3.connect(zotero_db_path)
cur = conn.cursor()

# ===== FETCH AFFECTED ROWS =====
print("[✓] Querying attachments with bad paths...")
cur.execute(
    """
    SELECT itemID, path
    FROM itemAttachments
    WHERE path LIKE ?
""",
    (f"%{prefix_to_remove}%",),
)

rows = cur.fetchall()
print(f"[✓] Attachments to update: {len(rows)}")

# ===== PREPARE LOG =====
log = []

# ===== UPDATE PATHS =====
for itemID, old_path in rows:
    if prefix_to_remove in old_path:
        # Extract the portion after the prefix
        new_path = old_path.split(prefix_to_remove)[-1].lstrip("/\\")
        log.append({"itemID": itemID, "old_path": old_path, "new_path": new_path})
        cur.execute(
            """
            UPDATE itemAttachments
            SET path = ?
            WHERE itemID = ?
        """,
            (new_path, itemID),
        )

# ===== COMMIT CHANGES =====
conn.commit()
conn.close()

# ===== SAVE LOG =====
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["itemID", "old_path", "new_path"])
    writer.writeheader()
    for row in log:
        writer.writerow(row)

print("\n✅ Path update complete.")
print(f"✔ Updated {len(log)} attachments.")
print(f"✔ Log saved to {log_path}")
