import sys
import os
import subprocess
import functools
import re
import ast
import logging
from PyQt6.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QTextEdit, QGroupBox, QHBoxLayout, QGridLayout, QLabel, QLineEdit
from PyQt6.QtCore import QThread, pyqtSignal, Qt
from PyQt6.QtWidgets import QSizePolicy
from pathlib import Path

logging.basicConfig(level=logging.INFO)

def extract_metadata(script_path):
    default_metadata = {"Author": "Unknown", "Version": "Unknown", "Description": "No description available", "Contributors": "Not specified"}
    metadata = default_metadata.copy()
    try:
        with open(script_path, "r", encoding="utf-8") as f:
            content = f.read()
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL) or re.search(r"'''(.*?)'''", content, re.DOTALL)
        if docstring_match:
            metadata["Description"] = docstring_match.group(1).strip().split("\n")[0]
        author_match = re.search(r'__author__\s*=\s*["\'](.*?)["\']', content)
        version_match = re.search(r'__version__\s*=\s*["\'](.*?)["\']', content)
        Contributors_match = re.search(r'__contributors__\s*=\s*(\[.*?\])', content, re.DOTALL)

        if author_match:
            metadata["Author"] = author_match.group(1)
        if version_match:
            metadata["Version"] = version_match.group(1)
        if Contributors_match:
            try:
                Contributors_list = ast.literal_eval(Contributors_match.group(1))
                if isinstance(Contributors_list, list):
                    metadata["Contributors"] = ", ".join(Contributors_list)
            except Exception:
                pass
    except Exception as e:
        logging.error(f"Error reading metadata from {script_path}: {e}")

    return metadata

def iter_python_scripts(directory):
    directory = Path(directory)
    grouped_scripts = {}

    for root, _, files in os.walk(directory):
        py_files = [f for f in files if f.endswith(".py") and f != Path(__file__).name]
        if not py_files:
            continue

        relative_root = Path(root).relative_to(directory)
        top_level_folder = relative_root.parts[0] if len(relative_root.parts) > 0 else "Root"

        if top_level_folder not in grouped_scripts:
            grouped_scripts[top_level_folder] = []

        grouped_scripts[top_level_folder].extend([str(Path(root) / f) for f in py_files])

    for folder, scripts in grouped_scripts.items():
        yield folder, sorted(scripts)

class ScriptRunner(QThread):
    output_signal = pyqtSignal(str)

    def __init__(self, script_path):
        super().__init__()
        self.script_path = script_path

    def run(self):
        process = subprocess.Popen([sys.executable, self.script_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        for line in stdout.splitlines():
            self.output_signal.emit(line.strip())
        for line in stderr.splitlines():
            self.output_signal.emit(line.strip())

class ScriptLauncher(QWidget):
    def __init__(self, script_dir="./"):
        super().__init__()
        self.setWindowTitle("HE2 Toolbox")
        self.resize(500, 200)
        self.move(QApplication.primaryScreen().geometry().center() - self.frameGeometry().center())

        self.layout = QVBoxLayout()

        self.main_layout = QHBoxLayout()

        self.script_layout = QVBoxLayout()
        self.script_groups = {}
        self.load_scripts(script_dir)
        self.main_layout.addLayout(self.script_layout, 1)

        self.output_box = QTextEdit()
        self.output_box.setReadOnly(True)
        self.output_box.setMinimumWidth(300)
        self.main_layout.addWidget(self.output_box, 1)

        self.layout.addLayout(self.main_layout)
        self.setLayout(self.layout)

    def load_scripts(self, directory):
        for folder, script_paths in iter_python_scripts(directory):
            group_box = QGroupBox(folder.upper())
            font = group_box.font()
            group_box.setFont(font)
            group_layout = QVBoxLayout()
            subcategories = {}
            for script_path in script_paths:
                relative_path = Path(script_path).relative_to(directory)
                subcategory = relative_path.parts[1] if len(relative_path.parts) > 1 else "Root"

                if subcategory not in subcategories:
                    subcategories[subcategory] = []

                subcategories[subcategory].append(script_path)

            for subcategory, scripts in subcategories.items():
                subcategory_group = QGroupBox(subcategory)
                subcategory_layout = QGridLayout()

                row, col = 0, 0
                for script_path in scripts:
                    button_text = os.path.splitext(os.path.basename(script_path))[0]
                    metadata = extract_metadata(script_path)
                    tooltip_text = f"Author: {metadata['Author']}\n Version: {metadata['Version']}\n {metadata['Description']}\n Contributors: {metadata['Contributors']}"

                    button = QPushButton(button_text)
                    font_metrics = button.fontMetrics()
                    text_width = font_metrics.horizontalAdvance(button_text) + 20
                    text_height = font_metrics.height() + 20
                    button.setMinimumSize(text_width, text_height)
                    button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
                    button.setToolTip(tooltip_text)
                    button.clicked.connect(functools.partial(self.run_script, script_path))
                    subcategory_layout.addWidget(button, row, col)
                    col += 1
                    if col >= 3:
                        col = 0
                        row += 1
                subcategory_group.setLayout(subcategory_layout)
                group_layout.addWidget(subcategory_group)

            group_box.setLayout(group_layout)
            self.script_layout.addWidget(group_box)

    def run_script(self, script_path):
        self.output_box.clear()
        if hasattr(self, 'runner') and self.runner.isRunning():
            self.runner.terminate()
        self.runner = ScriptRunner(script_path)
        self.runner.output_signal.connect(self.update_output)
        self.runner.start()

    def update_output(self, text):
        self.output_box.append(text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    launcher = ScriptLauncher()
    launcher.show()
    sys.exit(app.exec())
