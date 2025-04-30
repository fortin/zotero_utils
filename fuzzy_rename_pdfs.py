import re
import csv
from pathlib import Path
import bibtexparser
from difflib import SequenceMatcher
from decouple import config

# === CONFIG ===
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
log_path = pdf_dir.parent / "fuzzy_rename_log.csv"
dry_run = True  # Set to False to actually rename files

def normalize(text):
    return re.sub(r'\W+', '', text.lower())

def fuzzy_match(a, b):
    return SequenceMatcher(None, a, b).ratio()

# Load BibTeX entries
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)

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

# Scan and match PDFs
log = []

for pdf in pdf_dir.glob("*.pdf"):
    norm_name = normalize(pdf.stem)

    best_match = None
    best_score = 0.0

    for entry in entries:
        score = 0.0
        if entry["year"] in norm_name:
            score += 0.3
        if entry["author"] in norm_name:
            score += 0.3
        score += 0.4 * fuzzy_match(entry["title"], norm_name)

        if score > best_score and score > 0.65:
            best_score = score
            best_match = entry

    if best_match:
        new_name = f"{best_match['key']}.pdf"
        new_path = pdf_dir / new_name
        result = "⚠️ Exists — skipped" if new_path.exists() else "✓ Rename planned"
        if not dry_run and not new_path.exists():
            print(f"{pdf} renamed to {new_path}")
            pdf.rename(new_path)
            result = "✓ Renamed"
        log.append({
            "Original": pdf.name,
            "New": new_name,
            "CitationKey": best_match["key"],
            "Score": f"{best_score:.2f}",
            "Result": result
        })
    else:
        print(f"Failed to rename {pdf}")
        log.append({
            "Original": pdf.name,
            "New": "",
            "CitationKey": "",
            "Score": "0.00",
            "Result": "❌ No match"
        })

# Write log
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Original", "New", "CitationKey", "Score", "Result"])
    writer.writeheader()
    writer.writerows(log)

print(f"✅ Log written to: {log_path}")