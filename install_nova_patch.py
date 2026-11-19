from pathlib import Path
import ast
import shutil
from datetime import datetime

original = Path("nova_widget.py")
candidate = Path("nova_widget.py.candidate")

if not original.is_file() or not candidate.is_file():
    raise SystemExit("STOP: Original or candidate file is missing.")

# Validate both files before touching the original.
old_text = original.read_text(encoding="utf-8-sig")
new_text = candidate.read_text(encoding="utf-8-sig")
ast.parse(old_text)
ast.parse(new_text)

# Ensure the approved rendering and mouse handlers are unchanged.
def get_method(source, name):
    tree = ast.parse(source)
    for cls in tree.body:
        if isinstance(cls, ast.ClassDef) and cls.name == "NovaWidget":
            for node in cls.body:
                if isinstance(node, ast.FunctionDef) and node.name == name:
                    return ast.dump(node, include_attributes=False)
    return None

for name in ("paintEvent", "mouseReleaseEvent", "mousePressEvent"):
    if get_method(old_text, name) != get_method(new_text, name):
        raise SystemExit(f"STOP: Protected method differs: {name}")

# Preserve a timestamped rollback copy.
stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup = Path(f"nova_widget.py.pre_glass_install_{stamp}.bak")
shutil.copy2(original, backup)

# Atomic replacement in the same directory.
temp = Path("nova_widget.py.install_tmp")
temp.write_text(new_text, encoding="utf-8")
ast.parse(temp.read_text(encoding="utf-8"))
temp.replace(original)

print("INSTALL SUCCESS")
print("Backup:", backup)
print("Installed nova_widget.py syntax: OK")
