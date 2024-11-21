from pathlib import Path
from pdf2image import convert_from_path

# Path to the PDF file
pdf_files = Path(".").rglob("hard/MS*.pdf")
# name is MS_1_2
for pdf_file in pdf_files:
    index = str(pdf_file).split("/")[-1].split(".")[0].split("_")[-1]
    pages = convert_from_path(pdf_file, 500)
    for i, page in enumerate(pages):
        page.save(f"hard_{index}.png", "PNG")

