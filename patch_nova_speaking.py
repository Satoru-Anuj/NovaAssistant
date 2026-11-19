from pathlib import Path
import ast
import py_compile
import shutil
import time

file = Path("nova_widget.py")
source = file.read_text(encoding="utf-8")
tree = ast.parse(source)

method = next(
    (n for n in ast.walk(tree)
     if isinstance(n, ast.FunctionDef)
     and n.name == "_paint_active_plasma"),
    None
)

if method is None:
    raise SystemExit("STOP: Active animation method not found. No changes made.")

start = method.lineno - 1
end = method.end_lineno
lines = source.splitlines(keepends=True)
method_text = "".join(lines[start:end])

marker = "# NOVA_LIQUID_SPEAKING_RIBBON"
if marker in method_text:
    raise SystemExit("The speaking ribbon is already installed. No changes made.")

anchor = '        mode = str(state).lower()'
if anchor not in method_text or "# A single clean waveform" not in method_text:
    raise SystemExit(
        "STOP: The current animation is not the expected waveform version. "
        "No changes made. Share the current method before patching."
    )

insert = '''
        # NOVA_LIQUID_SPEAKING_RIBBON
        # Replace the bars only while Nova is speaking.
        if "speak" in mode or "respond" in mode:
            ribbon_width = min(w * 0.78, 340.0)
            ribbon_height = min(h * 0.28, 62.0)
            left = cx - ribbon_width / 2
            layers = [
                (0.0, QColor(25, 115, 255, 65), 12.0),
                (1.0, QColor(0, 205, 255, 150), 5.0),
                (2.0, QColor(150, 245, 255, 235), 2.0),
            ]

            for layer, color, thickness in layers:
                path = QPainterPath()
                steps = 72

                for j in range(steps + 1):
                    u = j / steps
                    x = left + u * ribbon_width
                    envelope = math.sin(math.pi * u) ** 0.65
                    wave1 = math.sin(u * math.pi * 3.0 - phase * 3.8 + layer * 0.5)
                    wave2 = math.sin(u * math.pi * 5.0 + phase * 2.4 - layer * 0.7)
                    wave3 = math.sin(u * math.pi * 1.5 - phase * 1.8)
                    y = cy + ribbon_height * envelope * (
                        0.52 * wave1 + 0.28 * wave2 + 0.20 * wave3
                    )

                    if j == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)

                painter.setPen(QPen(
                    color, thickness,
                    Qt.PenStyle.SolidLine,
                    Qt.PenCapStyle.RoundCap,
                    Qt.PenJoinStyle.RoundJoin
                ))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(path)

            # Two moving highlights give the ribbon a liquid, energized feel.
            painter.setPen(Qt.PenStyle.NoPen)
            for k in range(2):
                u = (phase * 0.24 + k * 0.5) % 1.0
                x = left + u * ribbon_width
                envelope = math.sin(math.pi * u) ** 0.65
                y = cy + ribbon_height * envelope * (
                    0.52 * math.sin(u * math.pi * 3.0 - phase * 3.8)
                    + 0.28 * math.sin(u * math.pi * 5.0 + phase * 2.4)
                    + 0.20 * math.sin(u * math.pi * 1.5 - phase * 1.8)
                )
                painter.setBrush(QColor(170, 250, 255, 240))
                painter.drawEllipse(x - 3.0, y - 3.0, 6.0, 6.0)

            painter.end()
            return
'''

method_text = method_text.replace(anchor, anchor + insert, 1)
updated = "".join(lines[:start]) + method_text + "".join(lines[end:])

check = Path("_nova_speaking_check.py")
check.write_text(updated, encoding="utf-8")

try:
    py_compile.compile(str(check), doraise=True)
finally:
    check.unlink(missing_ok=True)

backup = Path(
    "nova_widget_before_liquid_speaking_"
    + time.strftime("%Y%m%d_%H%M%S") + ".py"
)
shutil.copy2(file, backup)
file.write_text(updated, encoding="utf-8")

print("SUCCESS: Liquid Neon Ribbon added for speaking only.")
print("Listening, thinking, Idle, and Glass Bar were preserved.")
print("Backup:", backup)
print("Syntax check passed.")
