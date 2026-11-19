from pathlib import Path
from datetime import datetime
import re
import py_compile
import shutil
import sys

file = Path("nova_widget.py")
if not file.is_file():
    raise SystemExit("ERROR: nova_widget.py was not found. Run this from the project folder.")

source = file.read_text(encoding="utf-8")

if "def _paint_glass_bar(self, event):" not in source:
    raise SystemExit("ERROR: Glass Bar method not found; file was not changed.")

if "def mouseReleaseEvent(self, event):" not in source:
    raise SystemExit("ERROR: Click handlers not found; file was not changed.")

backup = file.with_name(
    f"nova_widget.py.pre_visual_redesign_{datetime.now():%Y%m%d_%H%M%S}.bak"
)
shutil.copy2(file, backup)

new_glass = r"""    def _paint_glass_bar(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        t = time.perf_counter() - self.started
        try:
            status = self.status_file.read_text(
                encoding="utf-8"
            ).strip().lower()
        except (OSError, UnicodeError):
            status = "idle"

        if any(s in status for s in ("speak", "response", "output")):
            state = "speaking"
        elif any(s in status for s in ("listen", "record", "microphone")):
            state = "listening"
        elif any(s in status for s in ("think", "process", "working")):
            state = "thinking"
        else:
            state = "idle"

        speed = {"idle": 0.8, "listening": 2.8,
                 "thinking": 5.0, "speaking": 2.0}[state]
        pulse = (1.0 + math.sin(t * speed)) / 2.0

        # Atmospheric cyan/violet halo.
        halo = QRadialGradient(190, 85, 185)
        halo.setColorAt(
            0.0, QColor(20, 150, 225, 25 + int(pulse * 26))
        )
        halo.setColorAt(
            0.48, QColor(75, 40, 180, 12 + int(pulse * 12))
        )
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(5, 3, 380, 164)

        # Dark smoked-glass capsule with a subtle luminous rim.
        pill = QPainterPath()
        pill.addRoundedRect(22, 43, 346, 84, 42, 42)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(3, 7, 16, 242))
        painter.drawPath(pill)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(
            QColor(100, 205, 255, 75 + int(pulse * 65)), 1.25
        ))
        painter.drawPath(pill)

        # Restrained inner edge and top glass reflection.
        inner = QPainterPath()
        inner.addRoundedRect(25, 46, 340, 78, 39, 39)
        painter.setPen(QPen(QColor(255, 255, 255, 15), 0.8))
        painter.drawPath(inner)

        reflection = QPainterPath()
        reflection.moveTo(65, 46)
        reflection.cubicTo(120, 42, 270, 42, 325, 46)
        painter.setPen(QPen(QColor(225, 245, 255, 48), 1.0))
        painter.drawPath(reflection)

        # Animated infinity ribbon.
        amp = {
            "idle": 1.4, "listening": 5.5,
            "thinking": 7.0, "speaking": 4.0
        }[state]
        phase = t * speed
        loop = QPainterPath()
        loop.moveTo(86, 84)
        loop.cubicTo(
            75, 65 + math.sin(phase) * amp,
            52, 63 - math.sin(phase * 1.2) * amp,
            46, 81
        )
        loop.cubicTo(
            40, 99, 64, 105 + math.sin(phase) * amp,
            80, 88
        )
        loop.cubicTo(
            96, 71, 107, 64 - math.sin(phase * 0.8) * amp,
            119, 78
        )
        loop.cubicTo(133, 94, 107, 106, 86, 84)

        painter.setPen(QPen(
            QColor(80, 35, 255, 55 + int(pulse * 65)), 15,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        ))
        painter.drawPath(loop)

        painter.setPen(QPen(
            QColor(170, 65, 255, 235), 6.0,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        ))
        painter.drawPath(loop)

        painter.setPen(QPen(
            QColor(45, 220 + int(pulse * 35), 255, 250), 2.5,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        ))
        painter.drawPath(loop)

        ridge = QPainterPath()
        ridge.moveTo(103, 73)
        ridge.cubicTo(115, 70, 124, 81, 115, 92)
        painter.setPen(QPen(
            QColor(160, 255, 245, 225), 1.4,
            Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap
        ))
        painter.drawPath(ridge)

        # Brand label and live state.
        painter.setPen(QColor(225, 237, 250, 225))
        font = painter.font()
        font.setFamily("Segoe UI")
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(66, 112, "N O V A")

        state_label = {
            "idle": "READY",
            "listening": "LISTENING",
            "thinking": "THINKING",
            "speaking": "SPEAKING"
        }[state]
        painter.setPen(QColor(
            110, 225, 255, 205 if state != "idle" else 145
        ))
        font.setPixelSize(7)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(139, 88, state_label)

        # Inset glass control capsule; original click zones retained.
        control = QPainterPath()
        control.addRoundedRect(245, 66, 94, 38, 19, 19)
        painter.setPen(QPen(QColor(200, 225, 255, 95), 0.9))
        painter.setBrush(QColor(12, 18, 30, 247))
        painter.drawPath(control)

        top = QPainterPath()
        top.moveTo(263, 68)
        top.cubicTo(282, 65, 304, 65, 321, 68)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(255, 255, 255, 45), 0.8))
        painter.drawPath(top)

        # Home icon: hit area x=248..271.
        home = QPainterPath()
        home.moveTo(252, 82)
        home.lineTo(260, 75)
        home.lineTo(268, 82)
        home.moveTo(255, 81)
        home.lineTo(255, 91)
        home.lineTo(265, 91)
        home.lineTo(265, 81)
        painter.setPen(QPen(
            QColor(240, 248, 255, 240), 1.6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        ))
        painter.drawPath(home)
        painter.drawLine(259, 91, 259, 85)

        # Audio icon: hit area x=273..301.
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(230, 245, 255, 245))
        painter.drawRoundedRect(275, 81, 3, 8, 1, 1)
        painter.drawRoundedRect(280, 76, 3, 18, 1, 1)
        painter.drawRoundedRect(285, 73, 3, 24, 1, 1)
        painter.drawRoundedRect(290, 78, 3, 14, 1, 1)
        painter.drawRoundedRect(295, 82, 3, 6, 1, 1)

        # Microphone icon: hit area x=305..329.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(
            QColor(240, 248, 255, 245), 1.6,
            Qt.PenStyle.SolidLine,
            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin
        ))
        painter.drawRoundedRect(312, 74, 9, 16, 4, 4)
        painter.drawArc(308, 78, 17, 18, 180 * 16, 180 * 16)
        painter.drawLine(316, 96, 316, 99)
        painter.drawLine(311, 99, 321, 99)

        # State accent around the controls.
        if state != "idle":
            accent = {
                "listening": QColor(35, 220, 255, 65 + int(pulse * 75)),
                "thinking": QColor(155, 95, 255, 65 + int(pulse * 75)),
                "speaking": QColor(80, 225, 255, 65 + int(pulse * 85))
            }[state]
            painter.setPen(QPen(accent, 1.15))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(245, 66, 94, 38, 19, 19)

        painter.end()
"""

try:
    start = source.index("    def _paint_glass_bar(self, event):")
    end = source.index("    def mouseReleaseEvent(self, event):", start)
    source = source[:start] + new_glass + "\n" + source[end:]

    # Add glow behind the existing 3D mesh only when Active.
    marker = "        faces = []\n        us, vs = 112, 8"
    glow_code = """        if active:
            glow = QRadialGradient(cx, cy, min(w, h) * 0.49)
            glow.setColorAt(0.0, QColor(0, 190, 255, 35 + int(pulse * 24)))
            glow.setColorAt(0.48, QColor(85, 55, 255, 18 + int(pulse * 12)))
            glow.setColorAt(1.0, QColor(0, 0, 0, 0))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(glow)
            painter.drawEllipse(
                cx - min(w, h) * 0.49,
                cy - min(w, h) * 0.49,
                min(w, h) * 0.98,
                min(w, h) * 0.98
            )

        faces = []
        us, vs = 112, 8"""
    if source.count(marker) != 1:
        raise RuntimeError("Could not uniquely locate the Active mesh; refusing to save.")
    source = source.replace(marker, glow_code, 1)

    file.write_text(source, encoding="utf-8")
    py_compile.compile(str(file), doraise=True)
    print("SUCCESS: Glass Bar and Active visuals patched.")
    print(f"Backup: {backup}")
    print("Python syntax check passed.")
except Exception as exc:
    shutil.copy2(backup, file)
    print(f"PATCH FAILED: {exc}")
    print("Original file restored from backup.")
    sys.exit(1)
