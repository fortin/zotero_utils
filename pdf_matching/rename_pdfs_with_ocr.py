import csv
import re
import subprocess
from difflib import SequenceMatcher
from pathlib import Path
from tempfile import NamedTemporaryFile

import bibtexparser
from decouple import config
from pdfminer.high_level import extract_text

# === CONFIG ===
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
log_path = pdf_dir.parent / "logs/content_match_rename_log.csv"
dry_run = False  # Set to False to apply renames


def normalize(text):
    return re.sub(r"\W+", "", text.lower())


def fuzzy_match(a, b):
    return SequenceMatcher(None, a, b).ratio()


def extract_text_from_pdf(pdf_path, max_chars=1000):
    try:
        text = extract_text(pdf_path, maxpages=1)
        return normalize(text[:max_chars])
    except Exception:
        return ""


def ocr_and_extract_text(pdf_path, max_chars=1000):
    with NamedTemporaryFile(suffix=".pdf", delete=False) as temp_file:
        temp_path = Path(temp_file.name)
    try:
        subprocess.run(
            ["ocrmypdf", "--skip-text", "--force-ocr", str(pdf_path), str(temp_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return extract_text_from_pdf(temp_path, max_chars), True
    except Exception:
        return "", False
    finally:
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)


# Load BibTeX entries
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)

entries = []
for entry in bib_db.entries:
    key = entry.get("ID", "").strip()
    if not key or key.startswith(":") or key.startswith("/") or "/" in key:
        continue
    safe_key = re.sub(r'[\/:*?"<>|]', "_", key)
    author = entry.get("author", "").split(" and ")[0].split(",")[0].strip()
    title = entry.get("title", "").strip().split(":")[0]
    entries.append(
        {
            "key": safe_key,
            "author": normalize(author),
            "title": normalize(" ".join(title.split()[:6])),
        }
    )

# Main loop
log = []

for pdf in pdf_dir.glob("*.pdf"):
    content = extract_text_from_pdf(pdf)
    used_ocr = False

    if not content or len(content) < 100:
        content, used_ocr = ocr_and_extract_text(pdf)

    if not content:
        log.append(
            {
                "Original": pdf.name,
                "New": "",
                "CitationKey": "",
                "Score": "0.00",
                "Result": "❌ Failed to read (even with OCR)",
            }
        )
        continue

    best_match = None
    best_score = 0.0

    for entry in entries:
        score = 0.0
        if entry["author"] in content:
            score += 0.3
        score += 0.7 * fuzzy_match(entry["title"], content)
        if score > best_score and score > 0.9:
            best_score = score
            best_match = entry

    if best_match:
        new_name = f"{best_match['key']}.pdf"
        new_path = pdf_dir / new_name
        result = "✓ Rename planned" if dry_run else "✓ Renamed"
        if not dry_run and not new_path.exists():
            pdf.rename(new_path)
        elif new_path.exists():
            result = "⚠️ Exists — skipped"
        log.append(
            {
                "Original": pdf.name,
                "New": new_name,
                "CitationKey": best_match["key"],
                "Score": f"{best_score:.2f}",
                "Result": f"{result}{' (OCR)' if used_ocr else ''}",
            }
        )
    else:
        log.append(
            {
                "Original": pdf.name,
                "New": "",
                "CitationKey": "",
                "Score": "0.00",
                "Result": "❌ No match (after OCR)" if used_ocr else "❌ No match",
            }
        )

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["Original", "New", "CitationKey", "Score", "Result"]
    )
    writer.writeheader()
    writer.writerows(log)

print(f"✅ Log written to: {log_path}")
