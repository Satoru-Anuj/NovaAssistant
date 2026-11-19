from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

path = Path("nova_studio_qt.py")
source = path.read_text(encoding="utf-8")
updated = source

# Remove the three redundant toolbar buttons.
for line in (
    '            ("Delete Selected Clip", self.delete_selected_clip),\n',
    '            ("Select Video", lambda: self.timeline_widget.set_track("video")),\n',
    '            ("Select Audio", lambda: self.timeline_widget.set_track("audio")),\n',
):
    if line not in updated:
        print("STOP: Expected toolbar line not found:")
        print(repr(line))
        sys.exit(1)
    updated = updated.replace(line, "", 1)

# Add a Backspace shortcut to the main window without displaying a toolbar button.
if "self.backspace_delete_action" not in updated:
    anchor = "        self.player.errorOccurred.connect(self._playback_error)\n"
    if anchor not in updated:
        print("STOP: Could not find the safe shortcut insertion point.")
        sys.exit(1)

    shortcut_code = (
        "        self.backspace_delete_action = QAction('Delete selected clip', self)\n"
        "        self.backspace_delete_action.setShortcut('Backspace')\n"
        "        self.backspace_delete_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)\n"
        "        self.backspace_delete_action.triggered.connect(self.delete_selected_clip)\n"
        "        self.addAction(self.backspace_delete_action)\n"
    )
    updated = updated.replace(anchor, anchor + shortcut_code, 1)

# Ensure the Qt namespace is imported for the shortcut context.
if "Qt.ShortcutContext.WidgetWithChildrenShortcut" in updated:
    import_lines = updated.splitlines()
    qt_import_present = any(
        line.strip() == "from PySide6.QtCore import Qt" or
        line.strip().startswith("from PySide6.QtCore import ") and
        "Qt" in line.split(" import ", 1)[1].split("#", 1)[0].split(",")
        for line in import_lines
        if " import " in line
    )
    if not qt_import_present:
        core_import = next(
            (line for line in import_lines
             if line.startswith("from PySide6.QtCore import ")),
            None
        )
        if core_import:
            if "Qt" not in core_import.split(" import ", 1)[1].split(","):
                updated = updated.replace(core_import, core_import + ", Qt", 1)
        else:
            updated = "from PySide6.QtCore import Qt\n" + updated

if updated == source:
    print("No changes were needed.")
    sys.exit(0)

backup_dir = Path("studio_rebuild_backups")
backup_dir.mkdir(exist_ok=True)
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = backup_dir / f"before_backspace_delete_{stamp}.py"
shutil.copy2(path, backup)

temp = path.with_name("nova_studio_qt_backspace_check.py")
try:
    temp.write_text(updated, encoding="utf-8")
    py_compile.compile(str(temp), doraise=True)
    path.write_text(updated, encoding="utf-8")
    py_compile.compile(str(path), doraise=True)
finally:
    if temp.exists():
        temp.unlink()

print("PATCH APPLIED.")
print(f"Backup: {backup}")
print("Toolbar selection/deletion buttons removed; Backspace shortcut added.")
