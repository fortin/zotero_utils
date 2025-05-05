import csv
import shutil
from pathlib import Path

from decouple import config
from rapidfuzz import fuzz

# ========== SETTINGS ==========
pdf_dir = Path(config("PDF_FOLDER"))
review_dir = pdf_dir.parent / "to_review"
review_dir.mkdir(exist_ok=True)

unmatched_csv = Path("unmatched_pdfs.csv")
review_log = Path("logs/review_log.csv")

move_files = False  # Set True to MOVE instead of copying

# ========== LOAD UNMATCHED ==========
with unmatched_csv.open("r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    unmatched = list(reader)

# ========== FIND BEST MATCHES ==========
pdf_files = list(pdf_dir.glob("*.pdf"))
print(f"[✓] PDFs found: {len(pdf_files)}")
print(f"[✓] Unmatched items: {len(unmatched)}")


def normalize(text):
    return "".join(c.lower() for c in text if c.isalnum())


log_rows = []

for row in unmatched:
    title = row["Title"]
    key = row["Key"]
    n_title = normalize(title)
    best_score = 0
    best_pdf = None

    for pdf in pdf_files:
        n_pdf = normalize(pdf.stem)
        score = fuzz.partial_ratio(n_title, n_pdf)
        if score > best_score:
            best_score = score
            best_pdf = pdf

    if best_pdf and best_score >= 70:
        dest = review_dir / best_pdf.name
        if move_files:
            shutil.move(best_pdf, dest)
            action = "Moved"
        else:
            shutil.copy2(best_pdf, dest)
            action = "Copied"

        print(f"{action}: {best_pdf.name} (score {best_score}) for '{title[:60]}...'")
        log_rows.append(
            {
                "Key": key,
                "Title": title,
                "Matched PDF": best_pdf.name,
                "Score": best_score,
                "Action": action,
            }
        )
    else:
        print(f"❌ No good match (below 70%) for '{title[:60]}...'")
        log_rows.append(
            {
                "Key": key,
                "Title": title,
                "Matched PDF": "",
                "Score": "",
                "Action": "No match found",
            }
        )

# ========== WRITE REVIEW LOG ==========
with review_log.open("w", newline="", encoding="utf-8") as f:
    fieldnames = ["Key", "Title", "Matched PDF", "Score", "Action"]
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(log_rows)

print("\n✅ Review copies/moves completed.")
print(f"✔ Review log saved to {review_log}")
