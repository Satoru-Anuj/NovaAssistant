from pathlib import Path
import shutil
import py_compile
import sys

ROOT = Path(__file__).resolve().parent
WIDGET = ROOT / "nova_widget.py"
MAIN = ROOT / "main.py"
STATE = ROOT / "nova_ui_state.txt"

BACKUPS = {
    WIDGET: ROOT / "nova_widget.py.before_ring_redesign.bak",
    MAIN: ROOT / "main.py.before_ring_redesign.bak",
}

for path in (WIDGET, MAIN):
    if not path.is_file():
        raise SystemExit(f"Missing required file: {path.name}")

for path, backup in BACKUPS.items():
    if not backup.exists():
        shutil.copy2(path, backup)

original_widget = WIDGET.read_text(encoding="utf-8")
original_main = MAIN.read_text(encoding="utf-8")

widget = original_widget
main = original_main

def replace_once(source, old, new, label):
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected one match, found {count}")
    return source.replace(old, new, 1)

try:
    # Accelerate the existing Idle ring when Nova is active.
    old_status = '''        active = False

        try:
            status = self.status_file.read_text(encoding="utf-8").strip().lower()
            active = status not in ("", "idle", "ready", "off", "sleeping")
        except (OSError, UnicodeError):
            pass
'''
    new_status = '''        status = "idle"
        try:
            status = self.status_file.read_text(encoding="utf-8").strip().lower()
        except (OSError, UnicodeError):
            pass

        if any(s in status for s in ("speak", "response", "output")):
            state = "speaking"
        elif any(s in status for s in ("listen", "record", "microphone")):
            state = "listening"
        elif any(s in status for s in ("think", "process", "working")):
            state = "thinking"
        else:
            state = "idle"

        active = state != "idle"
        state_speed = {
            "idle": 1.3, "listening": 8.0,
            "thinking": 13.0, "speaking": 10.0
        }[state]
'''
    widget = replace_once(widget, old_status, new_status, "Idle ring status")

    widget = replace_once(
        widget,
        'pulse = 0.5 + 0.5 * math.sin(t * (3.8 if active else 1.3))',
        'pulse = 0.5 + 0.5 * math.sin(t * state_speed)',
        "Idle ring pulse"
    )
    widget = replace_once(
        widget,
        'ax, ay, az = t * 0.78, t * 0.93, t * 0.58',
        'ax, ay, az = t * state_speed * 0.20, t * state_speed * 0.24, t * state_speed * 0.15',
        "Idle ring rotation"
    )
    widget = replace_once(
        widget,
        't * (0.055 if active else 0.022)',
        't * (0.11 if active else 0.022)',
        "Idle ring colour animation"
    )

    # Replace the complete Glass Bar painter, preserving event handlers.
    method_start = widget.find("    def _paint_glass_bar(self, event):")
    next_method = widget.find("    def mouseReleaseEvent(self, event):", method_start)
    if method_start < 0 or next_method < 0:
        raise RuntimeError("Could not safely locate Glass Bar painter boundaries")

    new_glass = r'''    def _paint_glass_bar(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        t = time.perf_counter() - self.started
        try:
            status = self.status_file.read_text(encoding="utf-8").strip().lower()
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

        speeds = {"idle": 1.7, "listening": 8.5, "thinking": 13.5, "speaking": 10.5}
        speed = speeds[state]
        pulse = (1.0 + math.sin(t * speed)) / 2.0

        # Read actual toggle states; assume ON before the first toggle.
        ui_state = {"mic": "on", "audio": "on"}
        try:
            state_path = Path(__file__).with_name("nova_ui_state.txt")
            for line in state_path.read_text(encoding="utf-8").splitlines():
                if "=" in line:
                    key, value = line.split("=", 1)
                    if key.strip() in ui_state and value.strip() in ("on", "off"):
                        ui_state[key.strip()] = value.strip()
        except (OSError, UnicodeError):
            pass

        # Animated atmospheric glow.
        halo = QRadialGradient(190, 85, 190)
        if state == "thinking":
            halo.setColorAt(0.0, QColor(130, 65, 255, 48 + int(pulse * 55)))
            halo.setColorAt(0.48, QColor(20, 100, 255, 22 + int(pulse * 25)))
        elif state == "speaking":
            halo.setColorAt(0.0, QColor(0, 225, 255, 45 + int(pulse * 65)))
            halo.setColorAt(0.48, QColor(100, 60, 255, 20 + int(pulse * 30)))
        else:
            halo.setColorAt(0.0, QColor(20, 150, 225, 25 + int(pulse * 38)))
            halo.setColorAt(0.48, QColor(75, 40, 180, 12 + int(pulse * 20)))
        halo.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(halo)
        painter.drawEllipse(5, 3, 380, 164)

        # Smoked-glass capsule.
        pill = QPainterPath()
        pill.addRoundedRect(22, 43, 346, 84, 42, 42)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(3, 7, 16, 242))
        painter.drawPath(pill)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(100, 205, 255, 75 + int(pulse * 75)), 1.25))
        painter.drawPath(pill)

        inner = QPainterPath()
        inner.addRoundedRect(25, 46, 340, 78, 39, 39)
        painter.setPen(QPen(QColor(255, 255, 255, 18), 0.8))
        painter.drawPath(inner)

        reflection = QPainterPath()
        reflection.moveTo(65, 46)
        reflection.cubicTo(120, 42, 270, 42, 325, 46)
        painter.setPen(QPen(QColor(225, 245, 255, 48), 1.0))
        painter.drawPath(reflection)

        # Rotating 3D-style torus ring. No infinity ribbon.
        cx, cy = 82.0, 84.0
        major, minor = 21.0, 6.0
        rx = t * speed * 0.55
        ry = t * speed * 0.72
        rz = t * speed * 0.34
        us, vs = 72, 8
        faces = []

        def ring_point(u, v):
            rr = major + minor * math.cos(v)
            x = rr * math.cos(u)
            y = rr * math.sin(u)
            z = minor * math.sin(v)

            y, z = y * math.cos(rx) - z * math.sin(rx), y * math.sin(rx) + z * math.cos(rx)
            x, z = x * math.cos(ry) + z * math.sin(ry), -x * math.sin(ry) + z * math.cos(ry)
            x, y = x * math.cos(rz) - y * math.sin(rz), x * math.sin(rz) + y * math.cos(rz)

            perspective = 150.0 / max(95.0, 150.0 - z)
            return cx + x * perspective, cy + y * perspective, z

        for i in range(us):
            u0 = 2 * math.pi * i / us
            u1 = 2 * math.pi * (i + 1) / us
            for j in range(vs):
                v0 = 2 * math.pi * j / vs
                v1 = 2 * math.pi * (j + 1) / vs
                pts = [
                    ring_point(u0, v0), ring_point(u1, v0),
                    ring_point(u1, v1), ring_point(u0, v1)
                ]
                depth = sum(p[2] for p in pts) / 4
                hue = (math.sin(u0 - t * speed * 0.8) + 1) / 2
                light = max(0.0, min(1.0, 0.5 + depth / 18.0))
                color = QColor(
                    int(35 + 35 * hue),
                    int(130 + 110 * hue),
                    255,
                    int(150 + 100 * light)
                )
                faces.append((depth, pts, color))

        painter.setPen(Qt.PenStyle.NoPen)
        for depth, pts, color in sorted(faces, key=lambda item: item[0]):
            path = QPainterPath()
            path.moveTo(pts[0][0], pts[0][1])
            for px, py, _ in pts[1:]:
                path.lineTo(px, py)
            path.closeSubpath()
            painter.setBrush(color)
            painter.drawPath(path)

        # Fast-moving luminous tracer around the ring.
        tracer = ring_point((t * speed * 1.7) % (2 * math.pi), 0.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(160, 255, 255, 225))
        painter.drawEllipse(tracer[0] - 2.2, tracer[1] - 2.2, 4.4, 4.4)

        # Brand label and current activity.
        painter.setPen(QColor(225, 237, 250, 230))
        font = painter.font()
        font.setFamily("Segoe UI")
        font.setPixelSize(9)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(58, 116, "N O V A")

        labels = {
            "idle": "READY",
            "listening": "LISTENING",
            "thinking": "THINKING",
            "speaking": "SPEAKING"
        }
        painter.setPen(QColor(115, 225, 255, 220 if state != "idle" else 150))
        font.setPixelSize(7)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(137, 88, labels[state])

        # Original control capsule and click coordinates remain unchanged.
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

        # Home icon: x=248..271.
        home = QPainterPath()
        home.moveTo(252, 82)
        home.lineTo(260, 75)
        home.lineTo(268, 82)
        home.moveTo(255, 81)
        home.lineTo(255, 91)
        home.lineTo(265, 91)
        home.lineTo(265, 81)
        painter.setPen(QPen(QColor(240, 248, 255, 240), 1.6,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawPath(home)
        painter.drawLine(259, 91, 259, 85)

        # Speaker icon: x=273..301. Slash means muted.
        speaker = QPainterPath()
        speaker.moveTo(275, 82)
        speaker.lineTo(279, 82)
        speaker.lineTo(285, 77)
        speaker.lineTo(285, 92)
        speaker.lineTo(279, 87)
        speaker.lineTo(275, 87)
        speaker.closeSubpath()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(230, 245, 255, 245))
        painter.drawPath(speaker)
        if ui_state["audio"] == "on":
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(QPen(QColor(230, 245, 255, 240), 1.4,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawArc(281, 77, 13, 15, -55 * 16, 110 * 16)
            painter.drawArc(281, 73, 19, 23, -55 * 16, 110 * 16)
        else:
            painter.setPen(QPen(QColor(255, 100, 130, 255), 2.0,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(275, 74, 297, 96)

        # Microphone icon: x=305..329. Slash means microphone disabled.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(240, 248, 255, 245), 1.6,
                            Qt.PenStyle.SolidLine,
                            Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.drawRoundedRect(312, 74, 9, 16, 4, 4)
        painter.drawArc(308, 78, 17, 18, 180 * 16, 180 * 16)
        painter.drawLine(316, 96, 316, 99)
        painter.drawLine(311, 99, 321, 99)
        if ui_state["mic"] == "off":
            painter.setPen(QPen(QColor(255, 100, 130, 255), 2.0,
                                Qt.PenStyle.SolidLine,
                                Qt.PenCapStyle.RoundCap))
            painter.drawLine(307, 73, 328, 97)

        # Activity-specific accent.
        if state != "idle":
            accent = {
                "listening": QColor(35, 220, 255, 75 + int(pulse * 100)),
                "thinking": QColor(155, 95, 255, 75 + int(pulse * 100)),
                "speaking": QColor(80, 225, 255, 75 + int(pulse * 110))
            }[state]
            painter.setPen(QPen(accent, 1.35))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(245, 66, 94, 38, 19, 19)

        painter.end()

'''
    widget = widget[:method_start] + new_glass + widget[next_method:]

    # Write mic/audio status from the existing backend.
    helper = r'''    def write_ui_state(self):
        try:
            data = "\n".join((
                f"mic={'on' if self.listening else 'off'}",
                f"audio={'on' if self.audio_enabled else 'off'}",
                ""
            ))
            (BASE_DIR / "nova_ui_state.txt").write_text(data, encoding="utf-8")
        except OSError as error:
            print("UI state warning:", error)

'''
    if "    def write_ui_state(self):" not in main:
        anchor = "    def set_status(self, status):"
        if main.count(anchor) != 1:
            raise RuntimeError("Could not locate set_status exactly once")
        main = main.replace(anchor, helper + anchor, 1)

    # Ensure initial state is reflected in the UI file.
    if "self.write_ui_state()" not in main:
        init_anchor = '        self.status = "idle"'
        if main.count(init_anchor) != 1:
            raise RuntimeError("Could not locate initial idle status exactly once")
        main = main.replace(
            init_anchor,
            init_anchor + "\n        self.write_ui_state()",
            1
        )

    # Update the UI state after each existing control toggle.
    main = replace_once(
        main,
        '''                    self.set_status("listening" if self.listening else "idle")
''',
        '''                    self.set_status("listening" if self.listening else "idle")
                    self.write_ui_state()
''',
        "Microphone toggle state"
    )
    main = replace_once(
        main,
        '''                    print("Voice output:", "ON" if self.audio_enabled else "MUTED")
''',
        '''                    print("Voice output:", "ON" if self.audio_enabled else "MUTED")
                    self.write_ui_state()
''',
        "Audio toggle state"
    )

    # Write both updated files and compile before accepting the patch.
    WIDGET.write_text(widget, encoding="utf-8")
    MAIN.write_text(main, encoding="utf-8")

    py_compile.compile(str(WIDGET), doraise=True)
    py_compile.compile(str(MAIN), doraise=True)

    STATE.write_text("mic=on\naudio=on\n", encoding="utf-8")
    print("PATCH SUCCESSFUL")
    print("Both Python files compiled successfully.")
    print("Backups:", BACKUPS[WIDGET].name, "and", BACKUPS[MAIN].name)
    print("Restart Nova to test the redesign.")

except Exception as error:
    WIDGET.write_text(original_widget, encoding="utf-8")
    MAIN.write_text(original_main, encoding="utf-8")
    print("PATCH FAILED:", error)
    print("Original source files restored.")
    sys.exit(1)
