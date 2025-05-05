import csv
from pathlib import Path

# ================= CONFIG =================
csv_path = Path("logs/pdf_match_log.csv")
output_path = Path("logs/pdf_match_log_fullpath.csv")

# Base folder where your PDFs are stored
pdf_base = Path("/Users/antonio/Dropbox/Documents/DocumentLibrary/BibDesk")

# ================= SCRIPT =================
rows = []

with csv_path.open("r", encoding="utf-8") as infile:
    reader = csv.DictReader(infile)
    for row in reader:
        pdf = row.get("PDF", "")
        if pdf and not pdf.startswith("/"):
            full_path = pdf_base / pdf
            row["PDF"] = str(full_path)
        rows.append(row)

with output_path.open("w", newline="", encoding="utf-8") as outfile:
    writer = csv.DictWriter(outfile, fieldnames=reader.fieldnames)
    writer.writeheader()
    writer.writerows(rows)

print(f"✅ CSV updated with full paths: {output_path}")
