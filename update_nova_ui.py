from pathlib import Path
import re

p = Path("main.py")
if not p.exists():
    raise SystemExit("main.py not found. Open the NovaAssistant folder in the terminal first.")

source = p.read_text(encoding="utf-8")
backup = Path("main_before_futuristic_ui.py")
if not backup.exists():
    backup.write_text(source, encoding="utf-8")

def replace_method(code, name, replacement):
    pattern = rf"(?ms)^    def {re.escape(name)}\(.*?(?=^    def |\Z)"
    updated, count = re.subn(pattern, replacement.rstrip() + "\n\n", code, count=1)
    if count != 1:
        raise SystemExit(f"Could not safely locate method {name}(). No changes saved.")
    return updated

new_resize = '''    def set_expanded(self, expanded):
        if self.expanded == expanded:
            return

        self.expanded = expanded
        target = 270 if expanded else 104
        start = self.root.winfo_width()
        if start <= 1:
            start = self.window_w

        x = self.root.winfo_x()
        y = self.root.winfo_y()

        old_job = getattr(self, "resize_job", None)
        if old_job:
            try:
                self.root.after_cancel(old_job)
            except Exception:
                pass

        steps = 16
        duration_ms = 220

        def ease_out(t):
            return 1 - (1 - t) ** 4

        def frame(i):
            if self.closing:
                return
            t = min(1.0, i / steps)
            width = round(start + (target - start) * ease_out(t))
            self.window_w = width
            self.root.geometry(f"{width}x72+{x}+{y}")
            if i < steps:
                self.resize_job = self.root.after(
                    max(1, duration_ms // steps), lambda: frame(i + 1)
                )
            else:
                self.window_w = target
                self.root.geometry(f"{target}x72+{x}+{y}")
                self.resize_job = None

        frame(1)
'''

new_animate = '''    def animate(self):
        if self.closing:
            return

        canvas = self.canvas
        canvas.delete("all")

        w = max(self.root.winfo_width(), 104)
        h = 72
        self.window_w = w

        # Draw a clean, softly rounded black Dynamic Island.
        radius = 32
        points = []
        corners = [
            (w - 3 - radius, 3 + radius, -90, 0),
            (w - 3 - radius, h - 3 - radius, 0, 90),
            (3 + radius, h - 3 - radius, 90, 180),
            (3 + radius, 3 + radius, 180, 270),
        ]
        for cx0, cy0, start_angle, end_angle in corners:
            for j in range(13):
                a = math.radians(start_angle + (end_angle - start_angle) * j / 12)
                points.append((cx0 + radius * math.cos(a), cy0 + radius * math.sin(a)))
        flat = [v for point in points for v in point]
        canvas.create_polygon(flat, fill="#030509", outline="#111722", width=1)

        # Smooth colour wheel for the RGB trails.
        def rgb(hue, brightness=1.0):
            r, g, b = colorsys.hsv_to_rgb(hue % 1.0, 0.88, brightness)
            return f"#{int(r*255):02x}{int(g*255):02x}{int(b*255):02x}"

        active = self.busy or self.status not in ("idle", "ready")
        speed = 2.2 if active else 0.8
        self.angle = (self.angle + speed) % 360
        phase = math.radians(self.angle)

        cx, cy = 52, 36
        rings = [
            (13.0, 0.0, 1.0),
            (19.0, 125.0, -0.8),
            (25.0, 245.0, 0.65),
        ]

        # Fine, subtle base rings.
        for radius0, offset, direction in rings:
            coords = []
            for j in range(73):
                a = 2 * math.pi * j / 72
                coords.extend((cx + radius0 * math.cos(a), cy + radius0 * math.sin(a)))
            canvas.create_line(
                *coords, fill="#17232e", width=1, smooth=True
            )

            # Layered trails create a luminous edge without heavy blur effects.
            trail_length = 1.55 if active else 1.15
            start = phase * direction + math.radians(offset)
            segments = 24
            for j in range(segments):
                a1 = start + trail_length * j / segments
                a2 = start + trail_length * (j + 1) / segments
                x1, y1 = cx + radius0 * math.cos(a1), cy + radius0 * math.sin(a1)
                x2, y2 = cx + radius0 * math.cos(a2), cy + radius0 * math.sin(a2)
                hue = (j / segments + offset / 360 + phase / (2 * math.pi)) % 1.0

                # A dim outer trace and a sharper coloured core.
                canvas.create_line(x1, y1, x2, y2, fill=rgb(hue, 0.45), width=4)
                canvas.create_line(x1, y1, x2, y2, fill=rgb(hue, 1.0), width=1.7)

            # A moving light particle at the end of each trail.
            tip = start + trail_length
            px = cx + radius0 * math.cos(tip)
            py = cy + radius0 * math.sin(tip)
            canvas.create_oval(px-2, py-2, px+2, py+2, fill="#f5fdff", outline="")

        # Small, understated centre glint.
        canvas.create_oval(cx-2, cy-2, cx+2, cy+2, fill="#d9fbff", outline="")

        # Compact, minimal controls appear only when expanded.
        if self.expanded:
            mic_x = w - 43
            other_x = w - 83

            # Tiny microphone icon, drawn from simple clean strokes.
            canvas.create_oval(
                mic_x-3.5, 25, mic_x+3.5, 37,
                outline="#d8e4f0", width=1.4
            )
            canvas.create_arc(
                mic_x-7, 27, mic_x+7, 42,
                start=200, extent=140, style="arc",
                outline="#8fa8bd", width=1.2
            )
            canvas.create_line(
                mic_x, 40, mic_x, 44, fill="#d8e4f0", width=1.3
            )
            canvas.create_line(
                mic_x-4, 44, mic_x+4, 44,
                fill="#d8e4f0", width=1.3
            )

            # Small secondary control: a restrained three-dot glyph.
            for k in range(3):
                xx = other_x + (k - 1) * 4
                canvas.create_oval(
                    xx-1, 35, xx+1, 37,
                    fill="#9db3c7", outline=""
                )

        self.root.after(24, self.animate)
'''

try:
    source = replace_method(source, "set_expanded", new_resize)
    source = replace_method(source, "animate", new_animate)

    if "import colorsys" not in source:
        source = source.replace("import math", "import math\\nimport colorsys", 1)

    p.write_text(source, encoding="utf-8")
except Exception as exc:
    raise SystemExit(f"Patch failed: {exc}")

print("Nova UI updated. Backup: main_before_futuristic_ui.py")
