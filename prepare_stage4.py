from pathlib import Path
from datetime import datetime
import ast
import shutil
import sys

path = Path("nova_studio_qt.py")
if not path.is_file():
    raise SystemExit("ERROR: nova_studio_qt.py was not found.")

source = path.read_text(encoding="utf-8")
tree = ast.parse(source)

cls = next(
    (n for n in tree.body
     if isinstance(n, ast.ClassDef) and n.name == "NovaStudioQt"),
    None,
)
if cls is None:
    raise SystemExit("ERROR: NovaStudioQt class was not found.")

methods = {
    n.name: n for n in cls.body
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
}
required = ("apply_ai_edit", "save_ai_result_as", "load_video")
if any(name not in methods for name in required):
    raise SystemExit("ERROR: Expected method boundaries were not found.")

if "NOVA_STAGE3B_MULTI_ACTION" not in source:
    raise SystemExit("ERROR: Stage 3B marker missing; refusing to patch.")
if "NOVA_STAGE3F_AUTO_PREVIEW" not in source:
    raise SystemExit("ERROR: Stage 3F marker missing; refusing to patch.")

print("Preflight passed.")
print("Methods:")
for name in required:
    node = methods[name]
    print(f"  {name}: {node.lineno}-{node.end_lineno}")

print("\nNo editor changes have been made.")
print("Next, the worker patch must preserve sequential exports and main-thread UI updates.")
