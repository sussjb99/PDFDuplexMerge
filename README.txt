============================================================
  PDF DUPLEX MERGE TOOL
============================================================

  Project:    PDF Duplex Merge Tool
  Version:    1.2
  Author:     sussjb99
  Copyright:  (c) 2026 sussjb99
  License:    GNU General Public License v3.0 or later
  Support:    https://ko-fi.com/sussjb99

  SPDX-License-Identifier: GPL-3.0-or-later


------------------------------------------------------------
1. WHAT THIS DOES
------------------------------------------------------------

A duplex scanner produces two separate PDFs: one for the front
side of each sheet and one for the back. This tool takes those
two files, corrects page skew, and produces a single PDF with
the pages in the correct reading order.

Pipeline:

    Front PDF  ----+
                   |  (1) deskew each side (optional)
    Back PDF   ----+  (2) interleave front/back pages
                   |  (3) write one merged PDF
                   v
              Output PDF

Page pairing assumes the usual duplex behaviour: the front PDF
contains the odd sides in order (1, 3, 5, ...) and the back PDF
contains the even sides in reverse order (n, n-2, ..., 2). The
back pages are reversed before interleaving to account for this.


------------------------------------------------------------
2. REQUIREMENTS
------------------------------------------------------------

Runtime:
    Windows 10 or 11, 64-bit
    Python 3.14 (only if running from source; the packaged app is
    self-contained and needs no Python at all)

Dependencies (see requirements.txt):
    PySide6        - GUI
    pypdf          - PDF merge
    pdf2image      - rasterise pages for skew analysis
    opencv-python  - skew detection
    numpy          - array operations
    Pillow         - PDF writing

Build-time only:
    pyinstaller    - produces the frozen executable

External binaries:
    poppler        - bundled in tools/poppler, or found on PATH


------------------------------------------------------------
3. RUNNING FROM SOURCE
------------------------------------------------------------

Set up ON EACH MACHINE. A virtual environment is not portable:
it records the absolute path of the Python it was created from,
so a venv folder copied from another computer will fail with
"Unable to create process" or build an executable that cannot
find its modules. Always create a fresh venv on the machine you
are building on.

    cd PDF_DuplexMerge
    py -3.14 -m venv venv314
    venv314\Scripts\pip install -r requirements.txt pyinstaller
    venv314\Scripts\activate
    python pdf_duplex_merge_gui.py

If "py" is not recognized, use "python" instead:

    python -m venv venv314

If neither works, Python 3.14 is not installed on that machine.
Install it from https://www.python.org/downloads/ and make sure
the "Add Python to PATH" box is checked during installation.

Command line alternatives:

    python duplex_merge.py front.pdf back.pdf merged.pdf
    python pdf_deskew.py  input.pdf  output.pdf


------------------------------------------------------------
4. BUILDING THE PORTABLE EXECUTABLE
------------------------------------------------------------

    cd PDF_DuplexMerge
    startenv.bat
    packaging\build.bat

The build script refuses to run unless venv314 exists and its
Python can import PySide6, pypdf, Pillow, numpy, OpenCV and
pdf2image, so it cannot quietly produce a broken executable from
a global Python installation. It also calls the venv's own
pyinstaller directly rather than whatever happens to be on PATH.

A successful build prints this line near the top:

    Dependencies OK - PySide6 6.12.0
    INFO: Python environment: ...\PDF_DuplexMerge\venv314

If that second line names a folder other than your venv, the
build is using the wrong interpreter and the resulting exe will
not run. See section 9.

Output lands in:

    dist\PDFDuplexMerge\
        PDFDuplexMerge.exe
        _internal\
        tools\poppler\
        LICENSE.txt
        README.txt
        THIRD-PARTY-NOTICES.txt

The whole folder is the application. Copy it, zip it, or install
it; the executable and _internal must remain in the same folder.

No Python is required on the machine that runs the exe.


------------------------------------------------------------
5. USING THE GUI
------------------------------------------------------------

1. Start the application.
2. Choose the Front PDF.
3. Choose the Back PDF.
4. Choose the Output PDF path.
5. Leave "Deskew each side before merging" checked unless the
   scans are already straight.
6. Click Start Merge.
7. When the Done dialog is acknowledged, the finished PDF opens
   in the system default viewer.

The activity log records every step, including which poppler
binary was used - that line is the first thing to check if a
build behaves differently on another machine.


------------------------------------------------------------
6. IMPORTANT LIMITATIONS
------------------------------------------------------------

Deskewing re-renders every page as an image. This means:

    - Any embedded text layer or OCR searchability is lost.
    - PDF metadata and bookmarks are not preserved.
    - The output file is larger than the input.

If your scans are already searchable, turn deskewing off.

Skew detection searches for the rotation that best aligns the rows
of ink on a page, over a window of plus or minus ten degrees. It
cannot detect pages that are rotated 180 degrees, and it will
report 0 degrees for blank pages. A page whose alignment peak is
too broad to be decisive - typically a page with no clear line
structure - is corrected to the document median instead of its own
measured angle.

Page counts are reported. If the front and back PDFs contain
different numbers of pages, the tool warns you before merging;
unpaired pages are appended at the end of the document.


------------------------------------------------------------
7. TUNING PARAMETERS
------------------------------------------------------------

In pdf_deskew.py:

    OUTLIER_THRESHOLD   1.5    degrees of deviation from the
                               document median before a page is
                               treated as a bad measurement

    DESKEW_DPI          200    raster resolution used for
                               analysis and output

    MIN_INK_POINTS      100    minimum ink pixels needed to
                               attempt an angle measurement

    ANALYSIS_MAX_DIM    1600   longest page dimension used for the
                               angle search. Pages are downscaled to
                               this before measuring; too small and
                               fine text detail blurs into a flat
                               plateau with no usable peak.

    WEAK_PEAK_WIDTH     2.0    degrees; a peak this wide means the
                               page has no decisive line structure,
                               so the document median is used

    MIN_ROTATE_ANGLE    0.1    degrees; smaller rotations are
                               skipped to avoid resampling blur

Environment variable:

    POPPLER_PATH        override the bundled poppler location


------------------------------------------------------------
8. PROJECT STRUCTURE
------------------------------------------------------------

    E:\PDF_DuplexMerge\
        pdf_duplex_merge_gui.py     GUI front end
        duplex_merge.py             merge engine
        pdf_deskew.py               deskew engine
        pdf_deskew_diag.py          skew diagnostic tool
        skew_probe.py               compares estimators at full and
                                    downscaled resolution
        skew_crosscheck.py          measures any PDF through the
                                    engine and reports residuals
        requirements.txt            dependency list
        LICENSE.txt                 GNU GPL-3.0
        README.txt                  this file
        startenv.bat                activate the venv
        packaging\                  build scripts
        tools\poppler\              bundled poppler
        test_data\                  sample Front.pdf / Back.pdf
        output\                     merged results
        dist\                       built executables


------------------------------------------------------------
9. TROUBLESHOOTING
------------------------------------------------------------

"No module named 'PySide6'" when the exe starts
    The build ran from a Python that did not have PySide6
    installed, usually a global install rather than the project
    venv. Look at the line "INFO: Python environment:" in the
    build log: it must point at your venv314 folder. Rebuild
    with startenv.bat run first. The bundle can also be checked
    directly - dist\PDFDuplexMerge\_internal should contain a
    PySide6 folder.

"Fatal error in launcher: Unable to create process"
    The venv was created on a different computer and copied over.
    Delete it and create a new one on this machine:

        rmdir /s /q venv314
        py -3.14 -m venv venv314
        venv314\Scripts\pip install -r requirements.txt pyinstaller

"'py' is not recognized"
    The Python launcher is not installed, or Python is not on
    PATH. Use "python" instead of "py", or reinstall Python with
    "Add Python to PATH" selected.

Window opens then closes immediately
    The Qt platform plugin is missing from the bundle. Rebuild
    and confirm the build log lists platforms\qwindows.dll.

Merge stalls during deskewing
    poppler is not being found. Check the activity log line that
    reports the poppler path, or set POPPLER_PATH.

Antivirus flags the executable
    Frozen Python binaries are frequently misflagged. Use the
    --onedir layout rather than --onefile, and keep the folder
    unpacked.

Output looks rotated the wrong way
    Verify the sign convention against your OpenCV version with
    pdf_deskew_diag.py on a known-skewed page.

Executable is very large
    The full PySide6 package includes Qt modules this tool never
    uses. Installing pyside6-essentials reduces the size.


------------------------------------------------------------
10. LICENSE
------------------------------------------------------------

This program is free software: you can redistribute it and/or
modify it under the terms of the GNU General Public License as
published by the Free Software Foundation, either version 3 of
the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program. If not, see
<https://www.gnu.org/licenses/>.

The full license text is in LICENSE.txt. The source code for this
program is distributed alongside the executable as
pdf_duplex_merge_gui.py, duplex_merge.py and pdf_deskew.py.


------------------------------------------------------------
11. THIRD-PARTY COMPONENTS
------------------------------------------------------------

This application bundles libraries under their own licenses:

    poppler           GPLv2/GPLv3   https://poppler.freedesktop.org
    Qt / PySide6      LGPL-3.0      https://www.qt.org/licensing
    OpenCV            BSD-3-Clause  https://opencv.org/license/
    NumPy             BSD-3-Clause  https://numpy.org/license.html
    Pillow            MIT-style     https://pillow.readthedocs.io
    pypdf             BSD-3-Clause  https://github.com/pypdf/pypdf
    pdf2image         MIT           https://github.com/bittner/pdf2image

Their notices must be preserved. The full details, including the
version of poppler bundled here and where its source code can be
obtained, are in THIRD-PARTY-NOTICES.txt.

The bundled poppler release carries its own licence texts under
tools/poppler/share/poppler/ (COPYING, COPYING.adobe, COPYING.gpl2).


------------------------------------------------------------
12. SUPPORT
------------------------------------------------------------

If this tool saves you time, you can support its development:

    https://ko-fi.com/sussjb99

Support is entirely optional; the software remains free under
the GNU GPL v3.0 or later.
============================================================