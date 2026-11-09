# ============================================================
#  PDF Duplex Merge Tool - Deskew Engine
#  File: pdf_deskew.py
#  Version: 1.2 (Projection-profile skew detection with weak-signal
#              guard, frozen-executable aware poppler lookup,
#              expanded rotation canvas, optional progress callback)
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
#  Purpose: Correct page skew in a scanned PDF so that merged duplex
#           documents line up cleanly.
#
#  Pipeline:
#           PDF -> poppler raster (pdf2image) -> thresholded ink
#                 -> rotation search maximising row-ink alignment
#                 -> document median -> rotation -> PDF out (PIL)
#
#  IMPORTANT LIMITATION:
#           Deskewing is destructive. Pages are re-rendered as
#           bitmaps, so any embedded text layer, OCR searchability,
#           bookmarks and metadata are lost, and the output file is
#           larger. Use it only on genuinely skewed scans.
#
#  Requirements:
#           - poppler (pdf2image needs pdftoppm.exe on PATH or in a
#             bundled tools/poppler folder beside the executable)
#           - opencv-python
#           - numpy
#           - Pillow
#
#  Usage:
#           As a module:  from pdf_deskew import deskew_pdf
#           On the CLI:   python pdf_deskew.py input.pdf output.pdf
# ============================================================

import os
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np

from pdf2image import convert_from_path
from PIL import Image


# ----------------------------------------------------------------------
# Tuning constants
# ----------------------------------------------------------------------

# A page whose measured angle differs from the document median by
# more than this many degrees is treated as a measurement error and
# corrected to the median instead of its own value. Raise this if
# your scans legitimately contain differently rotated pages.
OUTLIER_THRESHOLD = 1.5

# Raster resolution used for the final page rendering. Higher is
# sharper but slower and produces a larger PDF.
DESKEW_DPI = 200

# Skew is measured on a downscaled copy of the page. The downscale
# has to stay large enough that individual text strokes survive the
# averaging. 800 px blurred fine detail into a flat plateau and
# produced a meaningless peak on page 4 of the test set; 1600 px
# resolves it, at roughly three seconds per page.
ANALYSIS_MAX_DIM = 1600

# Half-width of the angle search, in degrees. Raise to 15 if scans
# arrive rotated more than 10 degrees out of level.
MAX_SEARCH_ANGLE = 10.0

# Below this many ink pixels the page is too sparse (blank page,
# mostly white sheet) to measure a reliable angle.
MIN_INK_POINTS = 100

# A peak this wide means the page has no decisive line structure, so
# its own angle is no better than the document median.
WEAK_PEAK_WIDTH = 2.0

# Rotation smaller than this is ignored; it would only introduce
# resampling blur for no benefit.
MIN_ROTATE_ANGLE = 0.1

# Environment variable that can point at a poppler bin directory.
# Useful on machines where the bundled poppler is not wanted.
POPPLER_ENV_VAR = "POPPLER_PATH"

# Candidate poppler layouts, in the order they are searched.
# "Library/bin" is the layout of the Windows poppler release;
# "bin" is the plain Linux layout.
POPPLER_LAYOUTS = (
    ("tools", "poppler", "Library", "bin"),
    ("tools", "poppler", "bin"),
)


# ----------------------------------------------------------------------
# Locating poppler
# ----------------------------------------------------------------------

def app_root():
    r"""
    Return the directory the application is actually running from.

    In a PyInstaller --onedir bundle this is the folder holding the
    exe (and the tools\poppler folder copied beside it). In a
    --onefile bundle the data files are extracted to a temporary
    directory exposed as sys._MEIPASS. Running as a plain script uses
    the directory of this file.
    """
    if getattr(sys, "frozen", False):
        candidates = [Path(sys.executable).parent]

        # _MEIPASS only exists for --onefile builds. Path("")
        # evaluates to the current directory, so the attribute has to
        # be tested before it is turned into a Path.
        meipass = getattr(sys, "_MEIPASS", None)

        if meipass:
            candidates.append(Path(meipass))

        for candidate in candidates:
            if candidate.exists():
                return candidate

    return Path(__file__).parent


def resolve_poppler_path():
    """
    Find the poppler bin directory to hand to pdf2image.

    Preference order:
        1. POPPLER_PATH environment variable.
        2. A bundled tools/poppler folder in the application tree.
        3. A poppler found on the system PATH.
        4. None.

    Returns:
        Path string, or None.
    """
    env_path = os.environ.get(POPPLER_ENV_VAR)

    if env_path and Path(env_path).is_dir():
        return env_path

    root = app_root()

    for layout in POPPLER_LAYOUTS:
        candidate = root.joinpath(*layout)

        if candidate.is_dir():
            return str(candidate)

    found = shutil.which("pdftoppm")

    if found:
        return os.path.dirname(found)

    return None


def root_note():
    """Human-readable description of where poppler was searched."""
    root = app_root()

    return ", ".join(
        str(root.joinpath(*layout)) for layout in POPPLER_LAYOUTS
    )


# ----------------------------------------------------------------------
# Skew measurement
# ----------------------------------------------------------------------

def _binary_ink(image):
    """
    Return a thresholded, downscaled, black-ink-on-white image.

    The page is inverted so ink becomes the bright foreground, then
    shrunk to ANALYSIS_MAX_DIM. INTER_AREA averages pixel blocks
    during the shrink, so the result is re-binarised to keep the
    row profile crisp.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)

    binary = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )[1]

    h, w = binary.shape
    scale = ANALYSIS_MAX_DIM / max(h, w)

    if scale < 1.0:
        binary = cv2.resize(
            binary,
            (max(1, int(w * scale)), max(1, int(h * scale))),
            interpolation=cv2.INTER_AREA
        )
        binary = ((binary > 127) * 255).astype(np.uint8)

    return binary


def _alignment_score(binary, angle):
    """
    Row-ink variance of the page rotated by `angle` degrees.

    When text lines are horizontal each line lands on its own group
    of rows, so the profile of ink per row has sharp peaks and deep
    valleys and its variance is high. A tilted page smears the lines
    across rows and the variance drops. Maximising this score is
    therefore a direct measurement of page level.
    """
    h, w = binary.shape

    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)

    rotated = cv2.warpAffine(
        binary,
        matrix,
        (w, h),
        flags=cv2.INTER_NEAREST,
        borderValue=0
    )

    return float(np.var(rotated.sum(axis=1)))


def _peak_width(binary, angle):
    """
    Width, in degrees, of the region where the alignment score stays
    within 95% of its maximum.

    A narrow peak is a decisive measurement. A wide plateau means the
    page has no clear line structure and the reported angle is
    effectively a coin flip between grid points that all score about
    the same.
    """
    peak = _alignment_score(binary, angle)

    width = 0.0

    for direction in (-1, 1):
        probe = angle

        while abs(probe - angle) <= MAX_SEARCH_ANGLE:
            probe += direction * 0.1

            if _alignment_score(binary, probe) < 0.95 * peak:
                break

        width += abs(probe - angle)

    return float(width)


def measure_skew(image):
    """
    Return (angle_to_apply, peak_width_degrees) for one page.

    The angle is the rotation that makes the page level. The peak
    width describes how sharp the maximum was: small is good, and
    anything above WEAK_PEAK_WIDTH means the measurement should not
    be trusted on its own.

    Notes:
        - The angle is the rotation to apply, matching
          cv2.getRotationMatrix2D's convention directly. Unlike the
          older bounding-rectangle method there is no negation step.
        - A page rotated 180 degrees is indistinguishable from an
          upright one by any of these methods.
        - Cost is roughly ninety small rotations per page. Reduce
          ANALYSIS_MAX_DIM or MAX_SEARCH_ANGLE for very large books.
    """
    binary = _binary_ink(image)

    if int((binary > 0).sum()) < MIN_INK_POINTS:
        return 0.0, 0.0

    half = int(MAX_SEARCH_ANGLE * 2)

    coarse = max(
        range(-half, half + 1),
        key=lambda step: _alignment_score(binary, step / 2.0)
    )

    best = coarse / 2.0

    fine = max(
        np.arange(best - 0.5, best + 0.55, 0.1),
        key=lambda angle: _alignment_score(binary, angle)
    )

    angle = float(fine)

    return angle, _peak_width(binary, angle)


def detect_skew_angle(image):
    """Backwards-compatible wrapper returning only the angle."""
    return measure_skew(image)[0]


def detect_skew_angle_rect(image):
    """
    Legacy bounding-rectangle estimator, kept for diagnostics.

    It is fast, but it measures the outline of the ink rather than the
    alignment of the text lines, so an unusual ink distribution on a
    page can make it report an angle ninety degrees away from the real
    one. Compare it against the projection method with
    skew_crosscheck.py before relying on it.

    Returns:
        Signed angle in degrees, or 0.0 when the page is too sparse.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.bitwise_not(gray)

    thresh = cv2.threshold(
        gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU
    )[1]

    coords = np.column_stack(np.where(thresh > 0))

    if len(coords) < MIN_INK_POINTS:
        return 0.0

    angle = cv2.minAreaRect(coords)[-1]

    # minAreaRect returns angles in (-90, 0] on OpenCV < 4.5 and
    # [0, 90) on OpenCV >= 4.5. Normalise to (-45, 45].
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    return -angle


# ----------------------------------------------------------------------
# Correction
# ----------------------------------------------------------------------

def rotate_image(image, angle):
    """
    Rotate an image by `angle` degrees, keeping page dimensions.

    The rotation is performed onto a temporarily enlarged canvas so
    that no part of the page is clipped by the canvas edge, then
    cropped back to the original size from the centre. The earlier
    version's corners looked smeared because BORDER_REPLICATE
    duplicated edge pixels into the empty corner triangles; those
    corners are now filled with page white.

    Trade-off: content within roughly a corner-triangle of the page
    edge is trimmed away. For scans with normal margins this is not
    visible; for full-bleed scans, lower the rotation or skip
    deskewing.

    Args:
        image: OpenCV BGR numpy array.
        angle: Degrees to rotate.

    Returns:
        Rotated image with the same width and height as the input.
    """
    if abs(angle) < MIN_ROTATE_ANGLE:
        return image

    (h, w) = image.shape[:2]

    matrix = cv2.getRotationMatrix2D((w / 2.0, h / 2.0), angle, 1.0)

    # Bounding box of the rotated page.
    cos = abs(matrix[0][0])
    sin = abs(matrix[0][1])

    new_w = int(round(w * cos + h * sin))
    new_h = int(round(h * cos + w * sin))

    # Shift the rotation centre so the rotated content is centred
    # inside the enlarged canvas.
    matrix[0, 2] += (new_w - w) / 2.0
    matrix[1, 2] += (new_h - h) / 2.0

    rotated = cv2.warpAffine(
        image,
        matrix,
        (new_w, new_h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(255, 255, 255)
    )

    # Crop back to the original page size, centred, so every page in
    # the output has identical dimensions.
    x_offset = (new_w - w) // 2
    y_offset = (new_h - h) // 2

    return rotated[y_offset:y_offset + h, x_offset:x_offset + w]


def deskew_pdf(
    input_pdf,
    output_pdf,
    verbose=True,
    dpi=DESKEW_DPI,
    progress_callback=None
):
    """
    Deskew an entire PDF.

    Two passes are required: every page must be measured before the
    document median is known, and the median is what makes the
    outlier and weak-signal tests meaningful. Both page images are
    therefore held in memory. For very large scans, lower the DPI or
    process the front and back PDFs separately rather than the
    merged file.

    Args:
        input_pdf:  Path to the skewed PDF.
        output_pdf: Path to write the corrected PDF.
        verbose:    Print progress to stdout. The GUI passes False
                    and uses progress_callback instead.
        dpi:        Raster resolution of the output pages.
        progress_callback: Optional callable(percent, message) for
                    GUI progress reporting.

    Returns:
        Number of pages processed.

    Raises:
        RuntimeError: If no poppler binaries can be located.
        ValueError: If the PDF contains no pages.
        Exception: Propagated from OpenCV/PIL on unreadable input.
    """
    if verbose:
        print(f"Loading PDF: {input_pdf}")

    poppler_path = resolve_poppler_path()

    # Worth logging: in a packaged app this is the single most useful
    # diagnostic line, because "poppler not found" is the most common
    # way a portable build fails.
    if poppler_path:
        if verbose:
            print(f"Poppler: {poppler_path}")
    else:
        raise RuntimeError(
            "Could not find pdftoppm.exe. Keep the tools/poppler "
            "folder next to PDFDuplexMerge.exe, install poppler and "
            "put it on PATH, or set the POPPLER_PATH environment "
            f"variable to a poppler bin directory. Searched: {root_note()}"
        )

    pages = convert_from_path(
        input_pdf,
        dpi=dpi,
        poppler_path=poppler_path
    )

    if not pages:
        raise ValueError(f"No pages found in {input_pdf}")

    total = len(pages)

    page_images = []
    raw_angles = []
    peak_widths = []

    if verbose:
        print()
        print("Pass 1 - Measuring angles")
        print("-------------------------")

    for index, page in enumerate(pages):

        # pdf2image hands back PIL RGB images; OpenCV works in BGR.
        image = cv2.cvtColor(np.array(page), cv2.COLOR_RGB2BGR)

        angle, width = measure_skew(image)

        page_images.append(image)
        raw_angles.append(angle)
        peak_widths.append(width)

        if verbose:
            note = "  (weak signal)" if width > WEAK_PEAK_WIDTH else ""
            print(f"Page {index + 1}: {angle:.2f}°{note}")

        if progress_callback:
            percent = int((index + 1) * 50 / total)
            progress_callback(
                percent,
                f"Measured page {index + 1} ({angle:.2f}°)"
            )

    #
    # The median is taken only over pages that gave a decisive
    # measurement, so a page with no clear line structure cannot
    # pull the reference value toward it.
    #
    confident = [
        angle
        for angle, width in zip(raw_angles, peak_widths)
        if width <= WEAK_PEAK_WIDTH
    ]

    median_angle = float(np.median(confident)) if confident else 0.0

    if verbose:
        print()
        print(f"Document median angle: {median_angle:.2f}°")
        print()
        print("Pass 2 - Correcting pages")
        print("--------------------------")

    corrected_pages = []

    for index, image in enumerate(page_images):

        angle = raw_angles[index]

        #
        # Two reasons to fall back to the median:
        #
        #   1. Weak signal. The page has no sharp alignment peak, so
        #      its own angle is meaningless.
        #   2. Outlier. The page disagrees with the rest of the
        #      document by more than OUTLIER_THRESHOLD.
        #
        # Assumption behind (2): a page that disagrees with the rest
        # is a bad measurement, not a genuinely different orientation.
        # If your scans include rotated inserts or mixed-orientation
        # pages, raise OUTLIER_THRESHOLD or set it to a large number
        # to trust each page's own angle.
        #
        weak = peak_widths[index] > WEAK_PEAK_WIDTH

        if weak or abs(angle - median_angle) > OUTLIER_THRESHOLD:

            reason = "weak signal" if weak else "outlier"

            if verbose:
                print(
                    f"Page {index + 1}: {reason} "
                    f"({angle:.2f}°) using {median_angle:.2f}°"
                )

            angle = median_angle

        elif verbose:
            print(f"Page {index + 1}: using {angle:.2f}°")

        corrected = cv2.cvtColor(
            rotate_image(image, angle),
            cv2.COLOR_BGR2RGB
        )

        corrected_pages.append(Image.fromarray(corrected))

        if progress_callback:
            percent = 50 + int((index + 1) * 45 / total)
            progress_callback(percent, f"Corrected page {index + 1}")

    if verbose:
        print()
        print("Saving PDF...")

    #
    # PIL writes the first page and appends the rest. This produces an
    # image-only PDF with no text layer.
    #
    corrected_pages[0].save(
        output_pdf,
        save_all=True,
        append_images=corrected_pages[1:]
    )

    if verbose:
        print(f"Created: {output_pdf}")

    return len(corrected_pages)


def main():
    """Command line interface, kept for quick testing outside the GUI."""

    if len(sys.argv) != 3:
        print("Usage: python pdf_deskew.py input.pdf output.pdf")
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_pdf = sys.argv[2]

    try:
        page_count = deskew_pdf(input_pdf, output_pdf, verbose=True)
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}")
        sys.exit(1)

    print(f"Total Pages: {page_count}")


if __name__ == "__main__":
    main()