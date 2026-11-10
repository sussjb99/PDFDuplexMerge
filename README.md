# PDF Duplex Merge Tool

Merge two single-sided PDF scans into a correctly ordered duplex PDF, with optional automatic deskewing.

A common workflow for non-duplex scanners is:

1. Scan all front sides.
2. Flip the stack.
3. Scan all back sides.
4. End up with two PDF files.

PDF Duplex Merge Tool combines those files into a single document with pages in the proper reading order and can automatically correct page skew before merging.

---

## Features

- Merge front and back scan PDFs into a single document
- Automatic page reordering
- Optional page deskewing
- Simple Windows GUI
- Standalone executable available (no Python required)
- Built-in Poppler support
- Open source under GPL v3

---

## How It Works

```text
Front PDF  ----+
               |  (1) Deskew pages (optional)
Back PDF   ----+  (2) Reverse back pages
               |  (3) Interleave pages
               |  (4) Create merged PDF
               v
          Output PDF
```

The tool assumes a typical manual duplex scanning workflow:

```text
Front PDF: 1, 3, 5, 7...

Back PDF:  8, 6, 4, 2...
```

The back pages are automatically reversed before interleaving.

Result:

```text
1, 2, 3, 4, 5, 6, 7, 8
```

---

## Screenshot

*Add a screenshot of the GUI here.*

```markdown
![PDF Duplex Merge Tool](docs/screenshot-main-window.png)
```

---

## Requirements

### Runtime

#### Packaged Version

- Windows 10 or Windows 11
- No Python required

#### Source Version

- Python 3.14+

### Python Dependencies

- PySide6
- pypdf
- pdf2image
- opencv-python
- numpy
- Pillow

### External Dependencies

- Poppler

---

## Running From Source

Create a fresh virtual environment on each machine.

```cmd
cd PDF_DuplexMerge

py -3.14 -m venv venv314

venv314\Scripts\pip install -r requirements.txt pyinstaller

venv314\Scripts\activate

python pdf_duplex_merge_gui.py
```

If the Python launcher is unavailable:

```cmd
python -m venv venv314
```

Command-line usage:

```cmd
python duplex_merge.py front.pdf back.pdf merged.pdf
```

Deskew only:

```cmd
python pdf_deskew.py input.pdf output.pdf
```

---

## Building the Portable Executable

```cmd
cd PDF_DuplexMerge

startenv.bat

packaging\build.bat
```

Output:

```text
dist\
└── PDFDuplexMerge\
    ├── PDFDuplexMerge.exe
    ├── _internal\
    ├── tools\
    ├── LICENSE.txt
    ├── README.md
    └── THIRD-PARTY-NOTICES.txt
```

The complete folder must remain together.

No Python installation is required on the destination machine.

---

## Using the Application

1. Select the Front PDF.
2. Select the Back PDF.
3. Choose the Output PDF.
4. Enable or disable Deskew.
5. Click **Start Merge**.
6. Wait for completion.
7. The merged PDF opens automatically.

---

## Limitations

Deskewing works by converting pages to images.

Because of this:

- OCR layers are lost
- Searchable text is lost
- Bookmarks are not preserved
- Metadata is not preserved
- Output files may be larger than the originals

If your scans are already straight, consider disabling deskew for best results.

---

## Project Structure

```text
PDF_DuplexMerge/
│
├── pdf_duplex_merge_gui.py
├── duplex_merge.py
├── pdf_deskew.py
├── pdf_deskew_diag.py
├── skew_probe.py
├── skew_crosscheck.py
│
├── packaging/
├── tools/
├── test_data/
├── output/
│
├── requirements.txt
├── LICENSE.txt
├── THIRD-PARTY-NOTICES.txt
└── README.md
```

---

## Troubleshooting

### "No module named PySide6"

Rebuild using the project's virtual environment.

### "Fatal error in launcher: Unable to create process"

Delete and recreate the virtual environment.

```cmd
rmdir /s /q venv314

py -3.14 -m venv venv314

venv314\Scripts\pip install -r requirements.txt pyinstaller
```

### "'py' is not recognized"

Use:

```cmd
python
```

instead of:

```cmd
py
```

or reinstall Python with the launcher enabled.

### Merge stalls during deskewing

Verify Poppler is available.

You can also set:

```text
POPPLER_PATH
```

to manually specify the Poppler location.

---

## Support the Project

If PDF Duplex Merge Tool saves you time, consider supporting development:

☕ **Ko-fi**

https://ko-fi.com/sussjb99

Support is entirely optional. The software will remain free and open source.

---

## License

Copyright © 2026 sussjb99

Licensed under:

**GNU General Public License v3.0 or later (GPL-3.0-or-later)**

See:

- LICENSE.txt
- https://www.gnu.org/licenses/

---

## Third-Party Components

| Component | License |
|------------|----------|
| Poppler | GPLv2 / GPLv3 |
| Qt / PySide6 | LGPL-3.0 |
| OpenCV | BSD-3-Clause |
| NumPy | BSD-3-Clause |
| Pillow | MIT |
| pypdf | BSD-3-Clause |
| pdf2image | MIT |

See `THIRD-PARTY-NOTICES.txt` for full details.
