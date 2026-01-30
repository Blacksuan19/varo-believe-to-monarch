"""GUI application using PySide6 (Qt for Python)."""

import os
import sys
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import pandas as pd
from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .extractors import extract_transactions_from_pdf
from .processing import finalize_monarch
from .utils import default_workers, find_pdfs


class Worker(QObject):
    """Background worker for PDF processing."""

    progress = Signal(int, int, str)  # completed, total, status
    finished = Signal(str, str, int)  # result_msg, details, failures_count
    error = Signal(str)

    def __init__(
        self,
        folder: Path,
        output: Path,
        pattern: str,
        workers: int,
        include_file_names: bool,
    ):
        super().__init__()
        self.folder = folder
        self.output = output
        self.pattern = pattern
        self.workers = workers
        self.include_file_names = include_file_names
        self._is_running = True

    @Slot()
    def run(self):
        try:
            pdfs = find_pdfs(self.folder, self.pattern)
            total = len(pdfs)

            if total == 0:
                self.error.emit(
                    f"No PDFs found matching '{self.pattern}' in {self.folder}"
                )
                return

            self.progress.emit(0, total, f"Found {total} PDF(s). Processing...")

            frames = []
            failures = []
            completed = 0

            # Use ProcessPoolExecutor strictly within the thread
            # This is safe because QThread doesn't conflict with multiprocessing like Tkinter does
            with ProcessPoolExecutor(max_workers=self.workers) as ex:
                futs = {
                    ex.submit(extract_transactions_from_pdf, str(p)): p for p in pdfs
                }

                for fut in as_completed(futs):
                    if not self._is_running:
                        break

                    p = futs[fut]
                    try:
                        df = fut.result()
                        frames.append(df)
                        completed += 1
                        self.progress.emit(
                            completed,
                            total,
                            f"Processed: {p.name} ({len(df)} transactions)",
                        )
                    except Exception as e:
                        failures.append((str(p), repr(e)))
                        completed += 1
                        self.progress.emit(
                            completed, total, f"Error in {p.name}: {e!r}"
                        )

            if not self._is_running:
                return

            self.progress.emit(total, total, "Combining results...")
            combined = (
                pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
            )
            result = finalize_monarch(combined, self.include_file_names)

            if result.empty:
                self.error.emit("No transactions extracted from PDFs")
                return

            self.progress.emit(total, total, "Saving CSV file...")
            result.to_csv(self.output, index=False)

            msg = f"✓ Successfully converted {len(result)} transactions"
            details = f"Saved to: {self.output}"
            if failures:
                details += f"\n\n⚠ {len(failures)} file(s) failed."

            self.finished.emit(msg, details, len(failures))

        except Exception as e:
            self.error.emit(f"Critical error: {e!r}")

    def stop(self):
        self._is_running = False


class VaroToMonarchGUI(QMainWindow):
    """Main GUI window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Varo to Monarch Converter")
        self.setGeometry(100, 100, 700, 500)

        # Main widget & layout
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title
        title = QLabel("Varo to Monarch Converter")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        # Input Folder
        input_group = QGroupBox("Input")
        input_layout = QGridLayout(input_group)
        input_layout.addWidget(QLabel("PDF Folder:"), 0, 0)
        self.folder_input = QLineEdit()
        input_layout.addWidget(self.folder_input, 0, 1)
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        input_layout.addWidget(browse_btn, 0, 2)
        layout.addWidget(input_group)

        # Output File
        output_group = QGroupBox("Output")
        output_layout = QGridLayout(output_group)
        output_layout.addWidget(QLabel("CSV File:"), 0, 0)
        self.output_input = QLineEdit()
        self.output_input.setPlaceholderText("Auto-generated")
        output_layout.addWidget(self.output_input, 0, 1)
        save_btn = QPushButton("Save As...")
        save_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(save_btn, 0, 2)
        layout.addWidget(output_group)

        # Advanced Options
        self.advanced_check = QCheckBox("Show Advanced Options")
        self.advanced_check.toggled.connect(self._toggle_advanced)
        layout.addWidget(self.advanced_check)

        self.advanced_group = QGroupBox("Advanced Options")
        self.advanced_group.setVisible(False)
        adv_layout = QGridLayout(self.advanced_group)

        adv_layout.addWidget(QLabel("Pattern:"), 0, 0)
        self.pattern_input = QLineEdit("*.pdf")
        adv_layout.addWidget(self.pattern_input, 0, 1)

        adv_layout.addWidget(QLabel("Workers:"), 1, 0)
        self.workers_input = QLineEdit(str(default_workers()))
        adv_layout.addWidget(self.workers_input, 1, 1)

        self.include_file_names_check = QCheckBox("Include file names column")
        self.include_file_names_check.setChecked(True)
        adv_layout.addWidget(self.include_file_names_check, 2, 0, 1, 2)

        layout.addWidget(self.advanced_group)
        self.status_label = QLabel("Ready")
        layout.addWidget(self.status_label)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)

        # Action Button
        self.convert_btn = QPushButton("Convert to Monarch CSV")
        self.convert_btn.setMinimumHeight(50)
        self.convert_btn.setStyleSheet("font-size: 16px; font-weight: bold;")
        self.convert_btn.clicked.connect(self._start_conversion)
        layout.addWidget(self.convert_btn)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select PDF Folder")
        if folder:
            self.folder_input.setText(folder)
            if not self.output_input.text():
                default_out = Path(folder) / "varo_monarch_combined.csv"
                self.output_input.setText(str(default_out))

    def _browse_output(self):
        file, _ = QFileDialog.getSaveFileName(
            self, "Save CSV As", "", "CSV Files (*.csv);;All Files (*)"
        )
        if file:
            self.output_input.setText(file)

    def _toggle_advanced(self, checked):
        self.advanced_group.setVisible(checked)

    def _start_conversion(self):
        folder_str = self.folder_input.text().strip()
        if not folder_str:
            QMessageBox.critical(self, "Error", "Please select a PDF folder.")
            return

        folder = Path(folder_str)
        if not folder.exists():
            QMessageBox.critical(self, "Error", "Selected folder does not exist.")
            return

        output_str = self.output_input.text().strip()
        if not output_str:
            output = folder / "varo_monarch_combined.csv"
            self.output_input.setText(str(output))
        else:
            output = Path(output_str)

        try:
            pattern = self.pattern_input.text().strip() or "*.pdf"
            workers = int(self.workers_input.text().strip())
        except ValueError:
            QMessageBox.critical(self, "Error", "Workers must be a number.")
            return

        # Disable UI
        self.convert_btn.setEnabled(False)
        self.convert_btn.setText("Converting...")
        self.status_label.setText("Starting...")
        self.progress_bar.setValue(0)

        # Setup Thread and Worker
        self.thread = QThread()
        self.worker = Worker(
            folder,
            output,
            pattern,
            workers,
            self.include_file_names_check.isChecked(),
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.progress.connect(self._on_progress)

        # Cleanup signals
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker.error.connect(self.thread.quit)
        self.worker.error.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)

        self.thread.start()

    @Slot(int, int, str)
    def _on_progress(self, current, total, status):
        self.status_label.setText(status)
        if total > 0:
            self.progress_bar.setValue(int((current / total) * 100))

    @Slot(str, str, int)
    def _on_finished(self, msg, details, failures):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("Convert to Monarch CSV")
        self.progress_bar.setValue(100)

        # Update status label with result instead of popup
        status_text = msg
        if failures > 0:
            status_text += f" (⚠ {failures} files failed)"
        self.status_label.setText(status_text)

    @Slot(str)
    def _on_error(self, err_msg):
        self.convert_btn.setEnabled(True)
        self.convert_btn.setText("Convert to Monarch CSV")
        self.status_label.setText("Error")
        QMessageBox.critical(self, "Error", err_msg)


def main():
    """Launch the GUI application."""
    # Force usage of xdg-desktop-portal on Linux.
    # This ensures we get the native system file picker (KDE/Gnome) instead of the Qt internal one,
    # and improves theme integration when using pip-installed PySide6.
    if sys.platform == "linux" and "QT_QPA_PLATFORMTHEME" not in os.environ:
        os.environ["QT_QPA_PLATFORMTHEME"] = "xdgdesktopportal"

    app = QApplication(sys.argv)

    window = VaroToMonarchGUI()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
