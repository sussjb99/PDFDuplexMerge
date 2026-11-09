# ============================================================
#  PDF Duplex Merge Tool - Deskew Diagnostic
#  File: pdf_deskew_diag.py
#  Version: 1.2 (Measures through the deskew engine rather than
#               reimplementing an estimator, so a diagnostic can
#               never disagree with the application)
#  Last Modified: 2026-11-09
#  Author: sussjb99
#  Support: https://ko-fi.com/sussjb99
#
#  Copyright (c) 2026 sussjb99.
#  Licensed under the GNU General Public License, version 3.0 or
#  later. See LICENSE.txt for the full license text.
#
#  Purpose: Report what the deskew engine would do to a PDF without
#           writing anything. Use it when a merged document looks
#           crooked and you want to know which pages are responsible.
#
#  Usage:
#           python pdf_deskew_diag.py input.pdf
#
#  For each page it prints the angle the engine measured, how sharp
#  that measurement was, whether the weak-signal or outlier guard
#  would override it, and the angle that would actually be applied.
# The legacy bounding-rectangle estimator is shown alongside as a
# comparison only; the application does not use it.
# ============================================================

import sys

import cv2
import numpy as np
from pdf2image import convert_from_path

from pdf_deskew import (
    ANALYSIS_MAX_DIM,
    DESKEW_DPI,
    MIN_INK_POINTS,
    MIN_ROTATE_ANGLE,
    OUTLIER_THRESHOLD,
    WEAK_PEAK_WIDTH,
    _binary_ink,
    detect_skew_angle_rect,
    measure_skew,
    resolve_poppler_path,
)


def decide_angle(raw_angle, peak_width, median_angle):
    """
    Reproduce the selection logic from deskew_pdf.

    Returns (applied_angle, reason). Kept separate so a diagnostic can
    show the decision without performing the rotation. If the rules in
    pdf_deskew.py change, this function has to change with them; that
    is the one place where a diagnostic can drift from the engine.
    """
    if peak_width > WEAK_PEAK_WIDTH:
        return median_angle, "weak signal"

    if abs(raw_angle - median_angle) > OUTLIER_THRESHOLD:
        return median_angle, "outlier"

    return raw_angle, "own angle"


def main():
    if len(sys.argv) != 2:
        print("Usage: python pdf_deskew_diag.py input.pdf")
        sys.exit(1)

    input_pdf = sys.argv[1]

    poppler_path = resolve_poppler_path()

    if not poppler_path:
        print("ERROR: could not locate pdftoppm.exe.")
        print("Set POPPLER_PATH, or keep tools/poppler beside the app.")
        sys.exit(1)

    pages = convert_from_path(
        input_pdf,
        dpi=DESKEW_DPI,
        poppler_path=poppler_path
    )

    if not pages:
        print(f"ERROR: no pages found in {input_pdf}")
        sys.exit(1)

    total = len(pages)

    raw_angles = []
    peak_widths = []
    ink_counts = []
    page_images = []

    print()
    print("=" * 72)
    print("DESKEW DIAGNOSTICS")
    print("=" * 72)
    print(f"File:                {input_pdf}")
    print(f"Poppler:             {poppler_path}")
    print(f"Output DPI:          {DESKEW_DPI}")
    print(f"Analysis resolution: {ANALYSIS_MAX_DIM} px")
    print(f"Weak peak above:     {WEAK_PEAK_WIDTH} degrees")
    print(f"Outlier beyond:      {OUTLIER_THRESHOLD} degrees")
    print()

    for index, page in enumerate(pages):
        image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

        angle, width = measure_skew(image)

        # Count ink on the same downscaled binary the engine measures
        # against, so this number is directly comparable to the
        # MIN_INK_POINTS threshold in pdf_deskew.py. A count below
        # MIN_INK_POINTS means measure_skew returned (0.0, 0.0)
        # through its early exit and the page has no measurable angle.
        ink = int((_binary_ink(image) > 0).sum())

        raw_angles.append(angle)
        peak_widths.append(width)
        ink_counts.append(ink)
        page_images.append(image)

        confident = width <= WEAK_PEAK_WIDTH

        print(
            f"Page {index + 1:02d}: "
            f"angle={angle:+6.2f}deg  "
            f"peak={width:4.1f}  "
            f"ink={ink:>7d}  "
            f"{'confident' if confident else 'WEAK'}"
        )

    #
    # Median taken only over decisive pages, matching the engine.
    #
    confident_angles = [
        angle
        for angle, width in zip(raw_angles, peak_widths)
        if width <= WEAK_PEAK_WIDTH
    ]

    median_angle = float(np.median(confident_angles)) if confident_angles else 0.0

    print()
    print(f"Document median angle: {median_angle:.2f} degrees")
    print()
    print("Angles that would be applied")
    print("-----------------------------")

    rotations = 0

    for index, (angle, width) in enumerate(zip(raw_angles, peak_widths), 1):
        applied, reason = decide_angle(angle, width, median_angle)

        rect = detect_skew_angle_rect(page_images[index - 1])

        if abs(applied) >= MIN_ROTATE_ANGLE:
            rotations += 1

        print(
            f"Page {index:02d}: "
            f"applied={applied:+6.2f}deg  ({reason})  "
            f"legacy rect={rect:+6.2f}"
        )

    print()
    print(f"Pages rotated:      {rotations} of {total}")
    print(f"Pages not rotated:  {total - rotations} (below {MIN_ROTATE_ANGLE} degrees)")


if __name__ == "__main__":
    main()
