from pathlib import Path
import ast

files = [
    "nova_widget.py",
    "nova_widget_before_state3_20261013_135809.py",
    "nova_widget.py.before_ring_redesign.bak",
    "nova_widget.py.before_idle_restore.bak",
    "nova_widget_before_idle_active_backup.py",
    "nova_widget.py.candidate",
]

for name in files:
    path = Path(name)
    if not path.exists():
        continue

    source = path.read_text(encoding="utf-8-sig")
    print("\n" + "=" * 72)
    print(name, "|", len(source), "characters")

    try:
        tree = ast.parse(source)
        cls = next(
            node for node in tree.body
            if isinstance(node, ast.ClassDef) and node.name == "NovaWidget"
        )

        for node in cls.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name in ("paintEvent", "_paint_glass_bar",
                                 "_paint_active_plasma"):
                    segment = ast.get_source_segment(source, node)
                    print(f"\n--- {node.name} ---")
                    print("\n".join(segment.splitlines()[:12]))
                    print("Lines in method:", len(segment.splitlines()))
    except Exception as exc:
        print("Inspection error:", exc)
