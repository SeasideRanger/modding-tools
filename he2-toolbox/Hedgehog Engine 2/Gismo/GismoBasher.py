"""Gismo generator and template editor for KnuxTools"""
__author__ = "SeasideRanger"
__version__ = "1.5.3"
__contributors__ = ["Skyth", "Knuxfan24"]

import sys
import os
import re
import json
import subprocess
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QToolBar, QWidget, QVBoxLayout,
    QLineEdit, QComboBox, QStyledItemDelegate, QLabel, QPushButton,
    QHBoxLayout, QDialog, QSpinBox, QTextEdit, QWidgetAction, QSizePolicy
)
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtCore import Qt
from PyQt6.QtCore import QSettings
from pathlib import Path
import shutil

BASE_DIR       = Path(__file__).resolve().parent
SETTINGS_FILE  = BASE_DIR / 'settings.json'
TEMPLATES_DIR  = BASE_DIR / 'templates'

ENUM_MAP = {
    ('Design', 'Collision', 'Shape'): ['Box', 'Sphere', 'Capsule', 'Cylinder', 'Mesh', 'None'],
    ('Design', 'Collision', 'BasePoint'): ['Centre', 'ZPlane', 'XPlane', 'YPlane'],
    ('Design', 'RigidBody', 'Type'): ['None', 'Static', 'Dynamic'],
    ('Design', 'RigidBody', 'Material'): ['None', 'Wood', 'Iron'],
    ('ProgramMotion', 'Type'): ['Swing', 'Rotate', 'LinearSwing'],
    ('Kill', 'Type'): ['None', 'Kill', 'Break', 'Motion'],
    ('Plan', 'ContactDamageType'): ['None', 'LowSpeed', 'MiddleSpeed', 'HighSpeed'],
}
BOOLEAN_ENUM = ['true', 'false']

class EnumDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        opts = index.data(Qt.ItemDataRole.UserRole + 1)
        if isinstance(opts, list):
            cb = QComboBox(parent)
            cb.addItems(opts)
            return cb
        return super().createEditor(parent, option, index)
    def setEditorData(self, editor, index):
        if isinstance(editor, QComboBox):
            current = index.data(Qt.ItemDataRole.DisplayRole)
            idx = editor.findText(current)
            editor.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            super().setEditorData(editor, index)
    def setModelData(self, editor, model, index):
        if isinstance(editor, QComboBox):
            model.setData(index, editor.currentText(), Qt.ItemDataRole.EditRole)
        else:
            super().setModelData(editor, model, index)

class JsonEditor(QMainWindow):
    def __init__(self):

        self.settings = QSettings("GismoBasher")
        self.exe_path = ""
        self.load_settings()

        super().__init__()
        self.setWindowTitle("GismoBasher")
        self.resize(800, 600)

        self.current_file = None

        toolbar = QToolBar()
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for name, handler in [
            ("Open JSON", self.open_file),
            ("Save JSON", self.save_as_file)
        ]:
            act = QAction(name, self)
            act.triggered.connect(handler)
            toolbar.addAction(act)

        select_model_action = QAction("Select .model", self)
        select_model_action.triggered.connect(self.select_model_file)
        toolbar.addAction(select_model_action)

        generate_template_action = QAction("Load Template:", self)
        generate_template_action.triggered.connect(self.generate_template)
        toolbar.addAction(generate_template_action)

        self.template_selector = QComboBox()
        self.refresh_template_list()
        template_selector_action = QWidgetAction(self)
        template_selector_action.setDefaultWidget(self.template_selector)
        toolbar.addAction(template_selector_action)
        toolbar.addSeparator()

        path_label = QLabel("Path to KnuxTools:")
        self.path_input = QLineEdit(self.exe_path)
        self.path_input.setPlaceholderText("Enter path to KnuxTools")
        path_browse_button = QPushButton("Browse")
        path_browse_button.clicked.connect(self.select_path)

        path_widget = QWidget()
        path_layout = QHBoxLayout(path_widget)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.addWidget(path_label)
        path_layout.addWidget(self.path_input)
        path_layout.addWidget(path_browse_button)

        path_action = QWidgetAction(self)
        path_action.setDefaultWidget(path_widget)
        toolbar.addAction(path_action)

        toolbar.setFixedWidth(1000)

        for action in toolbar.actions():
            widget = toolbar.widgetForAction(action)
            if widget:
                widget.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
                widget.setMaximumHeight(30)

        side_panel = QWidget()
        side_layout = QVBoxLayout(side_panel)
        side_layout.setContentsMargins(5,5,5,5)

        side_layout.addWidget(QLabel("Output:"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        side_layout.addWidget(self.log_output)
        side_layout.addStretch()

        for button in side_panel.findChildren(QPushButton):
            font_metrics = button.fontMetrics()
            text_width = font_metrics.horizontalAdvance(button.text()) + 20  # Add padding
            text_height = font_metrics.height() + 20  # Add padding
            button.setMinimumSize(text_width, text_height)

        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search keys or values...")
        self.search_bar.textChanged.connect(self.filter_items)

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Key", "Value"])
        self.tree.header().setSectionResizeMode(0, self.tree.header().ResizeMode.Stretch)
        self.tree.header().setSectionResizeMode(1, self.tree.header().ResizeMode.Stretch)
        self.tree.setAlternatingRowColors(True)
        self.tree.setUniformRowHeights(True)
        self.tree.setAnimated(True)
        self.tree.setItemDelegateForColumn(1, EnumDelegate())

        central = QWidget()
        main_layout = QHBoxLayout(central)
        main_layout.setContentsMargins(5,5,5,5)
        bottom_panel = QWidget()
        bottom_layout = QVBoxLayout(bottom_panel)
        bottom_layout.setContentsMargins(0, 0, 0, 0)
        bottom_layout.addWidget(self.search_bar)
        bottom_layout.addWidget(self.tree, 4)
        bottom_layout.addWidget(QLabel("Output:"))
        bottom_layout.addWidget(self.log_output, 1)
        main_layout.addWidget(bottom_panel, 1)
        self.setCentralWidget(central)

    def log(self, message):
        self.log_output.append(message)

    def save_settings(self):
        self.settings.setValue("exe_path", self.exe_path)
        with open(SETTINGS_FILE, 'w') as f:
            json.dump({
                "exe_path": self.exe_path
            }, f, indent=2)

    def load_settings(self):
        if os.path.exists(SETTINGS_FILE):
            with open(SETTINGS_FILE, 'r') as f:
                s = json.load(f)
                self.exe_path   = os.path.normpath(s.get("exe_path", ""))

    def refresh_template_list(self):
        self.template_selector.clear()
        TEMPLATES_DIR.mkdir(exist_ok=True)
        for fn in TEMPLATES_DIR.iterdir():
            if fn.suffix == '.json' and fn.name != 'template_brk.hedgehog.bulletskeleton.json':
                display = fn.stem.replace('.hedgehog.gismo_rangers','')
                self.template_selector.addItem(display, fn)
        if self.template_selector.count():
            self.template_selector.setCurrentIndex(0)

    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Open JSON File", "", "JSON Files (*.json)")
        if not path:
            return
        self.current_file = path
        try:
            data = json.load(open(path))
            self.populate_tree(data)
            self.log(f"Loaded {path}")
        except Exception as e:
            self.log(f"ERROR: Failed to load JSON: {e}")

    def save_as_file(self):
        default = os.path.join(os.getcwd(), "template.hedgehog.gismo_rangers.json")
        path, _ = QFileDialog.getSaveFileName(self, "Save As JSON", default, "*.hedgehog.gismo_rangers.json;;All Files (*)")
        if not path:
            return
        if not path.lower().endswith('.hedgehog.gismo_rangers.json'):
            path += '.hedgehog.gismo_rangers.json'
        data = self.tree_to_data(self.tree.invisibleRootItem())
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
            self.current_file = path
            self.log(f"Saved As: {path}")
        except Exception as e:
            self.log(f"ERROR: Failed to Save As: {e}")

    def populate_tree(self, data):
        self.tree.clear()
        def walk(parent, value, path=()):
            parent.setFlags(parent.flags() | Qt.ItemFlag.ItemIsEditable)
            if isinstance(value, dict):
                parent.setData(0, Qt.ItemDataRole.UserRole, 'dict')
                for k, v in value.items():
                    child = QTreeWidgetItem(parent)
                    child.setText(0, k)
                    walk(child, v, path + (k,))
            elif isinstance(value, list):
                parent.setData(0, Qt.ItemDataRole.UserRole, 'list')
                for i, v in enumerate(value):
                    child = QTreeWidgetItem(parent)
                    child.setText(0, str(i))
                    walk(child, v, path + (str(i),))
            else:
                parent.setData(0, Qt.ItemDataRole.UserRole, 'value')
                if isinstance(value, bool):
                    txt = 'true' if value else 'false'
                elif value is None:
                    txt = ''
                else:
                    txt = str(value)
                parent.setText(1, txt)
                # enum choices
                for kp, opts in ENUM_MAP.items():
                    if len(kp) == len(path) and path[-len(kp):] == kp:
                        parent.setData(1, Qt.ItemDataRole.UserRole+1, opts)
                # boolean enum
                if txt in BOOLEAN_ENUM:
                    parent.setData(1, Qt.ItemDataRole.UserRole+1, BOOLEAN_ENUM)

        walk(self.tree.invisibleRootItem(), data)
        self.tree.collapseAll()
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            self.tree.expandItem(root.child(i))
        self.log("Template loaded.")

    def filter_items(self, text):
        txt = text.lower()
        def recurse(item):
            ok = txt in item.text(0).lower() or txt in item.text(1).lower()
            vis = ok
            for i in range(item.childCount()):
                if recurse(item.child(i)):
                    vis = True
            item.setHidden(not vis)
            return vis
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            recurse(root.child(i))

    def tree_to_data(self, item):
        t = item.data(0, Qt.ItemDataRole)
        if t == 'dict':
            data = {}
            for i in range(item.childCount()):
                child = item.child(i)
                data[child.text(0)] = self.tree_to_data(child)
            return data
        if t == 'list':
            elems = []
            for i in range(item.childCount()):
                child = item.child(i)
                key = int(child.text(0))
                elems.append((key, self.tree_to_data(child)))
            elems.sort(key=lambda x: x[0])
            return [v for _, v in elems]
        txt = item.text(1)
        if txt == '':
            return None
        try:
            return json.loads(txt)
        except:
            return txt

    def model_name_generator(self, obj, name):
        if isinstance(obj, dict):
            new_dict = {}
            for k, v in obj.items():
                if k == "Mesh" and isinstance(v, str) and v == "{model_name}":
                    new_dict[k] = f"{name}_col"
                else:
                    new_dict[k] = self.model_name_generator(v, name)
            return new_dict

        if isinstance(obj, list):
            return [self.model_name_generator(v, name) for v in obj]

        if isinstance(obj, str) and "{model_name}" in obj:
            return obj.replace("{model_name}", name)

        return obj

    def generate_template(self):
        idx = self.template_selector.currentIndex()
        if idx < 0:
            self.log(" No template selected.")
            return
        real = self.template_selector.itemData(idx)
        path = TEMPLATES_DIR / real
        if not path.is_file():
            self.log(f"Missing template: {real}")
            return
        try:
            data = json.load(open(path))
            self.populate_tree(data)
            self.current_file = None
            self.log(f"Loaded template “{self.template_selector.currentText()}”")
        except Exception as e:
            self.log(f"ERROR: Failed to load template: {e}")

    def select_model_file(self):
        mpaths, _ = QFileDialog.getOpenFileNames(
            self, "Select .model Files", "", "Model Files (*.model)"
        )
        if not mpaths:
            return
        brk_groups = {}
        normal_models = []
        for mpath in mpaths:
            model_path = Path(mpath)
            name = model_path.stem
            m = re.match(r'^(.+)_brk([A-Z])$', name)
            if m:
                prefix = m.group(1)
                letter = m.group(2)
                brk_groups.setdefault(prefix, set()).add(letter)
            else:
                normal_models.append(model_path)
        brk_template_path = TEMPLATES_DIR / "template_brk.hedgehog.bulletskeleton.json"
        if brk_groups and not brk_template_path.is_file():
            self.log("Missing template_brk.hedgehog.bulletskeleton.json in templates directory")

        for prefix, letters in brk_groups.items():
            try:
                full_list = json.load(open(brk_template_path))
            except Exception as e:
                self.log(f"ERROR loading bulletskeleton template: {e}")
                continue
            filtered = []
            for node in full_list:
                node_name = node.get("NodeName", "")
                if re.fullmatch(r'\{model_name\}_brk', node_name):
                    filtered.append(node)
                    continue
                m2 = re.fullmatch(r'\{model_name\}_brk([A-Z])__01', node_name)
                if m2 and m2.group(1) in letters:
                    filtered.append(node)
                    continue
            replaced_list = [self.model_name_generator(node, prefix) for node in filtered]
            sample_model = next(mp for mp in mpaths if Path(mp).stem.startswith(prefix + "_brk"))
            model_dir = Path(sample_model).parent
            out_brk_json = model_dir / f"{prefix}_brk.hedgehog.bulletskeleton.json"

            try:
                with open(out_brk_json, 'w') as bf:
                    json.dump(replaced_list, bf, indent=2)
                self.log(f"Wrote bulletskeleton: {out_brk_json.name}")
            except Exception as e:
                self.log(f"ERROR writing bulletskeleton JSON for {prefix}_brk: {e}")
                continue

            exe_path = Path(self.exe_path)
            exe_dir  = exe_path.parent
            if not exe_path.is_file():
                self.log("Executable path not set or invalid (for bulletskeleton).")
                continue
            try:
                result = subprocess.run(
                    [str(exe_path), str(out_brk_json)],
                    cwd=str(exe_dir),
                    capture_output=True,
                    text=True
                )
                self.log(f"[bulletskel EXE stdout]\n{result.stdout.strip()}")
                if result.stderr:
                    self.log(f"[bulletskel EXE stderr]\n{result.stderr.strip()}")
            except Exception as e:
                self.log(f"ERROR running EXE on {out_brk_json.name}: {e}")
                continue
            for f in exe_dir.iterdir():
                if f.stem == f"{prefix}_brk" and f.suffix.lower() != '.json':
                    try:
                        dest = model_dir / f.name
                        shutil.move(str(f), str(dest))
                        self.log(f"Created (bulletskel): {dest.name}")
                    except Exception as e:
                        self.log(f"ERROR moving bulletskeleton output {f.name}: {e}")

        for model_path in normal_models:
            model_dir  = model_path.parent
            name       = model_path.stem
            out_json = model_dir / f"{name}.hedgehog.gismo_rangers.json"
            data = self.model_name_generator(
                self.tree_to_data(self.tree.invisibleRootItem()), name
            )
            try:
                with open(out_json, 'w') as f:
                    json.dump(data, f, indent=2)
                self.log(f"Wrote {out_json.name}")
            except Exception as e:
                self.log(f"ERROR writing gismo_rangers JSON: {e}")
                continue
            exe_path = Path(self.exe_path)
            exe_dir  = exe_path.parent
            if not exe_path.is_file():
                self.log("Executable path not set or invalid.")
            else:
                result = subprocess.run(
                    [str(exe_path), str(out_json)],
                    cwd=str(exe_dir),
                    capture_output=True,
                    text=True
                )
                self.log(f"[gismo EXE stdout]\n{result.stdout.strip()}")
                if result.stderr:
                    self.log(f"[gismo EXE stderr]\n{result.stderr.strip()}")

            for ext in ('gismod', 'gismop'):
                dst = model_dir / f"{name}.{ext}"
                if dst.exists():
                    self.log(f"Created: {dst.name}")
                    continue
                src = exe_dir / f"{name}.{ext}"
                if src.exists():
                    try:
                        shutil.move(str(src), str(dst))
                        self.log(f"Created: {dst.name}")
                    except Exception as e:
                        self.log(f"ERROR moving {name}.{ext}: {e}")
                else:
                    self.log(f"Missing output: {name}.{ext}")

    def open_settings(self):
        dlg = SettingsDialog(self)
        dlg.exec()

    def select_path(self):
        path, _ = QFileDialog.getOpenFileName(self, "Select an executable")
        if path:
            norm = os.path.normpath(path)
            self.path_input.setText(norm)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    editor = JsonEditor()
    editor.show()
    sys.exit(app.exec())
