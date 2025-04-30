import bibtexparser
import re
from pathlib import Path
import csv
from decouple import config


# === CONFIG ===
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
csv_report_path = pdf_dir / "fallback_rename_report.csv"
dry_run = True  # Set to False to apply changes

def normalize(text):
    return re.sub(r'\W+', '', text.lower())

# === LOAD BIB FILE ===
with open(bib_path, "r", encoding="utf-8") as bibfile:
    bib_db = bibtexparser.load(bibfile)

# Prepare lookup table
bib_entries = []
for entry in bib_db.entries:
    key = entry.get("ID", "").strip()
    author = entry.get("author", "").split(" and ")[0].split(",")[0].strip()
    year = entry.get("year", "").strip()
    title = entry.get("title", "").strip()
    bib_entries.append({
        "key": key,
        "author": normalize(author),
        "year": year,
        "title": normalize(" ".join(title.split()[:4]))
    })

# === RENAME LOGIC ===
rename_log = []

for file in pdf_dir.glob("*.pdf"):
    base = file.stem
    if re.match(r".+ -\d{4}- .+", base):
        parts = base.split(" -")
        if len(parts) < 3:
            continue
        author_raw = parts[0].strip()
        year_match = re.findall(r"\d{4}", parts[1])
        if not year_match:
            continue
        year = year_match[0]
        title_words = normalize(" ".join(parts[2:])[:40])
        author_norm = normalize(author_raw)

        matched = None
        for entry in bib_entries:
            if entry["author"] in author_norm and entry["year"] == year and entry["title"] in title_words:
                matched = entry
                break

        if matched:
            new_filename = f"{matched['key']}.pdf"
            new_path = pdf_dir / new_filename
            if new_path.exists():
                result = "⚠️ Exists — skipped"
            else:
                result = "✓ Rename planned" if dry_run else "✓ Renamed"
                if not dry_run:
                    file.rename(new_path)
            rename_log.append({
                "Original": file.name,
                "New": new_filename,
                "CitationKey": matched['key'],
                "Result": result
            })
        else:
            rename_log.append({
                "Original": file.name,
                "New": "",
                "CitationKey": "",
                "Result": "❌ No match found"
            })

# === WRITE LOG ===
with open(csv_report_path, "w", newline="", encoding="utf-8") as csvfile:
    writer = csv.DictWriter(csvfile, fieldnames=["Original", "New", "CitationKey", "Result"])
    writer.writeheader()
    writer.writerows(rename_log)

print(f"Log saved to: {csv_report_path}")