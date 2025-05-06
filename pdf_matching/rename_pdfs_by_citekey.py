from pathlib import Path
import bibtexparser
import re
import csv
from decouple import config

# === CONFIG ===
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
log_path = pdf_dir / "rename_log.csv"
dry_run = True  # Set to False to apply renaming

# Normalize helper
def normalize(text):
    return re.sub(r'\W+', '', text.lower())

# Load bib file
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)

# Extract structured entries
entries = []
for entry in bib_db.entries:
    key = entry.get("ID", "").strip()
    author = entry.get("author", "").split(" and ")[0].split(",")[0].strip()
    year = entry.get("year", "").strip()
    title = entry.get("title", "").strip().split(":")[0]
    entries.append({
        "key": key,
        "author": normalize(author),
        "year": year,
        "title": normalize(" ".join(title.split()[:5]))
    })

# Scan and rename matching PDFs
log = []
for pdf in pdf_dir.glob("*.pdf"):
    fname = pdf.stem
    norm_fname = normalize(fname)

    match = next(
        (e for e in entries if e["author"] in norm_fname and e["year"] in norm_fname and e["title"] in norm_fname),
        None
    )

    if match:
        new_name = f"{match['key']}.pdf"
        new_path = pdf_dir / new_name
        result = "⚠️ Exists — skipped" if new_path.exists() else "✓ Renamed"
        if not dry_run and not new_path.exists():
            pdf.rename(new_path)
        log.append({
            "Original": pdf.name,
            "New": new_name,
            "CitationKey": match['key'],
            "Result": result
        })
    else:
        log.append({
            "Original": pdf.name,
            "New": "",
            "CitationKey": "",
            "Result": "❌ No match"
        })

# Write CSV report
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Original", "New", "CitationKey", "Result"])
    writer.writeheader()
    writer.writerows(log)

print(f"✅ Log written to: {log_path}")