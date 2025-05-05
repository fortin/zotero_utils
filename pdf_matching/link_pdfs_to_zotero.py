import csv
import re
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

ZOTERO_USER_ID = config("ZOTERO_USER_ID")
ZOTERO_API_KEY = config("ZOTERO_API_KEY")
zot = zotero.Zotero(ZOTERO_USER_ID, "user", ZOTERO_API_KEY)

dry_run = "--dry-run" in sys.argv
log_path = Path("logs/pdf_match_log.csv")


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
print("[✓] Loading BibTeX...")
with open(bib_path, "r", encoding="utf-8") as f:
    bib_db = bibtexparser.load(f)
    bib_entries = bib_db.entries

print(f"[✓] BibTeX entries loaded: {len(bib_entries)}")

bib_lookup = {}
for entry in bib_entries:
    key = entry.get("ID", "")
    title = normalize(entry.get("title", ""))
    if title:
        bib_lookup[title] = key

pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"[✓] PDFs found: {len(pdf_files)}")

print("[✓] Fetching Zotero items...")
zot_items = zot.everything(zot.items())
print(f"[✓] Zotero items fetched: {len(zot_items)}")

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
    creators = data.get("creators", [])
    author = creators[0]["lastName"] if creators and "lastName" in creators[0] else ""

    citekey = bib_lookup.get(n_title, None)

    expected_pdf = ""
    link_msg = ""

    if not citekey:
        link_msg = "No citekey found in BibTeX"
        log_rows.append(
            {"Key": item_key, "Title": title, "PDF": "", "Action": link_msg}
        )
        continue

    expected_pdf = f"{citekey}.pdf"
    expected_path = pdf_dir / expected_pdf

    # Check for existing linked attachment
    children = fetch_children_with_retry(item_key)
    already_linked = False
    for att in children:
        data_att = att["data"]
        path = data_att.get("path", "")
        if (
            data_att.get("linkMode") == "linked_file"
            and Path(path).name.lower() == expected_pdf.lower()
        ):
            already_linked = True
            break

    if already_linked:
        link_msg = "Already linked"
    elif expected_path.exists():
        if dry_run:
            link_msg = "Filename correct, ready to link [DRY RUN]"
        else:
            try:
                zot.attachment_simple([str(expected_path)], item_key)
                link_msg = "Linked existing file"
            except Exception as e:
                link_msg = f"Link failed: {e}"
    else:
        # Fuzzy matching
        pdf, score = best_pdf_match(title)
        if pdf:
            expected_pdf = pdf.name
            if dry_run:
                link_msg = f"Match found (score {score}) [DRY RUN]"
            else:
                try:
                    zot.attachment_simple([str(pdf)], item_key)
                    link_msg = f"Matched and linked (score {score})"
                except Exception as e:
                    link_msg = f"Link failed: {e}"
        else:
            link_msg = "No matching PDF found"

    log_rows.append(
        {"Key": citekey, "Title": title, "PDF": expected_pdf, "Action": link_msg}
    )

# =========================== SAVE LOG ===========================
with open(log_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["Key", "Title", "PDF", "Action"])
    writer.writeheader()
    writer.writerows(log_rows)

print("\n✅ Finished.")
print(f"✔ Log saved to {log_path}")
