# skew_crosscheck.py - measure any PDF and compare the two estimators.
# Usage: python skew_crosscheck.py path\to\file.pdf

import sys

import cv2
import numpy as np
from pdf2image import convert_from_path

from pdf_deskew import (
    ANALYSIS_MAX_DIM,
    WEAK_PEAK_WIDTH,
    detect_skew_angle_rect,
    measure_skew,
    resolve_poppler_path,
)


def main():
    if len(sys.argv) != 2:
        print("Usage: python skew_crosscheck.py <pdf>")
        sys.exit(1)

    pdf_path = sys.argv[1]

    pages = convert_from_path(
        pdf_path,
        dpi=200,
        poppler_path=resolve_poppler_path()
    )

    print(f"File: {pdf_path}")
    print(f"Analysis resolution: {ANALYSIS_MAX_DIM} px")
    print(f"Weak-signal threshold: {WEAK_PEAK_WIDTH} degrees")
    print()

    residuals = []

    for index, page in enumerate(pages, 1):
        image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

        angle, width = measure_skew(image)
        rect = detect_skew_angle_rect(image)

        flag = "WEAK" if width > WEAK_PEAK_WIDTH else "ok"

        residuals.append(abs(angle))

        print(
            f"Page {index}: engine={angle:+5.2f}  "
            f"peak={width:4.1f}  {flag:4}  "
            f"rect={rect:+5.2f}"
        )

    print()
    print(f"Mean residual: {np.mean(residuals):.2f} degrees")
    print(f"Max residual:  {np.max(residuals):.2f} degrees")


if __name__ == "__main__":
    main()