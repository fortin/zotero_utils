import sqlite3
import pandas as pd
from pathlib import Path
from decouple import config
import re
import argparse

# === CONFIGURATION ===
zotero_sqlite = Path(config("ZOTERO_SQLITE"))
output_csv = Path("../logs/extra_sanity_check.csv")

# === ARGPARSE ===
parser = argparse.ArgumentParser(
    description="Clean tex.uri / Papers 2 remnants from Zotero extra fields."
)
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Preview changes without modifying the database (default)",
)
args = parser.parse_args()

dry_run = args.dry_run

# === CONNECT TO SQLITE ===
conn = sqlite3.connect(zotero_sqlite)
cursor = conn.cursor()

# === STEP 1: PREVIEW EXTRA FIELDS ===

# Get all item extra fields containing 'papers2://'
query = """
SELECT itemDataValues.value, items.itemID
FROM itemData
JOIN fields ON itemData.fieldID = fields.fieldID
JOIN itemDataValues ON itemData.valueID = itemDataValues.valueID
JOIN items ON itemData.itemID = items.itemID
WHERE fields.fieldName = 'extra'
AND itemDataValues.value LIKE '%papers2://%';
"""
cursor.execute(query)
rows = cursor.fetchall()

print(f"🔎 Found {len(rows)} items with 'papers2://' in extra.")

# Export to CSV for review
df = pd.DataFrame(rows, columns=["value", "itemID"])  # corrected column order
df.to_csv(output_csv, index=False)
print(f"📄 Preview saved to: {output_csv}")


# === STEP 2: CLEANUP FUNCTION ===
def clean_value(val):
    val = str(val)
    lines = val.splitlines()
    cleaned = []
    for line in lines:
        if not re.search(r"tex\.uri\s*:", line) and "papers2://" not in line:
            cleaned.append(line)
    return "\n".join(cleaned).strip()


# === STEP 3: PROCESS AND UPDATE ===
updated = 0

for value, itemID in rows:
    new_value = clean_value(value)
    if new_value != value:
        print(f"\n📝 Item {itemID}:")
        print("Before:")
        print(value)
        print("After:")
        print(new_value)

        if not dry_run:
            # Update the itemDataValues table
            update_query = """
            UPDATE itemDataValues
            SET value = ?
            WHERE value = ? AND valueID IN (
                SELECT itemData.valueID
                FROM itemData
                JOIN fields ON itemData.fieldID = fields.fieldID
                WHERE itemData.itemID = ?
                AND fields.fieldName = 'extra'
            )
            """
            cursor.execute(update_query, (new_value, value, itemID))
            updated += 1

if not dry_run:
    conn.commit()
    print(f"\n✅ Updated {updated} items in the Zotero database.")
else:
    print("\n🔎 Dry-run complete. No changes written to the database.")

conn.close()
