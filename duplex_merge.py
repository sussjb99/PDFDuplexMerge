# ============================================================
#  PDF Duplex Merge Tool - Merge Engine
#  File: duplex_merge.py
#  Version: 1.2 (Surplus-page handling, importable as a module)
#  Last Modified: 2026-11-08
#  Author: sussjb99
#  Support: https://ko-fi.com/sussjb99
#
#  Copyright (c) 2026 sussjb99.
#  Licensed under the GNU General Public License, version 3.0 or
#  later. See LICENSE.txt for the full license text.
#
#  This program is free software: you can redistribute it and/or
#  modify it under the terms of the GNU General Public License as
#  published by the Free Software Foundation, either version 3 of
#  the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
#  General Public License for more details.
#
#  Purpose: Engine module that pairs the front and back scan PDFs
#           produced by a duplex scanner into a single, correctly
#           ordered document.
#
#  Assumptions about the input:
#           - front.pdf holds the odd-numbered sides in reading
#             order (1, 3, 5, ...).
#           - back.pdf holds the even-numbered sides in REVERSE
#             order (n, n-2, ..., 2). This is how most duplex feed
#             scanners emit the reverse side, which is why the back
#             pages are reversed before interleaving.
#
#  Usage:
#           As a module:  from duplex_merge import merge_pdf_files
#           On the CLI:   python duplex_merge.py front.pdf back.pdf
#                                             output.pdf
# ============================================================

import sys

from pypdf import PdfReader
from pypdf import PdfWriter


def load_pages(pdf_path):
    """
    Read every page from a PDF into a plain list.

    The pages are returned as a list rather than the reader's lazy
    sequence so that the caller can reverse and slice it freely.

    Args:
        pdf_path: Path to the source PDF.

    Returns:
        List of pypdf Page objects, in document order.

    Raises:
        Exception: If the file is missing, unreadable, encrypted, or
            not a valid PDF. Callers are expected to handle this.
    """

    reader = PdfReader(pdf_path)

    return list(reader.pages)


def merge_pages(front_pages, back_pages):
    """
    Interleave front and back pages into reading order.

    The back list is reversed in place. This is safe because
    load_pages() returns a freshly built list each time, so no
    caller's data is affected.

    Args:
        front_pages: Odd sides, in order (1, 3, 5, ...).
        back_pages:  Even sides, in reverse order (n, n-2, ..., 2).

    Returns:
        A single list of pages ordered 1, 2, 3, 4, ...

    Note:
        If one side has more pages than the other, the unpaired
        remainder is appended at the end of the document. Both
        directions are handled - a longer back PDF is no longer
        silently discarded.
    """

    back_pages.reverse()

    paired = min(
        len(front_pages),
        len(back_pages)
    )

    merged = []

    for i in range(paired):

        merged.append(
            front_pages[i]
        )

        merged.append(
            back_pages[i]
        )

    #
    # Handle an unpaired remainder on either side. A sheet scanned
    # on only one side, or an extra front page at the end of the
    # stack, both land here.
    #

    if len(front_pages) > paired:

        merged.extend(
            front_pages[paired:]
        )

    elif len(back_pages) > paired:

        # back_pages has already been reversed, so this slice is
        # already in ascending page order.
        merged.extend(
            back_pages[paired:]
        )

    return merged


def save_pdf(
    pages,
    output_path
):
    """
    Write the merged page list to a new PDF file.

    Args:
        pages: List of pypdf Page objects.
        output_path: Destination file. Overwritten if it exists.

    Note:
        The pages still reference objects inside the original reader
        objects. pypdf resolves those references during write, so the
        source files must remain readable until this call completes.
    """

    writer = PdfWriter()

    for page in pages:

        writer.add_page(
            page
        )

    with open(
        output_path,
        "wb"
    ) as file:

        writer.write(
            file
        )


def merge_pdf_files(
    front_pdf,
    back_pdf,
    output_pdf
):
    """
    Merge front and back scan PDFs into a correctly ordered duplex
    PDF.

    This is the entry point used by pdf_duplex_merge_gui.py. The
    GUI expects an integer page count in return, so keep that
    contract if you change this function.

    Args:
        front_pdf: Path to the front-side scan.
        back_pdf:  Path to the back-side scan.
        output_pdf: Path to write the merged document.

    Returns:
        Number of pages written.

    Raises:
        Exception: Propagated from pypdf on unreadable or encrypted
            input. The GUI catches these and reports them to the user.
    """

    front_pages = load_pages(
        front_pdf
    )

    back_pages = load_pages(
        back_pdf
    )

    merged_pages = merge_pages(
        front_pages,
        back_pages
    )

    save_pdf(
        merged_pages,
        output_pdf
    )

    return len(
        merged_pages
    )


def main():
    """
    Command line interface, kept for quick testing outside the GUI.
    """

    if len(sys.argv) != 4:

        print(
            "Usage: "
            "python duplex_merge.py "
            "front.pdf "
            "back.pdf "
            "output.pdf"
        )

        sys.exit(1)

    front_pdf = sys.argv[1]
    back_pdf = sys.argv[2]
    output_pdf = sys.argv[3]

    print(
        f"Loading: {front_pdf}"
    )

    print(
        f"Loading: {back_pdf}"
    )

    try:

        page_count = merge_pdf_files(
            front_pdf,
            back_pdf,
            output_pdf
        )

    except Exception as exc:

        print(
            f"ERROR: {type(exc).__name__}: {exc}"
        )

        sys.exit(1)

    print(
        f"Created: {output_pdf}"
    )

    print(
        f"Total Pages: "
        f"{page_count}"
    )


if __name__ == "__main__":
    main()