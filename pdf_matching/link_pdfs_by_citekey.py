import csv
import re
from pathlib import Path

import bibtexparser
import requests
from decouple import config

# === USER CONFIG ===
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
csv_log_path = pdf_dir / "logs/zotero_link_log.csv"
headers = {"Zotero-API-Key": ZOTERO_API_KEY}


# === HELPERS ===
def normalize(text):
    return re.sub(r"\W+", "", text.lower())


def find_fallback_pdf(entry):
    author = entry.get("author", "").split(" and ")[0].split(",")[0].strip().lower()
    year = entry.get("year", "").strip()
    title_words = re.findall(r"\w+", entry.get("title", "").lower())
    patterns = [
        f"{author}_{year}",
        f"{author}{year}",
        f"{author}_{year}_{'_'.join(title_words[:3])}",
    ]
    for file in pdf_dir.glob("*.pdf"):
        base = file.stem.lower()
        if any(p in base for p in patterns):
            return file
    return None


# === MAIN LOGIC ===
with open(bib_path, "r", encoding="utf-8") as bibfile:
    bib_db = bibtexparser.load(bibfile)

log_rows = []

for entry in bib_db.entries:
    citation_key = entry.get("ID", "").strip()
    item_url = f"https://api.zotero.org/users/{ZOTERO_USER_ID}/items?format=json&key={citation_key}"
    r = requests.get(item_url, headers=headers)
    if r.status_code != 200:
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": "",
                "Result": f"❌ Zotero API error: {r.status_code} ({r.text[:100]})",
            }
        )
        continue

    try:
        items = r.json()
    except Exception as e:
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": "",
                "Result": f"❌ JSON decode error: {str(e)} — Body: {r.text[:100]}",
            }
        )
        continue
    if not items:
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": "",
                "Result": "❌ Item not found in Zotero",
            }
        )
        continue

    item_key = items[0]["key"]
    pdf_path = pdf_dir / f"{citation_key}.pdf"
    fallback_used = False

    if not pdf_path.exists():
        pdf_path = find_fallback_pdf(entry)
        fallback_used = True if pdf_path else False

    if not pdf_path or not pdf_path.exists():
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": "",
                "Result": "❌ No matching PDF found",
            }
        )
        continue

    rel_path = pdf_path.relative_to(pdf_dir.parent)  # relative to base dir
    attach_url = f"https://api.zotero.org/users/{ZOTERO_USER_ID}/items/{item_key}/file"

    payload = {
        "filename": pdf_path.name,
        "path": str(pdf_path),
        "linkMode": 2,  # linked file
    }

    # Actually attach file
    r = requests.post(
        f"https://api.zotero.org/users/{ZOTERO_USER_ID}/items/{item_key}/attachments",
        headers=headers,
        json={
            "itemType": "attachment",
            "linkMode": 2,
            "title": pdf_path.name,
            "path": str(rel_path),
            "contentType": "application/pdf",
            "tags": [],
            "relations": {},
        },
    )

    if r.status_code in (200, 201):
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": pdf_path.name,
                "Result": "✓ Linked (fallback)" if fallback_used else "✓ Linked",
            }
        )
    else:
        log_rows.append(
            {
                "CitationKey": citation_key,
                "File": pdf_path.name,
                "Result": f"❌ API error: {r.status_code}",
            }
        )

# === SAVE LOG ===
with open(csv_log_path, "w", newline="", encoding="utf-8") as csvfile:
    fieldnames = ["CitationKey", "File", "Result"]
    writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(log_rows)

print(f"Log written to: {csv_log_path}")
