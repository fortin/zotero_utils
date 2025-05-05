import pandas as pd
import sys
from pathlib import Path

from decouple import config

# === CONFIGURATION ===
base_dir = Path(__file__).parent.resolve()
linked_items_path = base_dir / "linked_items.csv"
bib_path = Path(config("BIB_PATH"))

citekey = sys.argv[1]
linked_items_path = Path(sys.argv[2])

# Load the linked_items.csv
df = pd.read_csv(linked_items_path)

# If the citekey already exists, do nothing.
if citekey in df["CitationKey"].values:
    print(f"Citekey {citekey} already in linked_items.csv — skipping update.")
    sys.exit(0)

# Otherwise, add a blank row for this citekey.
new_row = {"CitationKey": citekey, "Note": "", "DEVONthink_Link": ""}
df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

# Save the updated CSV.
df.to_csv(linked_items_path, index=False)
print(f"Added {citekey} to linked_items.csv")