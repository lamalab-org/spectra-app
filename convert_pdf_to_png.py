from pathlib import Path
from pdf2image import convert_from_path

# Path to the PDF file
pdf_files = Path(".").rglob("MS*.pdf")

for pdf_file in pdf_files:
    index = str(pdf_file).split(".pdf")[0]
    pages = convert_from_path(pdf_file, 500)
    for i, page in enumerate(pages):
        page.save(f"easy_{index}.png", "PNG")

