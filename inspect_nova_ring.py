from pathlib import Path
import ast

def get_methods(filename):
    source = Path(filename).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    cls = next(
        n for n in tree.body
        if isinstance(n, ast.ClassDef) and n.name == "NovaWidget"
    )
    methods = {}
    for n in cls.body:
        if isinstance(n, ast.FunctionDef):
            if n.name in ("paintEvent", "_paint_glass_bar"):
                methods[n.name] = (
                    ast.get_source_segment(source, n).splitlines()
                )
    return methods

backup = "nova_widget.py.before_ring_redesign.bak"
current = "nova_widget.py"

print("\n=== ORIGINAL IDLE ANIMATION ===")
old = get_methods(backup)
print("\n".join(old.get("paintEvent", [])))

print("\n=== ORIGINAL GLASS BAR RING REFERENCES ===")
for i, line in enumerate(old.get("_paint_glass_bar", [])):
    if any(word in line.lower() for word in (
        "ring", "torus", "infinity", "major", "minor",
        "faces", "ellipse", "rotate", "circle"
    )):
        start, end = max(0, i - 2), min(len(old["_paint_glass_bar"]), i + 4)
        print(f"\nLines {start + 1}-{end}:")
        print("\n".join(old["_paint_glass_bar"][start:end]))

print("\n=== CURRENT GLASS BAR RING REFERENCES ===")
new = get_methods(current)
for i, line in enumerate(new.get("_paint_glass_bar", [])):
    if any(word in line.lower() for word in (
        "ring", "torus", "infinity", "major", "minor",
        "faces", "ellipse", "rotate", "circle"
    )):
        start, end = max(0, i - 2), min(len(new["_paint_glass_bar"]), i + 4)
        print(f"\nLines {start + 1}-{end}:")
        print("\n".join(new["_paint_glass_bar"][start:end]))
