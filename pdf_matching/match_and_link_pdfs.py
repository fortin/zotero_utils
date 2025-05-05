import csv
import re
import shutil
import sys
import time
from pathlib import Path

import bibtexparser
from decouple import config
from httpx import ReadTimeout
from pyzotero import zotero
from rapidfuzz import fuzz
from tqdm import tqdm

# =========================== CONFIGURATION ===========================
bib_path = Path(config("BIB_PATH"))
pdf_dir = Path(config("PDF_FOLDER"))
storage_dir = Path(config("ZOTERO_STORAGE"))
log_path = Path("logs/pdf_match_log.csv")

ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

dry_run = "--dry-run" in sys.argv


# =========================== HELPERS ===========================
def normalize(text):
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def best_pdf_match(title):
    n_title = normalize(title)
    best_score = 0
    best_file = None
    for pdf in pdf_files:
        n_name = normalize(pdf.stem)
        score = fuzz.partial_ratio(n_title, n_name)
        if score > best_score and score > 70:
            best_score = score
            best_file = pdf
    return best_file, best_score


def fetch_children_with_retry(item_key, retries=5):
    delay = 2
    for attempt in range(retries):
        try:
            return zot.children(item_key)
        except (ReadTimeout, Exception):
            if attempt < retries - 1:
                time.sleep(delay)
                delay *= 2
            else:
                return []


# =========================== LOAD DATA ===========================
print("[✓] BibTeX entries loading...")
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)
    bib_entries = bib_db.entries

print(f"[✓] BibTeX entries loaded: {len(bib_entries)}")

bib_lookup = {}
for entry in bib_entries:
    key = entry.get("ID", "")
    title = normalize(entry.get("title", ""))
    bib_lookup[title] = key

print("Fetching Zotero items...")
zot_items = zot.everything(zot.items())
print(f"[✓] Zotero items fetched: {len(zot_items)}")

pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"[✓] PDFs available in folder: {len(pdf_files)}")

# =========================== PROCESS ===========================
log_rows = []

for item in tqdm(zot_items, desc="Matching items"):
    item_key = item["key"]
    data = item["data"]
    if data["itemType"] not in {
        "journalArticle",
        "book",
        "conferencePaper",
        "presentation",
    }:
        continue

    title = data.get("title", "")
    n_title = normalize(title)
    citekey = bib_lookup.get(n_title, None)

    if not citekey:
        log_rows.append(
            {"Key": item_key, "Title": title, "Action": "No citekey found in BibTeX"}
        )
        continue

    expected_pdf = pdf_dir / f"{citekey}.pdf"
    if not expected_pdf.exists():
        pdf, score = best_pdf_match(title)
        if not pdf:
            log_rows.append({"Key": item_key, "Title": title, "Action": "No PDF match"})
            continue
        source_pdf = pdf
    else:
        source_pdf = expected_pdf

    # Now prepare to place this PDF in Zotero storage
    storage_folder = storage_dir / item_key
    storage_folder.mkdir(parents=True, exist_ok=True)

    filename = source_pdf.name

    # ===== SANITIZE FILENAME =====
    if "/" in filename or "\\" in filename:
        sanitized_filename = filename.replace("/", "_").replace("\\", "_")
        log_rows.append(
            {
                "Key": item_key,
                "Title": title,
                "PDF": filename,
                "Action": f"Filename sanitized to {sanitized_filename}",
            }
        )
    else:
        sanitized_filename = filename

    dest_pdf = storage_folder / sanitized_filename

    if dest_pdf.exists():
        action = "Already present in storage"
    else:
        if dry_run:
            action = "Would copy"
        else:
            try:
                shutil.copy2(source_pdf, dest_pdf)
                action = "Copied to storage"
            except Exception as e:
                action = f"Copy failed: {e}"

    log_rows.append(
        {"Key": item_key, "Title": title, "PDF": sanitized_filename, "Action": action}
    )

# =========================== SAVE LOG ===========================
fields = ["Key", "Title", "PDF", "Action"]

with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for row in log_rows:
        writer.writerow(row)

print("\n✅ Process complete.")
print(f"✔ Log saved to {log_path}")
