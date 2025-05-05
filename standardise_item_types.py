import re
import sys
from pathlib import Path
from decouple import config

# --------------------------- CONFIG ---------------------------
bib_path = Path(config("BIB_PATH"))

# --------------------------- LOAD ---------------------------
with open(bib_path, "r", encoding="utf-8") as f:
    bib_content = f.read()

original_content = bib_content

# --------------------------- REPLACEMENTS ---------------------------

# Define replacement patterns
replacements = {
    r"@report": "@techreport",
    r"@thesis": "@phdthesis",
    r"@online": "@misc",
    r"@electronic": "@misc"
}

for pattern, replacement in replacements.items():
    bib_content = re.sub(pattern, replacement, bib_content, flags=re.IGNORECASE)

# --------------------------- SAVE OR REPORT ---------------------------
changes = original_content != bib_content

if changes:
    with open(bib_path, "w", encoding="utf-8") as f:
        f.write(bib_content)
    print(f"✅ Changes applied to {bib_path}")
    sys.exit(1)  # Hazel can detect this and notify
else:
    print("No changes needed.")
    sys.exit(0)