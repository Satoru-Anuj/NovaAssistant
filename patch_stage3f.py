from pathlib import Path
import py_compile
import shutil
from datetime import datetime

file = Path("nova_studio_qt.py")
source = file.read_text(encoding="utf-8-sig")

marker = "# NOVA_STAGE3F_AUTO_PREVIEW"
if marker in source:
    raise SystemExit("Stage 3F marker already exists; no changes made.")

anchor = '            QMessageBox.information(\n                self, "Edit Complete",'
if source.count(anchor) != 1:
    raise SystemExit(
        f"Expected one completion-dialog anchor, found {source.count(anchor)}. "
        "No changes made."
    )

assignment = "            self.ai_result_path = str(current_input)"
if source.count(assignment) != 1:
    raise SystemExit(
        f"Expected one final-result assignment, found {source.count(assignment)}. "
        "No changes made."
    )

backup = file.with_name(
    f"nova_studio_qt.py.before_auto_preview_{datetime.now():%Y%m%d_%H%M%S}.bak"
)
shutil.copy2(file, backup)

insertion = '''            # NOVA_STAGE3F_AUTO_PREVIEW
            # Load the completed AI export into the Program Monitor.
            self.statusBar().showMessage(
                f"Loading AI result: {Path(current_input).name}"
            )
            from PySide6.QtWidgets import QApplication
            QApplication.processEvents()
            self.load_video(str(current_input))
            self.statusBar().showMessage(
                f"AI result loaded: {Path(current_input).name}"
            )

'''

updated = source.replace(anchor, insertion + anchor, 1)

temp = file.with_name("nova_studio_qt_stage3f_check.py")
try:
    temp.write_text(updated, encoding="utf-8")
    py_compile.compile(str(temp), doraise=True)
    file.write_text(updated, encoding="utf-8")
    py_compile.compile(str(file), doraise=True)
except Exception:
    shutil.copy2(backup, file)
    raise
finally:
    temp.unlink(missing_ok=True)

print("PASS: Automatic Program Monitor loading added.")
print(f"Backup: {backup}")
