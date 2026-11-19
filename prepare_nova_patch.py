from pathlib import Path
import ast

target = Path("nova_widget.py")
method_file = Path("nova_glass_method.txt")
candidate = Path("nova_widget.py.candidate")

if not target.is_file() or not method_file.is_file():
    raise SystemExit("STOP: Required file missing.")

source = target.read_text(encoding="utf-8-sig")
method = method_file.read_text(encoding="utf-8-sig")

# Remove blank lines only; preserve Python indentation.
lines = method.splitlines()
while lines and not lines[0].strip():
    lines.pop(0)
method = "\n".join(lines).rstrip() + "\n"

if not method.startswith("    def _paint_glass_bar(self, event):"):
    raise SystemExit(
        "STOP: Unexpected header: " + repr(method.splitlines()[0])
    )

start = source.find("    def _paint_glass_bar(")
if start < 0 or source.find("    def _paint_glass_bar(", start + 1) >= 0:
    raise SystemExit("STOP: Expected exactly one target method.")

end = source.find("\n    def ", start + 5)
if end < 0:
    raise SystemExit("STOP: Following method boundary not found.")

method = method.replace("segments = 120", "segments = 84")
method = method.replace("across = 8", "across = 6")

updated = source[:start] + method.rstrip() + source[end:]

# Add QPointF to the existing QtGui import block if needed.
if "QPointF" not in updated:
    import_start = updated.find("from PySide6.QtGui import (")
    if import_start < 0:
        raise SystemExit("STOP: QtGui import block not found.")
    import_end = updated.find("\n)", import_start)
    if import_end < 0:
        raise SystemExit("STOP: QtGui import block end not found.")
    updated = updated[:import_end] + ", QPointF" + updated[import_end:]

try:
    ast.parse(updated, filename=str(candidate))
except SyntaxError as exc:
    raise SystemExit(f"STOP: Syntax error at line {exc.lineno}: {exc.msg}")

candidate.write_text(updated, encoding="utf-8")
print("PASS: Full-file syntax check succeeded.")
print("PASS: Original nova_widget.py remains unchanged.")
print("Candidate ready:", candidate)
