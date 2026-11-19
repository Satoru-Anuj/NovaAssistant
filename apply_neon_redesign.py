from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

path = Path("nova_studio_qt.py")
if not path.is_file():
    sys.exit("ERROR: nova_studio_qt.py was not found. No changes made.")

source = path.read_text(encoding="utf-8")
backup = path.with_name(
    f"nova_studio_qt.before_neon_redesign_{datetime.now():%Y%m%d_%H%M%S}.py"
)
shutil.copy2(path, backup)

method = source.find("    def _build_ui(self):")
if method < 0:
    sys.exit(f"ERROR: _build_ui was not found. Backup: {backup}")

start = source.find('        self.setStyleSheet("""', method)
if start < 0:
    sys.exit(f"ERROR: stylesheet start not found. Backup: {backup}")

end_marker = '        """)'
end = source.find(end_marker, start)
if end < 0:
    sys.exit(f"ERROR: stylesheet end not found. Backup: {backup}")
end += len(end_marker)

new_style = '''        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #0A0D14;
                color: #E8F2FF;
                font-family: "Segoe UI";
                font-size: 9pt;
            }
            QMainWindow { background: #080B11; }

            QMenuBar, QToolBar {
                background: #101622;
                color: #DDEBFF;
                border: none;
                border-bottom: 1px solid #26354A;
                padding: 7px;
                spacing: 7px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 11px;
                border-radius: 5px;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background: #16384A;
                color: #75F0FF;
            }
            QMenu {
                background: #111927;
                color: #E8F2FF;
                border: 1px solid #35435C;
                padding: 5px;
            }
            QMenu::item { padding: 7px 25px; }

            QFrame#panel {
                background: #111723;
                border: 1px solid #28364B;
                border-radius: 10px;
            }
            QLabel#heading {
                color: #78EFFF;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QLabel#muted { color: #8497B2; }

            QPushButton {
                background: #1A2434;
                color: #E4F0FF;
                border: 1px solid #34445B;
                padding: 8px 13px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #24374B;
                border-color: #47CFEA;
                color: #FFFFFF;
            }
            QPushButton:pressed { background: #13202E; }
            QPushButton:disabled {
                background: #131923;
                color: #5F6E82;
                border-color: #222D3C;
            }
            QPushButton#primary {
                background: #123E55;
                color: #E9FCFF;
                border: 1px solid #28C8E8;
                font-weight: 700;
            }
            QPushButton#primary:hover {
                background: #17627B;
                border-color: #8AF5FF;
            }
            QPushButton#tool {
                min-width: 38px;
                min-height: 34px;
                padding: 4px;
                font-weight: 700;
            }

            QListWidget, QTreeWidget, QTableWidget,
            QTabWidget::pane {
                background: #0B111B;
                color: #DDEAFF;
                border: 1px solid #27364B;
                padding: 5px;
                outline: none;
                selection-background-color: #164457;
                selection-color: #8BF4FF;
            }
            QListWidget::item, QTreeWidget::item {
                padding: 7px;
                border-radius: 4px;
            }
            QListWidget::item:selected, QTreeWidget::item:selected {
                background: #15394A;
                color: #8AF2FF;
                border-left: 2px solid #39DDF5;
            }

            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
            QSpinBox, QDoubleSpinBox {
                background: #0B111B;
                color: #E8F2FF;
                border: 1px solid #303F55;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #164457;
            }
            QLineEdit:focus, QTextEdit:focus,
            QPlainTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #45DDF4;
                background: #0D1622;
            }

            QTabWidget::pane {
                top: -1px;
                padding: 7px;
                border: 1px solid #2B3A50;
                border-radius: 7px;
            }
            QTabBar::tab {
                background: #151D2B;
                color: #91A2BA;
                padding: 9px 12px;
                border: 1px solid #29374B;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #20223B;
                color: #B6A9FF;
                border-color: #7667D9;
                border-bottom: 2px solid #9A85FF;
            }

            QSlider::groove:horizontal {
                height: 5px;
                background: #2B394D;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4AE5F5;
                width: 14px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background: #0B111B;
                border: 1px solid #566A83;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: #17617A;
                border: 1px solid #4AE5F5;
                border-radius: 4px;
            }

            QStatusBar {
                background: #090D14;
                color: #9DB0C9;
                border-top: 1px solid #28364B;
            }
            QSplitter::handle {
                background: #1D2B3D;
            }
            QSplitter::handle:hover {
                background: #3ACBE8;
            }
            QScrollBar:vertical {
                background: #0B111B;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #34465D;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4A94AC;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #0B111B;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #34465D;
                min-width: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4A94AC;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)'''

updated = source[:start] + new_style + source[end:]

old_sizes = "        workspace.setSizes([48, 210, 720, 275, 280])"
new_sizes = "        workspace.setSizes([52, 220, 790, 285, 245])"
if old_sizes not in updated:
    sys.exit(
        f"ERROR: expected workspace sizing line not found; no changes written. Backup: {backup}"
    )

updated = updated.replace(old_sizes, new_sizes, 1)

# Keep the root workspace/timeline split as-is; it is already 7:3.
path.write_text(updated, encoding="utf-8", newline="\n")

try:
    py_compile.compile(str(path), doraise=True)
except Exception:
    shutil.copy2(backup, path)
    sys.exit(f"Syntax check failed. Original restored from: {backup}")

print("SUCCESS: neon theme and workspace proportions applied.")
print(f"Backup: {backup}")
print("Syntax check: passed")
print("AI editing and playback methods were not intentionally changed.")
