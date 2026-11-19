
from pathlib import Path
import py_compile
import shutil
import sys

folder = Path(__file__).resolve().parent
target = folder / "nova_widget.py"
backup = folder / "nova_widget_before_idle_active_backup.py"

if not target.exists():
    sys.exit("ERROR: nova_widget.py was not found in this folder.")

source = target.read_text(encoding="utf-8")

if "NOVA_UI_STATES_PATCHED" in source:
    print("The UI states patch is already installed.")
    sys.exit(0)

paint_anchor = "    def paintEvent(self, event):"
mouse_anchor = "        self.setMouseTracking(True)"

if source.count(paint_anchor) != 1:
    sys.exit("STOP: Expected exactly one paintEvent method. No changes made.")

if mouse_anchor not in source:
    sys.exit("STOP: Mouse-tracking anchor not found. No changes made.")

# Save the original before editing.
shutil.copy2(target, backup)

# Preserve the original Glass Bar renderer exactly.
source = source.replace(
    paint_anchor,
    "    def paint_glass_bar(self, event):",
    1
)

# Add the new state-based renderer before the preserved Glass Bar renderer.
new_renderer = '''
    # NOVA_UI_STATES_PATCHED
    def paintEvent(self, event):
        if self.underMouse():
            self.paint_glass_bar(event)
        elif self.active_state:
            self.paint_active_core(event)
        else:
            self.paint_idle_core(event)

    def paint_idle_core(self, event):
        from PySide6.QtGui import QRadialGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        cx, cy = self.width() / 2, self.height() / 2
        radius = 37

        aura = QRadialGradient(cx, cy, 78)
        aura.setColorAt(0.0, QColor(0, 220, 255, 95))
        aura.setColorAt(0.45, QColor(20, 110, 255, 35))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(aura)
        p.drawEllipse(int(cx - 78), int(cy - 78), 156, 156)

        shell = QRadialGradient(cx - 13, cy - 16, radius * 1.8)
        shell.setColorAt(0.0, QColor(220, 255, 255, 245))
        shell.setColorAt(0.22, QColor(65, 220, 255, 235))
        shell.setColorAt(0.62, QColor(25, 110, 220, 245))
        shell.setColorAt(1.0, QColor(8, 20, 60, 250))
        p.setBrush(shell)
        p.setPen(QPen(QColor(150, 245, 255, 220), 1.5))
        p.drawEllipse(int(cx - radius), int(cy - radius),
                      int(radius * 2), int(radius * 2))

        core = QRadialGradient(cx - 8, cy - 10, radius)
        core.setColorAt(0.0, QColor(255, 255, 255, 235))
        core.setColorAt(0.25, QColor(90, 245, 255, 210))
        core.setColorAt(1.0, QColor(25, 95, 210, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(core)
        p.drawEllipse(int(cx - radius + 5), int(cy - radius + 5),
                      int(radius * 2 - 10), int(radius * 2 - 10))

        p.setBrush(QColor(255, 255, 255, 210))
        p.drawEllipse(int(cx - 17), int(cy - 22), 13, 7)

        p.setPen(QColor(175, 235, 255, 200))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.drawText(0, int(cy + 55), self.width(), 18,
                   Qt.AlignmentFlag.AlignHCenter, "N O V A")
        p.end()

    def paint_active_core(self, event):
        from PySide6.QtGui import QRadialGradient

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        cx, cy = self.width() / 2, self.height() / 2
        t = time.time()
        radius = 30

        aura = QRadialGradient(cx, cy, 83)
        aura.setColorAt(0.0, QColor(0, 220, 255, 115))
        aura.setColorAt(0.5, QColor(105, 50, 255, 45))
        aura.setColorAt(1.0, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(aura)
        p.drawEllipse(int(cx - 83), int(cy - 83), 166, 166)

        for i in range(3):
            p.save()
            p.translate(cx, cy)
            p.rotate(t * (35 if i % 2 == 0 else -27) + i * 60)
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(
                QColor(60 + i * 45, 220 - i * 20, 255, 180),
                2.0 if i == 0 else 1.3
            ))
            p.drawEllipse(-radius - i * 8, -radius // 2 - i * 5,
                          (radius + i * 8) * 2, radius + i * 10)
            p.restore()

        core = QRadialGradient(cx - 9, cy - 11, radius * 1.8)
        core.setColorAt(0.0, QColor(255, 255, 255, 250))
        core.setColorAt(0.3, QColor(70, 250, 255, 245))
        core.setColorAt(0.7, QColor(75, 90, 255, 240))
        core.setColorAt(1.0, QColor(30, 15, 100, 245))
        p.setBrush(core)
        p.setPen(QPen(QColor(160, 255, 255, 235), 1.4))
        p.drawEllipse(int(cx - radius), int(cy - radius),
                      radius * 2, radius * 2)

        for i in range(8):
            angle = t * 1.2 + i * math.pi / 4
            x = cx + math.cos(angle) * 52
            y = cy + math.sin(angle) * 36
            p.setPen(Qt.PenStyle.NoPen)
            p.setBrush(QColor(125, 240, 255, 210))
            p.drawEllipse(int(x - 2), int(y - 2), 4, 4)

        p.setPen(QColor(190, 220, 255, 220))
        p.setFont(QFont("Segoe UI", 8, QFont.Weight.DemiBold))
        p.drawText(0, int(cy + 55), self.width(), 18,
                   Qt.AlignmentFlag.AlignHCenter, "N O V A")
        p.end()

'''

source = source.replace(
    "    def paint_glass_bar(self, event):",
    new_renderer + "    def paint_glass_bar(self, event):",
    1
)

# Initialize the active state in the widget constructor.
source = source.replace(
    mouse_anchor,
    mouse_anchor + '''
        self.active_state = False
''',
    1
)

# Toggle the orb/plasma state when the microphone is clicked.
click_anchor = "            self.microphoneClicked.emit()"
if source.count(click_anchor) != 1:
    shutil.copy2(backup, target)
    sys.exit("STOP: Mic-click anchor was unexpected. Original restored.")

source = source.replace(
    click_anchor,
    '''            self.active_state = not self.active_state
            self.update()
            self.microphoneClicked.emit()''',
    1
)

target.write_text(source, encoding="utf-8")

try:
    py_compile.compile(str(target), doraise=True)
except Exception:
    shutil.copy2(backup, target)
    print("Compilation failed. Original nova_widget.py was restored.")
    raise

print("Patch applied and syntax check passed.")
print(f"Original backup: {backup}")
