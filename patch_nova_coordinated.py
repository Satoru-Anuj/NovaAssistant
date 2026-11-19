from pathlib import Path
from datetime import datetime
import ast

current_path = Path("nova_widget.py")
backup_path = Path("nova_widget.py.before_ring_redesign.bak")

if not current_path.exists() or not backup_path.exists():
    raise SystemExit("Required source or original animation backup is missing.")

current = current_path.read_text(encoding="utf-8-sig")
original = backup_path.read_text(encoding="utf-8-sig")

def parse(source, label):
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        raise SystemExit(f"{label} has invalid syntax: {exc}")

def method_source(source, tree, method_name):
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == method_name:
            lines = source.splitlines(keepends=True)
            return "".join(lines[node.lineno - 1:node.end_lineno])
    raise SystemExit(f"Could not find method: {method_name}")

current_tree = parse(current, "Current widget")
original_tree = parse(original, "Original backup")

if "_draw_matching_ring" in current:
    raise SystemExit("Repair already applied; no changes made.")

# Recover the exact previous idle renderer.
old_paint = method_source(original, original_tree, "paintEvent")

status_block = '''        active = False

        try:
            status = self.status_file.read_text(encoding="utf-8").strip().lower()
            active = status not in ("", "idle", "ready", "off", "sleeping")
        except (OSError, UnicodeError):
            pass

        w, h = self.width(), self.height()'''

if status_block not in old_paint:
    raise SystemExit("Original idle renderer did not match expected structure.")

new_status_block = '''        status = "idle"
        try:
            status = self.status_file.read_text(
                encoding="utf-8"
            ).strip().lower()
        except (OSError, UnicodeError):
            pass

        if any(word in status for word in ("speak", "response", "output")):
            state = "speaking"
        elif any(word in status for word in ("listen", "record", "microphone")):
            state = "listening"
        elif any(word in status for word in ("think", "process", "working")):
            state = "thinking"
        elif status in ("", "idle", "ready", "off", "sleeping"):
            state = "idle"
        else:
            state = "thinking"

        if state != "idle":
            painter.end()
            self._paint_active_plasma(t, state)
            return

        active = False
        w, h = self.width(), self.height()'''

old_paint = old_paint.replace(status_block, new_status_block, 1)

# Keep the existing Glass Bar layout and controls.
glass_start = current.find(
    "        # Rotating 3D-style torus ring. No infinity ribbon."
)
glass_end = current.find(
    "        # Brand label and current activity.", glass_start
)
if glass_start < 0 or glass_end < 0:
    raise SystemExit("Glass Bar ring section not found; no changes made.")

glass_ring = '''        # Same 3D ring geometry as the original idle animation.
        self._draw_matching_ring(
            painter, t, 82.0, 84.0, 104.0, state
        )

'''

current = current[:glass_start] + glass_ring + current[glass_end:]

# Replace the idle renderer only; keep the rest of the widget untouched.
current_tree = parse(current, "Widget before repair")
current_paint = method_source(current, current_tree, "paintEvent")
current = current.replace(current_paint, old_paint, 1)

# Extract the original ring's geometry so both states share the same shape.
geometry_start = old_paint.find("        radius = min(w, h) *")
geometry_end = old_paint.rfind("        painter.end()")
if geometry_start < 0 or geometry_end < geometry_start:
    raise SystemExit("Could not extract the original ring geometry.")

geometry = old_paint[geometry_start:geometry_end]
geometry = geometry.replace(
    "ax, ay, az = t * 0.78, t * 0.93, t * 0.58",
    "ax, ay, az = (t * 0.78 * motion, "
    "t * 0.93 * motion, t * 0.58 * motion)"
)
geometry = geometry.replace(
    "u * 3 - t * 2",
    "u * 3 - t * 2 * motion"
)
geometry = geometry.replace(
    "i / us + t * (0.055 if active else 0.022)",
    "i / us + t * motion * (0.055 if active else 0.022)"
)

ring_helper = '''    def _draw_matching_ring(self, painter, t, cx, cy, size, state="idle"):
        """Draw the original idle ring, scaled for the Glass Bar."""
        w = h = size
        active = state != "idle"
        motion = {
            "idle": 1.0,
            "listening": 1.0,
            "thinking": 1.7,
            "speaking": 2.5,
        }.get(state, 1.0)
        pulse = 0.5 + 0.5 * math.sin(
            t * (3.8 if active else 1.3) * motion
        )
''' + geometry + '''\n
'''

active_helper = '''    def _paint_active_plasma(self, t, state):
        """Action-specific animations while Nova is active."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_Clear
        )
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))
        painter.setCompositionMode(
            QPainter.CompositionMode.CompositionMode_SourceOver
        )

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        base = min(w, h) * 0.255
        pulse = 0.5 + 0.5 * math.sin(t * 3.0)

        # Give each action its own motion and visual character.
        if state == "listening":
            speed = 1.8
            amplitude = 1.1
            strands = 2
            spark_count = 6
            colors = [
                QColor(0, 185, 255, 150),
                QColor(110, 245, 255, 220),
            ]
        elif state == "thinking":
            speed = 2.6
            amplitude = 2.3
            strands = 3
            spark_count = 8
            colors = [
                QColor(55, 105, 255, 160),
                QColor(125, 100, 255, 205),
                QColor(70, 210, 255, 225),
            ]

            # Orbiting ellipses distinguish the thinking state.
            painter.save()
            painter.translate(cx, cy)
            painter.rotate((t * 48.0) % 360.0)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(85, 155, 255, 115), 1.2))
            painter.drawEllipse(
                -base * 1.25, -base * 0.42,
                base * 2.5, base * 0.84
            )
            painter.restore()
        else:
            speed = 4.0
            amplitude = 3.5
            strands = 4
            spark_count = 12
            colors = [
                QColor(0, 115, 255, 95),
                QColor(0, 200, 255, 155),
                QColor(100, 235, 255, 215),
                QColor(240, 255, 255, 230),
            ]

        # Listening uses expanding ripples around the ring.
        if state == "listening":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            for index in range(3):
                ripple = base + 5 + index * 5 + pulse * 4
                painter.setPen(QPen(
                    QColor(0, 190, 255, 55 - index * 12), 1.2
                ))
                painter.drawEllipse(
                    cx - ripple, cy - ripple,
                    ripple * 2, ripple * 2
                )

        # Flowing plasma strands.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        for strand in range(strands):
            path = QPainterPath()
            phase = strand * 0.9

            for i in range(241):
                u = 2 * math.pi * i / 240
                wave = (
                    math.sin(u * 3 - t * speed + phase) * amplitude
                    + math.sin(u * 7 + t * speed * 0.72 + phase) * 0.9
                )
                if state == "speaking":
                    wave += math.sin(u * 11 - t * speed * 1.35) * 0.8

                radius = base + wave
                angle = u + math.sin(t * speed * 0.22 + phase) * 0.12
                x = cx + radius * math.cos(angle)
                y = cy + radius * 0.78 * math.sin(angle)

                if i == 0:
                    path.moveTo(x, y)
                else:
                    path.lineTo(x, y)

            color = QColor(colors[strand])
            color.setAlpha(min(
                255, color.alpha() + int(pulse * 20)
            ))
            painter.setPen(QPen(
                color,
                1.0 + (0.8 if state == "speaking" else 0.0),
                Qt.PenStyle.SolidLine,
                Qt.PenCapStyle.RoundCap,
                Qt.PenJoinStyle.RoundJoin
            ))
            painter.drawPath(path)

        # Moving energy points.
        painter.setPen(Qt.PenStyle.NoPen)
        for i in range(spark_count):
            angle = (
                t * speed * (0.35 if state == "listening" else 0.7)
                + i * (2 * math.pi / spark_count)
            )
            radius = base + math.sin(t * speed + i) * amplitude
            x = cx + radius * math.cos(angle)
            y = cy + radius * 0.78 * math.sin(angle)
            dot = 1.2 + pulse * (
                1.0 if state == "speaking" else 0.5
            )
            painter.setBrush(colors[i % len(colors)])
            painter.drawEllipse(
                x - dot, y - dot, dot * 2, dot * 2
            )

        painter.end()

'''

# Replace the current active renderer.
tree = parse(current, "Widget with restored idle renderer")
old_active = method_source(current, tree, "_paint_active_plasma")
current = current.replace(old_active, active_helper, 1)

# Insert the shared ring renderer.
anchor = "    def _paint_active_plasma("
if current.count(anchor) != 1:
    raise SystemExit("Active renderer insertion point is ambiguous.")

current = current.replace(anchor, ring_helper + anchor, 1)

# Validate the complete result before writing any changes.
final_tree = parse(current, "Final repaired widget")
names = [
    n.name for n in ast.walk(final_tree)
    if isinstance(n, ast.FunctionDef)
]
for required in ("paintEvent", "_draw_matching_ring", "_paint_active_plasma",
                 "_paint_glass_bar"):
    if required not in names:
        raise SystemExit(f"Validation failed: missing {required}")

backup = current_path.with_name(
    "nova_widget_before_coordinated_repair_"
    + datetime.now().strftime("%Y%m%d_%H%M%S") + ".py"
)
backup.write_text(
    current_path.read_text(encoding="utf-8-sig"),
    encoding="utf-8"
)
current_path.write_text(current, encoding="utf-8")

print("Coordinated Nova animation repair applied.")
print("Original idle renderer restored.")
print("Glass Bar now reuses the same ring geometry.")
print("Listening, thinking, and speaking have distinct animations.")
print("Backup created:", backup)
