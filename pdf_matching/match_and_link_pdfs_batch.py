import os
import re
import io
import csv
import shutil
import requests
import datetime
from pathlib import Path
from decouple import config
from PyPDF2 import PdfReader, PdfWriter
from tqdm import tqdm

# === CONFIG ===
ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))

# Create originals folder
originals_dir = pdf_dir.parent / "originals"
originals_dir.mkdir(exist_ok=True)

# Log file with date stamp
timestamp = datetime.datetime.now().strftime("%Y-%m-%d")
log_path = pdf_dir.parent / f"auto_link_log_{timestamp}.csv"

# === ZOTERO SETUP ===
API_ROOT = f"https://api.zotero.org/users/{ZOTERO_USER_ID}"
session = requests.Session()
session.headers.update({"Zotero-API-Key": ZOTERO_API_KEY})

# === BIBTEX SETUP ===
import bibtexparser
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)
entries = {entry['ID']: entry for entry in bib_db.entries}

def zotero_api(path, params={}):
    resp = session.get(f"{API_ROOT}{path}", params=params)
    resp.raise_for_status()
    return resp.json()

def get_unlinked_items():
    start = 0
    items = []
    while True:
        params = {
            "itemType": "-attachment",
            "format": "json",
            "limit": 100,
            "start": start
        }
        batch = zotero_api("/items", params)
        if not batch:
            break
        items.extend(batch)
        start += 100
    return items

def search_pdf(title):
    title_clean = re.sub(r'[^\w\s]', '', title).lower()
    for pdf_path in pdf_dir.glob("*.pdf"):
        pdf_name_clean = re.sub(r'[^\w\s]', '', pdf_path.stem).lower()
        if title_clean in pdf_name_clean or pdf_name_clean in title_clean:
            return pdf_path
    return None

def update_pdf_metadata(pdf_path, entry):
    changed = False
    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()
    writer.append_pages_from_reader(reader)

    info = reader.metadata or {}

    title = entry.get("title", "").strip()
    author = entry.get("author", "").strip()
    year = entry.get("year", "").strip()

    new_info = {}
    if not info.get("/Title") and title:
        new_info["/Title"] = title
        changed = True
    if not info.get("/Author") and author:
        new_info["/Author"] = author
        changed = True
    if not info.get("/CreationDate") and year:
        new_info["/CreationDate"] = f"D:{year}0101000000"
        changed = True

    writer.add_metadata({**info, **new_info})

    if changed:
        temp_pdf = pdf_path.with_suffix(".temp.pdf")
        with open(temp_pdf, "wb") as f:
            writer.write(f)
        shutil.move(str(temp_pdf), str(pdf_path))

def link_to_zotero(item_key, file_path):
    files = {'file': open(file_path, 'rb')}
    params = {
        "linkMode": "imported_file",
        "title": Path(file_path).stem
    }
    url = f"{API_ROOT}/items/{item_key}/file"
    r = session.post(url, params=params, files=files)
    return r.status_code == 204

# === MAIN ===

unlinked_items = get_unlinked_items()
log_rows = []

print(f"Found {len(unlinked_items)} top-level items without attachments.")

for item in tqdm(unlinked_items, desc="Processing items"):
    data = item['data']
    key = data['key']
    title = data.get("title") or ""
    citekey = data.get("extra", "")
    m = re.search(r"Citation Key:\s*(\S+)", citekey)
    if not m:
        log_rows.append([key, title, "❌ No citation key"])
        continue
    citekey = m.group(1)

    entry = entries.get(citekey)
    if not entry:
        log_rows.append([key, title, "❌ No BibTeX entry for citation key"])
        continue

    # Check if already renamed PDF exists
    renamed_pdf = pdf_dir / f"{citekey}.pdf"
    if renamed_pdf.exists():
        log_rows.append([key, title, "✔ Already linked or renamed"])
        continue

    found_pdf = search_pdf(title)
    if not found_pdf:
        log_rows.append([key, title, "❌ No matching PDF found"])
        continue

    # Move original
    dest_original = originals_dir / found_pdf.name
    shutil.move(str(found_pdf), dest_original)

    # Copy and rename
    renamed_path = pdf_dir / f"{citekey}.pdf"
    shutil.copy(str(dest_original), str(renamed_path))

    # Update metadata
    update_pdf_metadata(renamed_path, entry)

    # Link to Zotero
    success = link_to_zotero(key, renamed_path)
    if success:
        log_rows.append([key, title, "✔ Linked and renamed"])
    else:
        log_rows.append([key, title, "❌ Failed to link to Zotero"])

# Save CSV log
with open(log_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Zotero Key", "Title", "Status"])
    writer.writerows(log_rows)

print(f"✅ Done. Log saved to {log_path}")