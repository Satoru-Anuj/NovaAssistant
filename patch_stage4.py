from pathlib import Path
from datetime import datetime
import ast
import shutil
import textwrap
import sys

path = Path("nova_studio_qt.py")
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)

cls = next(
    (n for n in tree.body
     if isinstance(n, ast.ClassDef) and n.name == "NovaStudioQt"),
    None,
)
if cls is None:
    raise SystemExit("STOP: NovaStudioQt class not found.")

methods = {
    n.name: n for n in cls.body
    if isinstance(n, ast.FunctionDef)
}
if not all(n in methods for n in (
    "apply_ai_edit", "save_ai_result_as", "load_video"
)):
    raise SystemExit("STOP: Expected methods missing.")

if "NOVA_STAGE3B_MULTI_ACTION" not in source:
    raise SystemExit("STOP: Stage 3B marker missing.")
if "NOVA_STAGE3F_AUTO_PREVIEW" not in source:
    raise SystemExit("STOP: Stage 3F marker missing.")
if "NOVA_STAGE4_BACKGROUND_WORKER" in source:
    raise SystemExit("STOP: Stage 4 patch appears already applied.")

apply_node = methods["apply_ai_edit"]
save_node = methods["save_ai_result_as"]
apply_lines = source.splitlines(keepends=True)

# Extract only the existing sequential processing section.
method_text = "".join(
    apply_lines[apply_node.lineno - 1:apply_node.end_lineno]
)

start_marker = "            import nova_video_editor as editor\n"
end_marker = "            self.ai_result_path = str(current_input)\n"

if method_text.count(start_marker) != 1:
    raise SystemExit("STOP: Processing start marker is not unique.")
if method_text.count(end_marker) != 1:
    raise SystemExit("STOP: Processing end marker is not unique.")

processing = method_text.split(start_marker, 1)[1]
processing = processing.split(end_marker, 1)[0]

# Remove the old try-block indentation, then adapt the request text
# reference so the worker never reads a GUI widget.
processing = textwrap.dedent(processing)
processing = processing.replace(
    "self.ai_request_input.toPlainText().strip().lower()",
    "self.request_text.strip().lower()",
)

if "self.ai_request_input" in processing:
    raise SystemExit(
        "STOP: A GUI widget reference remains in worker code."
    )
if "self." in processing.replace("self.request_text", ""):
    raise SystemExit(
        "STOP: Unexpected GUI/object reference in processing code."
    )

# The worker emits a completed file path, original path, and action log.
worker_body = textwrap.indent(processing.rstrip(), "            ")

worker_class = (
    "\n\n# NOVA_STAGE4_BACKGROUND_WORKER\n"
    "class NovaAIEditWorker(QThread):\n"
    "    succeeded = Signal(str, str, object)\n"
    "    failed = Signal(str)\n"
    "    progress = Signal(str)\n\n"
    "    def __init__(self, plan, source, request_text, parent=None):\n"
    "        super().__init__(parent)\n"
    "        self.plan = plan\n"
    "        self.source = source\n"
    "        self.request_text = request_text\n\n"
    "    def run(self):\n"
    "        try:\n"
    "            plan = self.plan\n"
    "            actions = plan.get('actions', [])\n"
    "            source = self.source\n"
    "            original_input = Path(source).resolve()\n"
    "            current_input = original_input\n"
    "            action_results = []\n"
    "            self.progress.emit('Preparing exports...')\n"
    "            import nova_video_editor as editor\n"
    "            import re\n"
    "            export_dir = Path(getattr(\n"
    "                editor, 'EXPORT_DIR',\n"
    "                Path(__file__).resolve().parent / 'Nova_Exports'\n"
    "            ))\n"
    "            export_dir.mkdir(parents=True, exist_ok=True)\n"
            + worker_body + "\n"
    "            self.succeeded.emit(\n"
    "                str(current_input), str(original_input), action_results\n"
    "            )\n"
    "        except Exception as exc:\n"
    "            self.failed.emit(str(exc))\n"
)

# Check the worker source parses before touching the editor file.
worker_test = (
    "from pathlib import Path\n"
    "import re\n"
    "from PySide6.QtCore import QThread, Signal\n"
    + worker_class
)
try:
    ast.parse(worker_test)
except SyntaxError as exc:
    raise SystemExit(f"STOP: Generated worker syntax error: {exc}")

# GUI-side replacement. No FFmpeg processing is performed here.
new_method = '''
    def apply_ai_edit(self):
        """Run sequential AI edits off the GUI thread."""
        plan = getattr(self, "ai_plan_data", None)
        actions = plan.get("actions", []) if isinstance(plan, dict) else []

        if not isinstance(actions, list) or not actions:
            QMessageBox.information(
                self, "AI Editing",
                "Generate a plan with at least one edit action first."
            )
            return

        source = self.player.source().toLocalFile()
        if not source or not Path(source).is_file():
            QMessageBox.information(self, "AI Editing", "Import a video first.")
            return

        current_worker = getattr(self, "_ai_edit_worker", None)
        if current_worker is not None and current_worker.isRunning():
            return

        self.ai_apply_button.setEnabled(False)
        self.statusBar().showMessage("AI edit running in background...")
        self._ai_edit_worker = NovaAIEditWorker(
            plan,
            source,
            self.ai_request_input.toPlainText().strip().lower(),
            self
        )
        self._ai_edit_worker.progress.connect(
            self.statusBar().showMessage
        )
        self._ai_edit_worker.succeeded.connect(
            self._ai_edit_succeeded
        )
        self._ai_edit_worker.failed.connect(
            self._ai_edit_failed
        )
        self._ai_edit_worker.finished.connect(
            self._ai_edit_worker_finished
        )
        self._ai_edit_worker.start()

    def _ai_edit_succeeded(self, output_path, original_path, action_results):
        """Update the GUI only after background processing finishes."""
        self.ai_result_path = output_path
        self.ai_save_button.setEnabled(True)
        self.ai_preview_button.setEnabled(True)
        self.ai_plan_output.appendPlainText(
            "\\\\n\\\\nSequential edit results:\\\\n"
            + "\\\\n".join(action_results)
        )
        # NOVA_STAGE3F_AUTO_PREVIEW
        self.statusBar().showMessage(
            f"Loading AI result: {Path(output_path).name}"
        )
        self.load_video(output_path)
        self.statusBar().showMessage(
            f"AI result loaded: {Path(output_path).name}"
        )
        QMessageBox.information(
            self, "Edit Complete",
            f"All {len(action_results)} action(s) exported successfully.\\\\n\\\\n"
            f"Original: {original_path}\\\\n\\\\nFinal output: {output_path}"
        )

    def _ai_edit_failed(self, error):
        QMessageBox.warning(
            self, "AI Editing",
            f"Edit failed:\\\\n{error}\\\\n\\\\n"
            "Any completed intermediate exports have been left in Nova_Exports."
        )
        self.statusBar().showMessage("AI edit failed.")

    def _ai_edit_worker_finished(self):
        self.ai_apply_button.setEnabled(
            bool(getattr(self, "ai_plan_data", None)
                 and self.ai_plan_data.get("actions"))
        )
        worker = getattr(self, "_ai_edit_worker", None)
        if worker is not None:
            worker.deleteLater()
            self._ai_edit_worker = None
'''

new_method = textwrap.dedent(new_method).lstrip("\n")
new_method = textwrap.indent(new_method.rstrip(), "    ") + "\n\n"

# Replace the method using verified AST line boundaries.
lines = source.splitlines(keepends=True)
replacement_start = apply_node.lineno - 1
replacement_end = save_node.lineno - 1
updated = (
    "".join(lines[:replacement_start])
    + new_method
    + "".join(lines[replacement_end:])
)

# Add Qt thread imports.
updated = updated.replace(
    "from PySide6.QtCore import Qt, QUrl, QTimer",
    "from PySide6.QtCore import Qt, QUrl, QTimer, QThread, Signal",
    1,
)

# Insert worker class before TimelineWidget.
timeline_marker = "class TimelineWidget(QWidget):"
if updated.count(timeline_marker) != 1:
    raise SystemExit("STOP: TimelineWidget insertion point is not unique.")
updated = updated.replace(
    timeline_marker,
    worker_class + "\n\n\n" + timeline_marker,
    1,
)

# Final structural checks before writing.
try:
    ast.parse(updated)
except SyntaxError as exc:
    raise SystemExit(f"STOP: Final syntax check failed: {exc}")

updated_tree = ast.parse(updated)
updated_cls = next(
    n for n in updated_tree.body
    if isinstance(n, ast.ClassDef) and n.name == "NovaStudioQt"
)
updated_methods = {
    n.name: n for n in updated_cls.body
    if isinstance(n, ast.FunctionDef)
}
for name in (
    "apply_ai_edit", "_ai_edit_succeeded",
    "_ai_edit_failed", "_ai_edit_worker_finished",
    "save_ai_result_as", "load_video"
):
    if name not in updated_methods:
        raise SystemExit(f"STOP: Required method missing after patch: {name}")

backup = path.with_name(
    f"nova_studio_qt.py.stage4_before_{datetime.now():%Y%m%d_%H%M%S}.bak"
)
shutil.copy2(path, backup)

try:
    path.write_text(updated, encoding="utf-8")
    compile(updated, str(path), "exec")
except Exception:
    shutil.copy2(backup, path)
    raise

print("Stage 4 patch applied.")
print(f"Backup: {backup.name}")
print("AST and compile checks: PASS")
