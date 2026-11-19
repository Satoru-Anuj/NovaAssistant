from pathlib import Path
import ast
import py_compile
import shutil
import time

path = Path("nova_widget.py")
source = path.read_text(encoding="utf-8")
tree = ast.parse(source)

target = next(
    (node for node in ast.walk(tree)
     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
     and node.name == "_paint_active_plasma"),
    None
)

if target is None:
    raise SystemExit("STOP: Could not find _paint_active_plasma. No changes made.")

replacement = '''    def _paint_active_plasma(self, t, state):
        """Minimal voice waveform animation. No orb, rings, sparks, or added effects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        w = self.width()
        h = self.height()
        cx = w / 2.0
        cy = h / 2.0
        phase = float(t)
        mode = str(state).lower()

        # A single clean waveform: no orb, halo, particles, or orbital geometry.
        count =  thirteen = 13
        bar_width = max(3.0, min(7.0, w * 0.018))
        gap = bar_width * 0.85
        total_width = count * bar_width + (count - 1) * gap
        max_height = min(h * 0.34, w * 0.22)

        for i in range(count):
            position = i / (count - 1)
            distance = abs(i - (count - 1) / 2) / ((count - 1) / 2)

            if "speak" in mode or "respond" in mode:
                # A moving voice signal with an uneven, natural rhythm.
                wave_a = abs(math.sin(phase * 4.2 - i * 0.62))
                wave_b = abs(math.sin(phase * 2.7 - i * 0.31 + 0.8))
                amplitude = 0.16 + 0.68 * (0.68 * wave_a + 0.32 * wave_b)
            elif "think" in mode:
                # Quiet, slow motion while Nova is processing.
                wave = 0.5 + 0.5 * math.sin(phase * 1.8 - i * 0.48)
                amplitude = 0.18 + 0.28 * wave
            else:
                # Listening: a gentle wave rising toward the centre.
                pulse = 0.5 + 0.5 * math.sin(phase * 2.0)
                amplitude = 0.12 + (1.0 - distance) * (0.28 + 0.28 * pulse)

            bar_height = max(5.0, max_height * amplitude)
            x = cx - total_width / 2 + i * (bar_width + gap)
            y = cy - bar_height / 2

            # Simple cyan-to-blue colour progression.
            r = int(45 + 20 * position)
            g = int(220 - 65 * position)
            b = 255

            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(r, g, b, 235))
            painter.drawRoundedRect(
                x, y, bar_width, bar_height,
                bar_width / 2, bar_width / 2
            )

        painter.end()
'''

lines = source.splitlines(keepends=True)
start = target.lineno - 1
end = target.end_lineno
updated = "".join(lines[:start]) + replacement + "".join(lines[end:])

check_path = Path("nova_widget_waveform_check.py")
check_path.write_text(updated, encoding="utf-8")

try:
    py_compile.compile(str(check_path), doraise=True)
except Exception:
    check_path.unlink(missing_ok=True)
    raise

backup = Path(
    "nova_widget_before_waveform_redesign_"
    + time.strftime("%Y%m%d_%H%M%S") + ".py"
)
shutil.copy2(path, backup)
path.write_text(updated, encoding="utf-8")
check_path.unlink(missing_ok=True)

print("SUCCESS: Active animation replaced with a clean voice waveform.")
print("Idle renderer and Glass Bar method were not modified.")
print("Backup created:", backup)
print("Syntax check passed.")
