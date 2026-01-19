---
name: pdf-processing
description: PyPDF2/pdf-lib PDF manipulation, coordinate transforms, form filling, merging, and text extraction. Use when working with PDF files, forms, or document processing.
---

# PDF Processing Skill

## Requirements
```bash
pip install pypdf pdfplumber reportlab PyPDF2
```

## Coordinate System
PDF coordinates start at **bottom-left** (0,0). Y increases upward.
```python
# Convert top-left coords to PDF coords
def to_pdf_coords(x, y, page_height):
    return (x, page_height - y)

# Get page dimensions
from pypdf import PdfReader
reader = PdfReader("doc.pdf")
page = reader.pages[0]
width = float(page.mediabox.width)   # typically 612 for letter
height = float(page.mediabox.height)  # typically 792 for letter
```

## Text Extraction
```python
# Using pdfplumber (best for tables)
import pdfplumber

with pdfplumber.open("doc.pdf") as pdf:
    for page in pdf.pages:
        text = page.extract_text()
        tables = page.extract_tables()

# Using PyPDF2
from PyPDF2 import PdfReader

reader = PdfReader("doc.pdf")
for page in reader.pages:
    text = page.extract_text()
```

## Merge PDFs
```python
from PyPDF2 import PdfMerger

merger = PdfMerger()
merger.append("doc1.pdf")
merger.append("doc2.pdf")
merger.write("merged.pdf")
merger.close()
```

## Split PDF
```python
from PyPDF2 import PdfReader, PdfWriter

reader = PdfReader("doc.pdf")
for i, page in enumerate(reader.pages):
    writer = PdfWriter()
    writer.add_page(page)
    writer.write(f"page_{i+1}.pdf")
```

## Create PDF with ReportLab
```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

c = canvas.Canvas("output.pdf", pagesize=letter)
width, height = letter

# Text (coords from bottom-left)
c.drawString(100, height - 100, "Hello World")

# Rectangle
c.rect(50, height - 200, 200, 50)

# Line
c.line(50, height - 250, 250, height - 250)

c.save()
```

## Form Filling
```python
from PyPDF2 import PdfReader, PdfWriter

reader = PdfReader("form.pdf")
writer = PdfWriter()

# Get form fields
fields = reader.get_fields()
print(fields.keys())

# Fill form
writer.append(reader)
writer.update_page_form_field_values(
    writer.pages[0],
    {"field_name": "value", "another_field": "another_value"}
)
writer.write("filled.pdf")
```

## PDF with Overlays (Watermarks)
```python
from PyPDF2 import PdfReader, PdfWriter

base = PdfReader("document.pdf")
overlay = PdfReader("watermark.pdf")
writer = PdfWriter()

for page in base.pages:
    page.merge_page(overlay.pages[0])
    writer.add_page(page)

writer.write("watermarked.pdf")
```

## Rotate Pages
```python
from PyPDF2 import PdfReader, PdfWriter

reader = PdfReader("doc.pdf")
writer = PdfWriter()

for page in reader.pages:
    page.rotate(90)  # 90, 180, 270
    writer.add_page(page)

writer.write("rotated.pdf")
```

## Extract Images
```python
from PyPDF2 import PdfReader

reader = PdfReader("doc.pdf")
for page in reader.pages:
    for image in page.images:
        with open(image.name, "wb") as f:
            f.write(image.data)
```

For form filling details, see [FORMS.md](FORMS.md).
For JavaScript pdf-lib operations, see [REFERENCE.md](REFERENCE.md).
