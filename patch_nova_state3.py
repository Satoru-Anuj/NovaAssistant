from pathlib import Path
from datetime import datetime

path = Path("nova_widget.py")
source = path.read_text(encoding="utf-8")

if "_paint_active_plasma" in source:
    raise SystemExit(
        "State 3 plasma patch already exists. No changes made."
    )

old = '        active = state != "idle"'
if source.count(old) != 1:
    raise SystemExit(
        "Could not safely locate the active-state switch. No changes made."
    )

source = source.replace(
    old,
    '''        if state != "idle":
            painter.end()
            self._paint_active_plasma(t, state)
            return

        active = False''',
    1
)

anchor = "    def enterEvent(self, event):"
if source.count(anchor) != 1:
    raise SystemExit(
        "Could not safely locate the insertion point. No changes made."
    )

helper = '''    def _paint_active_plasma(self, t, state):
        """Animated cyan-blue plasma for Nova's active states."""
        painter = QPainter(self)
        painter.setRenderHint(
            QPainter.RenderHint.Antialiasing, True
        )

        # Clear the previous frame so transparent edges remain transparent.
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Clear
        )
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        speed = {
            "listening": 1.8,
            "thinking": 3.2,
            "speaking": 4.0,
        }.get(state, 2.5)

        pulse = 0.5 + 0.5 * math.sin(t * speed * 2.0)
        base = min(w, h) * 0.255

        # Soft cyan/blue aura.
        glow = QRadialGradient(cx, cy, min(w, h) * 0.49)
        glow.setColorAt(
            0.0, QColor(0, 170, 255, 22 + int(pulse * 28))
        )
        glow.setColorAt(
            0.42, QColor(35, 70, 255, 18 + int(pulse * 20))
        )
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(glow)
        painter.drawEllipse(
            cx - min(w, h) * 0.49,
            cy - min(w, h) * 0.49,
            min(w, h) * 0.98,
            min(w, h) * 0.98
        )

        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Several flowing strands create the plasma-ring effect.
        strands = [
            (QColor(0, 105, 255, 45), 7.0, 0.0),
            (QColor(0, 205, 255, 100), 4.2, 1.1),
            (QColor(100, 235, 255, 205), 2.0, 2.3),
            (QColor(235, 255, 255, 225), 0.9, 3.4),
        ]

        for strand_index, (color, pen_width, phase) in enumerate(strands):
            path = QPainterPath()

            for i in range(241):
                u = 2 * math.pi * i / 240
                wave = (
                    math.sin(u * 3.0 - t * speed + phase) * 2.2
                    + math.sin(u * 7.0 + t * speed * 0.72) * 1.0
                    + math.sin(u * 11.0 - t * speed * 1.4) * 0.45
                )
                radius = base + wave
                angle = u + math.sin(t * speed * 0.22 + phase) * 0.12
                x = cx + radius * math.cos(angle)
                y = cy + radius * 0.78 * math.sin(angle)

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            animated_color = QColor(color)
            if strand_index >= 2:
                animated_color.setAlpha(
                    min(255, color.alpha() + int(pulse * 25))
                )

            painter.setPen(QPen(
                animated_color,
                pen_width + (pulse * 0.8 if strand_index < 2 else 0),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin
            ))
            painter.drawPath(path)

        # Moving energy sparks around the ring.
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(9):
            angle = t * speed * 0.55 + i * (2 * math.pi / 9)
            wobble = math.sin(t * speed + i * 1.7) * 2.0
            radius = base + wobble
            x = cx + radius * math.cos(angle)
            y = cy + radius * 0.78 * math.sin(angle)
            dot = 1.1 + 1.1 * (
                0.5 + 0.5 * math.sin(t * speed * 2 + i)
            )
            painter.setBrush(QColor(125, 245, 255, 225))
            painter.drawEllipse(x - dot, y - dot, dot * 2, dot * 2)

        painter.end()

'''
source = source.replace(anchor, helper + anchor, 1)

# Validate before touching the original file.
compile(source, str(path), "exec")

backup = path.with_name(
    "nova_widget_before_state3_"
    + datetime.now().strftime("%Y%m%d_%H%M%S")
    + ".py"
)
backup.write_text(path.read_text(encoding="utf-8"), encoding="utf-8")
path.write_text(source, encoding="utf-8")

print("State 3 plasma patch applied.")
print("Backup:", backup)
