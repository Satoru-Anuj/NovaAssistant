
from pathlib import Path
import shutil
import py_compile
from datetime import datetime

target = Path("nova_widget.py")

if not target.is_file():
    raise SystemExit("ERROR: Open the NovaAssistant project folder first.")

source = target.read_text(encoding="utf-8")

start = source.find("    def paintEvent(self, event):")
end = source.find("    def enterEvent(self, event):", start)

if start < 0 or end < 0 or "_paint_glass_bar(self, event)" not in source:
    raise SystemExit("ERROR: Expected methods not found. No changes made.")

backup = target.with_name(
    f"nova_widget.py.before_mobius_{datetime.now():%Y%m%d_%H%M%S}.bak"
)
shutil.copy2(target, backup)

new_method = '''    def paintEvent(self, event):
        if self.ui_mode == "glass":
            self._paint_glass_bar(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        t = time.perf_counter() - self.started
        active = False

        try:
            status = self.status_file.read_text(encoding="utf-8").strip().lower()
            active = status not in ("", "idle", "ready", "off", "sleeping")
        except (OSError, UnicodeError):
            pass

        w, h = self.width(), self.height()
        cx, cy = w / 2, h / 2
        pulse = 0.5 + 0.5 * math.sin(t * (3.8 if active else 1.3))

        if not active:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(2, 5, 12, 238))
            painter.drawRoundedRect(10, 8, w - 20, h - 16, 18, 18)

        radius = min(w, h) * (0.245 if active else 0.205)
        width = min(w, h) * (0.105 if active else 0.075)
        stretch = 1 + (0.20 * pulse if active else 0.035 * pulse)

        ax, ay, az = t * 0.78, t * 0.93, t * 0.58
        sx, cxr = math.sin(ax), math.cos(ax)
        sy, cyr = math.sin(ay), math.cos(ay)
        sz, czr = math.sin(az), math.cos(az)

        def project(u, v):
            wave = math.sin(u * 3 - t * 2) * (0.035 if active else 0.012)
            r = radius * (1 + wave)
            x = (r + v * math.cos(u / 2)) * math.cos(u) * stretch
            y = (r + v * math.cos(u / 2)) * math.sin(u)
            z = v * math.sin(u / 2) + math.sin(u * 2 + t) * radius * 0.1

            y, z = y * cxr - z * sx, y * sx + z * cxr
            x, z = x * cyr + z * sy, -x * sy + z * cyr
            x, y = x * czr - y * sz, x * sz + y * czr

            camera = min(w, h) * 1.65
            factor = camera / max(camera * 0.62, camera - z)
            return cx + x * factor, cy + y * factor, z

        faces = []
        us, vs = 112, 8

        for i in range(us):
            u0, u1 = 2 * math.pi * i / us, 2 * math.pi * (i + 1) / us
            for j in range(vs):
                v0 = width * (2 * j / vs - 1)
                v1 = width * (2 * (j + 1) / vs - 1)
                pts = [
                    project(u0, v0), project(u1, v0),
                    project(u1, v1), project(u0, v1)
                ]
                depth = sum(p[2] for p in pts) / 4
                mix = (math.sin(2 * math.pi * (
                    i / us + t * (0.055 if active else 0.022)
                ) - 0.8) + 1) / 2
                light = max(0, min(1, 0.5 + depth / (radius * 1.7)))
                color = QColor(
                    min(255, int(35 + 190 * (1 - mix) + 20 * light)),
                    min(255, int(65 + 165 * mix)),
                    min(255, int(150 + 100 * mix)),
                    int(135 + 100 * light)
                )
                faces.append((depth, pts, color))

        painter.setPen(Qt.PenStyle.NoPen)
        for depth, pts, color in sorted(faces, key=lambda f: f[0]):
            path = QPainterPath()
            path.moveTo(pts[0][0], pts[0][1])
            for px, py, _ in pts[1:]:
                path.lineTo(px, py)
            path.closeSubpath()
            painter.setBrush(color)
            painter.drawPath(path)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(
            QColor(100, 245, 255, 105 if not active else 190),
            1.0 if not active else 1.35
        ))

        for edge in (-1, 1):
            path = QPainterPath()
            for i in range(us + 1):
                px, py, _ = project(2 * math.pi * i / us, edge * width)
                if i == 0:
                    path.moveTo(px, py)
                else:
                    path.lineTo(px, py)
            painter.drawPath(path)

        painter.end()

'''

updated = source[:start] + new_method + source[end:]

# Validate syntax before replacing the original.
check = target.with_name("_nova_mobius_syntax_check.py")
check.write_text(updated, encoding="utf-8")

try:
    py_compile.compile(str(check), doraise=True)
finally:
    check.unlink(missing_ok=True)

target.write_text(updated, encoding="utf-8")

print("SUCCESS: Möbius animation installed.")
print(f"Backup saved: {backup}")
print("Glass Bar method and main.py were preserved.")
