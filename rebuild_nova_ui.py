from pathlib import Path
from pathlib import Path
from datetime import datetime
import shutil
import py_compile
import sys

ROOT = Path(__file__).rest
MAIN = ROOT / "main.py"
WIDGET = ROOT / "nova_widget.py"
STATUS = ROOT / "nova_status.txt"

if not MAIN.is_file() or not WIDGET.is_file():
    raise SystemExit(
        "ERROR: Open this script from the NovaAssistant project folder."
    )

main = MAIN.read_text(encoding="utf-8")
widget = WIDGET.read_text(encoding="utf-8")

# Make sure the expected source sections exist before modifying anything.
required = [
    "    def animate(self):",
    "    def set_status(self, status):",
    "    def say_wake_response(self):",
    'if __name__ == "__main__":',
    "    app.root.mainloop()",
]
for marker in required:
    if marker not in main:
        raise SystemExit(f"ERROR: main.py is missing expected code: {marker}")

if "    def paintEvent(self, event):" not in widget:
    raise SystemExit("ERROR: Original widget paintEvent was not found.")

if "    def mouseReleaseEvent(self, event):" not in widget:
    raise SystemExit("ERROR: Widget mouse controls were not found.")

if "    def _paint_glass_bar(self, event):" in widget:
    raise SystemExit(
        "The widget appears partly patched already. No files changed; "
        "inspect the existing edits before running another rebuild."
    )

# --- Rebuild the obsolete Tkinter animation out of the backend ---
start = main.index("    def animate(self):")
end = main.index("    def set_status(self, status):", start)

new_animate = '''    def animate(self):
        # The Qt widget is the only visible Nova interface.
        # Keep the Tk backend renderer disabled.
        return

'''

main = main[:start] + new_animate + main[end:]

# Publish assistant status for the Qt widget, without changing status callers.
start = main.index("    def set_status(self, status):")
end = main.index("    def say_wake_response(self):", start)

new_status = '''    def set_status(self, status):
        if self.closing:
            return

        self.status = status
        try:
            Path(__file__).with_name("nova_status.txt").write_text(
                str(status), encoding="utf-8"
            )
        except OSError:
            pass

'''

main = main[:start] + new_status + main[end:]

# Background launch must not show the old Tkinter window.
old_entry = '''if __name__ == "__main__":
    app = NovaOrb()
    app.root.mainloop()
'''
new_entry = '''if __name__ == "__main__":
    app = NovaOrb()
    if "--background" in sys.argv:
        app.root.withdraw()
    app.root.mainloop()
'''
if old_entry not in main:
    raise SystemExit(
        "ERROR: The expected main.py entry point differs from the inspected "
        "version. No files changed."
    )
main = main.replace(old_entry, new_entry, 1)

# --- Rebuild the Qt widget states while preserving its Glass Bar renderer ---
if not any(
    line.strip() == "from pathlib import Path"
    for line in widget.splitlines()
):
    widget = "from pathlib import Path\n" + widget

old_size = "        self.setFixedSize(390, 170)"
if old_size not in widget:
    raise SystemExit(
        "ERROR: Expected widget size was not found. No files changed."
    )
widget = widget.replace(old_size, "        self.setFixedSize(104, 104)", 1)

old_started = "        self.started = time.perf_counter()"
if old_started not in widget:
    raise SystemExit("ERROR: Widget animation initialization was not found.")
widget = widget.replace(
    old_started,
    old_started + '''
        self.ui_mode = "idle"
        self.status_file = Path(__file__).with_name("nova_status.txt")
''',
    1,
)

# Rename, but do not rewrite, the existing Glass Bar drawing method.
widget = widget.replace(
    "    def paintEvent(self, event):",
    "    def _paint_glass_bar(self, event):",
    1,
)

glass_method = widget.index("    def _paint_glass_bar(self, event):")

new_paint = '''    def paintEvent(self, event):
        if self.ui_mode == "glass":
            self._paint_glass_bar(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        t = time.perf_counter() - self.started
        active = False
        try:
            status = self.status_file.read_text(
                encoding="utf-8"
            ).strip().lower()
            active = status not in ("", "idle", "ready", "off", "sleeping")
        except (OSError, UnicodeError):
            pass

        cx, cy = self.width() / 2, self.height() / 2
        pulse = 0.5 + 0.5 * math.sin(t * (4.0 if active else 1.8))
        painter.setPen(Qt.PenStyle.NoPen)

        # Soft, restrained cyan-blue glow.
        glow = QRadialGradient(cx, cy, 49)
        glow.setColorAt(
            0, QColor(0, 155, 255, 34 if active else 15)
        )
        glow.setColorAt(1, QColor(0, 90, 255, 0))
        painter.setBrush(glow)
        painter.drawEllipse(2, 2, self.width() - 4, self.height() - 4)

        # Clean circular ring in Idle; brighter reactive plasma when Active.
        if not active:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(25, 165, 235, 65), 5))
            painter.drawEllipse(
                int(cx - 27), int(cy - 27), 54, 54
            )
            painter.setPen(QPen(QColor(55, 215, 255, 225), 2))
            painter.drawEllipse(
                int(cx - 27), int(cy - 27), 54, 54
            )
            painter.setPen(Qt.PenStyle.NoPen)
            dot = QRadialGradient(cx - 5, cy - 7, 29)
            dot.setColorAt(0, QColor(130, 250, 255, 220))
            dot.setColorAt(1, QColor(0, 135, 255, 0))
            painter.setBrush(dot)
            painter.drawEllipse(
                int(cx - 23), int(cy - 23), 46, 46
            )
        else:
            painter.setBrush(Qt.BrushStyle.NoBrush)

            # Several flowing paths create a compact plasma effect.
            for layer in range(3):
                path = QPainterPath()
                points = 120
                for i in range(points + 1):
                    angle = 2 * math.pi * i / points
                    wobble = (
                        math.sin(angle * 3 - t * 3.2 + layer) * 2.1
                        + math.sin(angle * 5 + t * 2.1) * 1.1
                    )
                    radius = 24 + layer * 2 + wobble + pulse * 1.5
                    x = cx + math.cos(angle) * radius
                    y = cy + math.sin(angle) * radius
                    if i == 0:
                        path.moveTo(x, y)
                    else:
                        path.lineTo(x, y)

                alpha = 45 if layer == 0 else (100 if layer == 1 else 220)
                width = 7 if layer == 0 else (3.5 if layer == 1 else 1.5)
                color = (
                    QColor(0, 160, 255, alpha)
                    if layer < 2
                    else QColor(100, 245, 255, alpha)
                )
                painter.setPen(QPen(color, width))
                painter.drawPath(path)

            painter.setPen(Qt.PenStyle.NoPen)
            core = QRadialGradient(cx, cy, 19)
            core.setColorAt(0, QColor(100, 245, 255, 120))
            core.setColorAt(1, QColor(0, 110, 255, 0))
            painter.setBrush(core)
            painter.drawEllipse(
                int(cx - 19), int(cy - 19), 38, 38
            )

        painter.end()

    def enterEvent(self, event):
        if self.ui_mode != "glass":
            old_x, old_y = self.x(), self.y()
            self.ui_mode = "glass"
            self.setFixedSize(390, 170)
            self.move(old_x - (390 - 104) // 2,
                      old_y - (170 - 104) // 2)
            self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.ui_mode == "glass":
            old_x, old_y = self.x(), self.y()
            self.ui_mode = "idle"
            self.setFixedSize(104, 104)
            self.move(old_x + (390 - 104) // 2,
                      old_y + (170 - 104) // 2)
            self.update()
        super().leaveEvent(event)

'''

widget = widget[:glass_method] + new_paint + widget[glass_method:]

# Validate both edited files in memory before touching the originals.
try:
    compile(main, str(MAIN), "exec")
    compile(widget, str(WIDGET), "exec")
except SyntaxError as exc:
    raise SystemExit(
        f"ERROR: Syntax validation failed; originals were not changed.\n{exc}"
    )

stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
backup_dir = ROOT / f"nova_ui_backup_{stamp}"
backup_dir.mkdir()

shutil.copy2(MAIN, backup_dir / "main.py")
shutil.copy2(WIDGET, backup_dir / "nova_widget.py")

try:
    MAIN.write_text(main, encoding="utf-8")
    WIDGET.write_text(widget, encoding="utf-8")

    py_compile.compile(str(MAIN), doraise=True)
    py_compile.compile(str(WIDGET), doraise=True)
except Exception:
    shutil.copy2(backup_dir / "main.py", MAIN)
    shutil.copy2(backup_dir / "nova_widget.py", WIDGET)
    raise SystemExit(
        f"ERROR: Validation failed. Original files restored from {backup_dir}"
    )

print("Nova UI rebuild applied and syntax-checked.")
print(f"Backup folder: {backup_dir}")
print("Glass Bar drawing method retained; microphone/audio handlers retained.")
print("Restart Nova before testing.")