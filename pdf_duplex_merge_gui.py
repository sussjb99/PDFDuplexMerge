# ============================================================
#  PDF Duplex Merge Tool
#  File: pdf_duplex_merge_gui.py
#  Version: 1.2 (Deskew-by-default, threaded pipeline, auto viewer,
#               projection-profile deskew engine with weak-signal guard)
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
#  Purpose: Front end for the duplex scan pipeline.
#           - Selects the front and back scan PDFs
#           - Deskews each side (OpenCV + pdf2image)
#           - Interleaves front/back pages into one duplex PDF
#           - Opens the result in the system's default PDF viewer
#
#  Modules used:
#           - duplex_merge.py   pypdf page interleaving
#           - pdf_deskew.py     OpenCV skew correction
# ============================================================

import os
import sys
import platform
import subprocess
import tempfile
import webbrowser
from pathlib import Path

from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QTextEdit,
    QProgressBar,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QStyleFactory,
    QMessageBox,
    QFrame,
    QCheckBox
)

from PySide6.QtCore import Qt, QThread, Signal


# ----------------------------------------------------------------------
# Project identity
# ----------------------------------------------------------------------

PROJECT_NAME = "PDF Duplex Merge Tool"
PROJECT_VERSION = "1.2"
AUTHOR = "sussjb99"
SUPPORT_URL = "https://ko-fi.com/sussjb99"


# ----------------------------------------------------------------------
# Engine imports. Importing the modules directly (rather than spawning
# them as subprocesses) keeps the activity log, progress bar and error
# handling under the GUI's control.
# ----------------------------------------------------------------------

MERGE_MODULE = "duplex_merge"
DESKEW_MODULE = "pdf_deskew"

try:
    from duplex_merge import merge_pdf_files
except ImportError as exc:
    merge_pdf_files = None
    MERGE_IMPORT_ERROR = str(exc)

try:
    from pdf_deskew import deskew_pdf
except ImportError as exc:
    deskew_pdf = None
    DESKEW_IMPORT_ERROR = str(exc)


def open_with_default_viewer(pdf_path):
    """
    Open the finished PDF in the system's default viewer.

    Returns:
        True if the launch succeeded, otherwise False.
    """
    path = Path(pdf_path)

    if not path.is_file() or path.stat().st_size == 0:
        return False

    try:
        if platform.system() == "Windows":
            os.startfile(str(path))
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])

        return True

    except Exception:
        return False


class PipelineWorker(QThread):
    """
    Runs the deskew + merge pipeline off the GUI thread so the window
    stays responsive and the progress bar actually moves.
    """

    progress = Signal(int, str)   # percent, message
    done = Signal(int, str)       # page count, output path
    failed = Signal(str)          # error message

    def __init__(self, front_path, back_path, output_path, deskew):
        super().__init__()
        self.front_path = front_path
        self.back_path = back_path
        self.output_path = output_path
        self.deskew = deskew
        self._stop = False

    def request_stop(self):
        self._stop = True

    def _stopped(self):
        if self._stop:
            self.progress.emit(0, "Cancelled.")
            return True
        return False

    def run(self):
        try:
            with tempfile.TemporaryDirectory(
                prefix="duplex_deskew_"
            ) as tmp_dir:
                front = self.front_path
                back = self.back_path

                if self.deskew:
                    self.progress.emit(5, "Deskewing front PDF...")

                    front_tmp = str(Path(tmp_dir) / "front_deskewed.pdf")
                    front_pages = deskew_pdf(
                        self.front_path,
                        front_tmp,
                        verbose=False
                    )
                    self.progress.emit(
                        25,
                        f"Front deskewed ({front_pages} pages)."
                    )

                    if self._stopped():
                        return

                    self.progress.emit(30, "Deskewing back PDF...")

                    back_tmp = str(Path(tmp_dir) / "back_deskewed.pdf")
                    back_pages = deskew_pdf(
                        self.back_path,
                        back_tmp,
                        verbose=False
                    )
                    self.progress.emit(
                        50,
                        f"Back deskewed ({back_pages} pages)."
                    )

                    if self._stopped():
                        return

                    front = front_tmp
                    back = back_tmp

                    if front_pages != back_pages:
                        self.progress.emit(
                            52,
                            f"Warning: side counts differ "
                            f"({front_pages} front vs {back_pages} back). "
                            f"Unpaired pages will not be merged."
                        )
                else:
                    self.progress.emit(10, "Reading PDFs...")

                self.progress.emit(60, "Merging front and back sides...")

                total_pages = merge_pdf_files(
                    front,
                    back,
                    self.output_path
                )

                self.progress.emit(100, "Merge complete.")
                self.done.emit(total_pages, self.output_path)

        except Exception as exc:
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class MainWindow(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setWindowTitle(PROJECT_NAME)
        self.resize(720, 500)

        self.worker = None

        self.build_ui()
        self.check_engines()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def create_path_row(self, callback):
        row = QHBoxLayout()

        edit = QLineEdit()
        edit.setReadOnly(True)

        button = QPushButton("...")
        button.setFixedWidth(30)
        button.setFixedHeight(24)

        button.clicked.connect(callback)

        row.addWidget(edit)
        row.addWidget(button)

        return row, edit

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        main_layout = QVBoxLayout()

        #
        # BLUE HEADER
        #

        header = QFrame()
        header.setStyleSheet(
            """
            background-color: #5B7DB1;
            color: white;
            """
        )

        header_layout = QVBoxLayout()

        title = QLabel(PROJECT_NAME)
        title.setStyleSheet(
            """
            font-weight:bold;
            font-size:14pt;
            color:white;
            """
        )

        subtitle = QLabel("Merge Duplex Scanned Documents")
        subtitle.setStyleSheet("color:white;")

        meta = QLabel(
            f"Version {PROJECT_VERSION}  ·  {AUTHOR}  ·  "
            "Copyright © 2026  ·  GPL-3.0-or-later"
        )
        meta.setStyleSheet(
            """
            color: #DCE6F2;
            font-size: 9pt;
            """
        )

        header_layout.addWidget(title)
        header_layout.addWidget(subtitle)
        header_layout.addWidget(meta)
        header.setLayout(header_layout)

        main_layout.addWidget(header)

        #
        # DOCUMENT SELECTION
        #

        docs_group = QGroupBox("Document Selection")
        docs_layout = QVBoxLayout()

        docs_layout.addWidget(QLabel("Front PDF"))
        front_row, self.front_edit = self.create_path_row(self.select_front)
        docs_layout.addLayout(front_row)

        docs_layout.addWidget(QLabel("Back PDF"))
        back_row, self.back_edit = self.create_path_row(self.select_back)
        docs_layout.addLayout(back_row)

        docs_layout.addWidget(QLabel("Output PDF"))
        output_row, self.output_edit = self.create_path_row(self.select_output)
        docs_layout.addLayout(output_row)

        docs_group.setLayout(docs_layout)
        main_layout.addWidget(docs_group)

        #
        # PROCESSING
        #

        process_group = QGroupBox("Processing")
        process_layout = QVBoxLayout()

        self.deskew_check = QCheckBox(
            "Deskew each side before merging"
        )
        self.deskew_check.setChecked(True)
        process_layout.addWidget(self.deskew_check)

        self.status_label = QLabel("Status: Ready")
        process_layout.addWidget(self.status_label)

        progress_row = QHBoxLayout()

        self.progress = QProgressBar()
        self.progress.setValue(0)

        self.percent_label = QLabel("0%")

        progress_row.addWidget(self.progress)
        progress_row.addWidget(self.percent_label)

        process_layout.addLayout(progress_row)

        buttons_row = QHBoxLayout()

        self.start_button = QPushButton("Start Merge")
        self.start_button.setFixedWidth(120)
        self.start_button.clicked.connect(self.start_merge)

        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setFixedWidth(100)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_merge)

        self.about_button = QPushButton("About")
        self.about_button.clicked.connect(self.show_about)

        self.support_button = QPushButton("Support")
        self.support_button.clicked.connect(self.show_support)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)

        buttons_row.addWidget(self.start_button)
        buttons_row.addWidget(self.cancel_button)
        buttons_row.addStretch()
        buttons_row.addWidget(self.about_button)
        buttons_row.addWidget(self.support_button)
        buttons_row.addWidget(self.close_button)

        process_layout.addLayout(buttons_row)

        process_group.setLayout(process_layout)
        main_layout.addWidget(process_group)

        #
        # ACTIVITY LOG
        #

        log_group = QGroupBox("Activity Log")
        log_layout = QVBoxLayout()

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumHeight(120)
        self.log.append("Ready.")

        log_layout.addWidget(self.log)
        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        central.setLayout(main_layout)

    # ------------------------------------------------------------------
    # ENGINE AVAILABILITY
    # ------------------------------------------------------------------

    def check_engines(self):
        missing = []

        if merge_pdf_files is None:
            missing.append(
                f"{MERGE_MODULE}.py ({MERGE_IMPORT_ERROR})"
            )

        if deskew_pdf is None:
            missing.append(
                f"{DESKEW_MODULE}.py ({DESKEW_IMPORT_ERROR})"
            )

        if missing:
            self.status_label.setText("Status: Missing engine modules")
            self.start_button.setEnabled(False)
            self.log.append(
                "Engine modules not importable from this folder:\n"
                + "\n".join(missing)
            )

    # ------------------------------------------------------------------
    # FILE SELECTORS
    # ------------------------------------------------------------------

    def select_front(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Front PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if path:
            self.front_edit.setText(path)
            self.log.append(f"Front PDF: {path}")

    def select_back(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Back PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if path:
            self.back_edit.setText(path)
            self.log.append(f"Back PDF: {path}")

    def select_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Select Output PDF",
            "",
            "PDF Files (*.pdf)"
        )

        if path:
            self.output_edit.setText(path)
            self.log.append(f"Output PDF: {path}")

    # ------------------------------------------------------------------
    # INPUT VALIDATION
    # ------------------------------------------------------------------

    def validate_inputs(self):
        front = self.front_edit.text().strip()
        back = self.back_edit.text().strip()
        output = self.output_edit.text().strip()

        problems = []

        if not front:
            problems.append("Front PDF is not selected.")
        elif not Path(front).is_file():
            problems.append(f"Front PDF not found: {front}")

        if not back:
            problems.append("Back PDF is not selected.")
        elif not Path(back).is_file():
            problems.append(f"Back PDF not found: {back}")

        if not output:
            problems.append("Output PDF is not selected.")
        elif not output.lower().endswith(".pdf"):
            problems.append("Output path must end with .pdf.")
        elif output in (front, back):
            problems.append(
                "Output path is the same as an input file - "
                "choose a different output."
            )

        if self.deskew_check.isChecked() and deskew_pdf is None:
            problems.append(
                f"Deskewing requested but {DESKEW_MODULE}.py is unavailable."
            )

        return problems

    # ------------------------------------------------------------------
    # RUN
    # ------------------------------------------------------------------

    def start_merge(self):
        if self.worker is not None and self.worker.isRunning():
            return

        problems = self.validate_inputs()

        if problems:
            self.log.append("Cannot start: " + " ".join(problems))
            QMessageBox.warning(self, "Input error", "\n".join(problems))
            return

        deskew = self.deskew_check.isChecked()

        self.progress.setValue(0)
        self.percent_label.setText("0%")
        self.status_label.setText("Status: Running")
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(True)

        self.log.append(
            f"Starting: {self.front_edit.text()} + "
            f"{self.back_edit.text()}"
            f"{'  (deskew on)' if deskew else ''} "
            f"-> {self.output_edit.text()}"
        )

        self.worker = PipelineWorker(
            self.front_edit.text().strip(),
            self.back_edit.text().strip(),
            self.output_edit.text().strip(),
            deskew
        )

        self.worker.progress.connect(self.on_progress)
        self.worker.done.connect(self.on_done)
        self.worker.failed.connect(self.on_failed)
        self.worker.start()

    def cancel_merge(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.status_label.setText("Status: Cancelling")

    def on_progress(self, percent, message):
        self.progress.setValue(percent)
        self.percent_label.setText(f"{percent}%")
        self.log.append(message)

    def on_done(self, page_count, output_path):
        self.status_label.setText("Status: Complete")
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        self.log.append(
            f"Created: {output_path} ({page_count} pages)"
        )

        QMessageBox.information(
            self,
            "Done",
            f"Merge complete.\n{page_count} pages written to\n{output_path}"
        )

        if open_with_default_viewer(output_path):
            self.status_label.setText(
                "Status: Complete - opened in PDF viewer"
            )
            self.log.append(
                f"Opening {output_path} in the default PDF viewer."
            )
        else:
            self.log.append(
                "Could not open the output PDF automatically. "
                "Open it manually."
            )

    def on_failed(self, message):
        self.status_label.setText("Status: Failed")
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)

        self.log.append(f"ERROR: {message}")

        QMessageBox.critical(
            self,
            "Merge failed",
            message
        )

    # ------------------------------------------------------------------
    # ABOUT / SUPPORT
    # ------------------------------------------------------------------

    def show_about(self):
        QMessageBox.about(
            self,
            "About",
            f"{PROJECT_NAME}\n"
            f"Version {PROJECT_VERSION}\n"
            f"by {AUTHOR}\n\n"
            f"Copyright (c) 2026 {AUTHOR}\n\n"
            "This program is free software, distributed under the GNU "
            "General Public License v3.0 or later.\n"
            "https://www.gnu.org/licenses/gpl-3.0.html\n\n"
            f"Support the development of this tool:\n{SUPPORT_URL}"
        )

    def show_support(self):
        QMessageBox.information(
            self,
            "Support",
            "If this tool saves you time, you can support its "
            f"development:\n\n{SUPPORT_URL}\n\n"
            "Support is entirely optional - the software remains "
            "free under the GNU GPL v3.0 or later."
        )

        webbrowser.open(SUPPORT_URL)

    def close(self):
        if self.worker is not None and self.worker.isRunning():
            self.worker.request_stop()
            self.worker.wait(3000)
        super().close()


def main():
    app = QApplication(sys.argv)

    #
    # IMPORTANT:
    # USE WINDOWS NATIVE CONTROL STYLE
    #

    app.setStyle(QStyleFactory.create("Windows"))

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()