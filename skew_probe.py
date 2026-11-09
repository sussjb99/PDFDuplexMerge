import numpy as np
import cv2
from pdf2image import convert_from_path

from pdf_deskew import (
    _binary_ink,
    _alignment_score,
    detect_skew_angle,
    detect_skew_angle_rect,
    resolve_poppler_path,
)


def full_res_peak(image):
    """Peak of the alignment score at full raster resolution."""
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)

    binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )[1]

    best = 0.0
    best_score = -1.0

    for angle in np.arange(-8.0, 8.05, 0.1):
        score = _alignment_score(binary, angle)

        if score > best_score:
            best_score, best = score, angle

    return best


def main():
    pages = convert_from_path(
        "test_data/Front.pdf",
        dpi=200,
        poppler_path=resolve_poppler_path()
    )

    for index, page in enumerate(pages, 1):
        image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

        small = _binary_ink(image)

        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        gray = cv2.bitwise_not(gray)

        full = cv2.threshold(
            gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
        )[1]

        scores = {
            angle: _alignment_score(small, angle)
            for angle in np.arange(-6.0, 6.05, 0.5)
        }

        peak = max(scores.values())

        print(f"Page {index}:")
        print(
            "  engine (800px) = "
            f"{detect_skew_angle(image):+.2f}  "
            "full-res = "
            f"{full_res_peak(image):+.2f}  "
            "rect = "
            f"{detect_skew_angle_rect(image):+.2f}"
        )
        print(
            "  score at peak = 1.00, "
            "others relative to it:"
        )

        for angle, score in scores.items():
            bar = "#" * int(score / peak * 20)
            print(f"    {angle:+5.1f}  {score / peak:5.2f}  {bar}")

        print()


if __name__ == "__main__":
    main()