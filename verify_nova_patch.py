from pathlib import Path
import ast

original = Path("nova_widget.py").read_text(encoding="utf-8-sig")
candidate = Path("nova_widget.py.candidate").read_text(encoding="utf-8-sig")

for label, source in (("Original", original), ("Candidate", candidate)):
    tree = ast.parse(source)
    widget = next(
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "NovaWidget"
    )
    names = {
        node.name for node in widget.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    print(f"{label}: _paint_glass_bar exists =", "_paint_glass_bar" in names)
    print(f"{label}: mouseReleaseEvent exists =", "mouseReleaseEvent" in names)
    print(f"{label}: paintEvent exists =", "paintEvent" in names)

for signal in ("microphoneClicked", "audioToggleRequested"):
    print(f"{signal} in candidate =", signal in candidate)

print("Candidate size:", Path("nova_widget.py.candidate").stat().st_size)
print("Original size:", Path("nova_widget.py").stat().st_size)
