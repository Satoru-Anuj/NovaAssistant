import sys
from pathlib import Path
import math
import ctypes
import time

from PySide6.QtCore import Qt, QTimer, Signal, QAbstractNativeEventFilter
from PySide6.QtGui import (
    QGuiApplication, QIcon, QPainter, QPixmap, QColor,
    QPen, QBrush, QSurfaceFormat, QVector2D, QAction, QPainter, QPainterPath, QRadialGradient
)
from PySide6.QtWidgets import (
    QApplication, QSystemTrayIcon,
    QMenu, QWidget
)
from PySide6.QtOpenGL import QOpenGLShader, QOpenGLShaderProgram
from PySide6.QtOpenGL import QOpenGLVertexArrayObject
from PySide6.QtOpenGLWidgets import QOpenGLWidget

from OpenGL.GL import (
    glClearColor, glClear, glEnable, glBlendFunc, glDrawArrays,
    GL_COLOR_BUFFER_BIT, GL_BLEND, GL_SRC_ALPHA,
    GL_ONE_MINUS_SRC_ALPHA, GL_TRIANGLE_STRIP
)


VERTEX_SHADER = r"""
#version 330 core

out vec2 v_uv;

void main()
{
    vec2 positions[4] = vec2[4](
        vec2(-1.0, -1.0),
        vec2( 1.0, -1.0),
        vec2(-1.0,  1.0),
        vec2( 1.0,  1.0)
    );

    vec2 p = positions[gl_VertexID];
    v_uv = p * 0.5 + 0.5;
    gl_Position = vec4(p, 0.0, 1.0);
}
"""


FRAGMENT_SHADER = r"""
#version 330 core

in vec2 v_uv;
out vec4 fragColor;

uniform vec2 u_resolution;
uniform float u_time;
uniform float u_dpr;

const float PI = 3.14159265359;

float roundedBox(vec2 p, vec2 halfStraight, float radius)
{
    return length(max(abs(p) - halfStraight, 0.0)) - radius;
}

float segmentDistance(vec2 p, vec2 a, vec2 b)
{
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / max(dot(ba, ba), 0.0001), 0.0, 1.0);
    return length(pa - ba * h);
}

vec3 ribbonPoint(float t, float tm)
{
    float z = cos(t + tm);
    float x = 31.0 * sin(t) * (1.0 + 0.13 * cos(t + tm));
    float y = 17.0 * sin(2.0 * t) + 2.5 * z;
    return vec3(x, y, z);
}

vec3 ribbonColour(float t)
{
    float f = fract(t / (2.0 * PI) + 0.08);
    vec3 cyan = vec3(0.0, 0.90, 1.0);
    vec3 pink = vec3(0.84, 0.0, 0.98);
    vec3 violet = vec3(0.49, 0.25, 1.0);

    if (f < 0.48)
        return mix(cyan, pink, smoothstep(0.0, 0.48, f));

    return mix(pink, violet, smoothstep(0.48, 1.0, f));
}

vec4 ribbonLayer(vec2 p, float tm)
{
    float best = 10000.0;
    float bestT = 0.0;
    float bestZ = 0.0;

    const int N = 112;

    vec3 previous = ribbonPoint(0.0, tm);

    for (int i = 1; i <= N; i++)
    {
        float t = 2.0 * PI * float(i) / float(N);
        vec3 current = ribbonPoint(t, tm);

        float d = segmentDistance(p, previous.xy, current.xy);

        if (d < best)
        {
            best = d;
            bestT = t - (2.0 * PI / float(N)) * 0.5;
            bestZ = (previous.z + current.z) * 0.5;
        }

        previous = current;
    }

    float width = 2.2 + 0.8 * (bestZ * 0.5 + 0.5);
    vec3 col = ribbonColour(bestT);

    float glow = exp(-best * 0.19) * 0.42;
    float body = 1.0 - smoothstep(width - 0.5, width + 0.6, best);
    float ridge = exp(-pow((best - width * 0.38) * 1.5, 2.0)) * 0.55;

    float lighting = 0.68 + 0.32 * (bestZ * 0.5 + 0.5);
    col *= lighting;

    vec3 result = col * (glow + body * 0.80 + ridge);
    float alpha = clamp(glow + body * 0.94 + ridge * 0.45, 0.0, 1.0);

    return vec4(result, alpha);
}

float lineMask(vec2 p, vec2 a, vec2 b, float thickness)
{
    float d = segmentDistance(p, a, b);
    return 1.0 - smoothstep(thickness, thickness + 0.8, d);
}

void main()
{
    // Work in logical pixels so the design survives Windows display scaling.
    vec2 frag = gl_FragCoord.xy / u_dpr;
    vec2 uv = vec2(frag.x, u_resolution.y - frag.y);

    vec2 pillP = uv - vec2(195.0, 85.0);
    float outerD = roundedBox(pillP, vec2(76.0, 0.0), 34.0);

    // Soft shadow outside the capsule.
    float shadow = exp(-max(outerD, 0.0) * 0.20) * 0.22;
    float body = 1.0 - smoothstep(-0.7, 0.9, outerD);

    vec3 colour = vec3(0.0);
    float alpha = max(shadow, body);

    // A subtle top-edge reflection.
    float topHighlight = lineMask(uv, vec2(120.0, 51.7),
                                  vec2(268.0, 51.7), 0.45);
    colour += vec3(0.10, 0.10, 0.12) * topHighlight * body;

    // Animated infinity loop with perspective-like depth shading.
    vec2 ribbonP = uv - vec2(130.0, 85.0);
    vec4 ribbon = ribbonLayer(ribbonP, u_time * 0.72);

    // Keep the ribbon inside the main pill.
    float ribbonClip = 1.0 - smoothstep(32.0, 34.0, length(ribbonP));
    ribbon.a *= ribbonClip * body;
    colour = mix(colour, ribbon.rgb, ribbon.a);

    // The inset control capsule.
    vec2 insetP = uv - vec2(237.5, 84.0);
    float insetD = roundedBox(insetP, vec2(29.5, 0.0), 23.0);
    float inset = 1.0 - smoothstep(-0.5, 0.8, insetD);

    vec3 insetColour = vec3(0.055, 0.055, 0.067);

    float insetTop = lineMask(uv, vec2(205.0, 62.5),
                              vec2(270.0, 62.5), 0.45);
    insetColour += vec3(0.18) * insetTop;

    colour = mix(colour, insetColour, inset);

    // Symmetrical audio waveform.
    float wave = 0.0;
    wave += lineMask(uv, vec2(204.0, 80.0), vec2(204.0, 88.0), 0.85);
    wave += lineMask(uv, vec2(215.0, 76.5), vec2(215.0, 91.5), 0.85);
    wave += lineMask(uv, vec2(244.0, 76.5), vec2(244.0, 91.5), 0.85);
    wave += lineMask(uv, vec2(255.0, 80.0), vec2(255.0, 88.0), 0.85);

    float pulse = 0.88 + 0.12 * sin(u_time * 5.0);
    wave *= pulse;

    // Centre dot.
    float dot = 1.0 - smoothstep(1.2, 2.0,
                                length(uv - vec2(230.0, 84.0)));
    wave = max(wave, dot);

    // Minimalist microphone body, curved cradle and stand.
    float micBody = 1.0 - smoothstep(
        0.6, 1.3,
        roundedBox(uv - vec2(272.0, 79.0), vec2(0.0, 3.0), 3.0)
    );

    float mic = micBody;
    mic = max(mic, lineMask(uv, vec2(265.8, 80.0),
                            vec2(265.8, 84.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(265.8, 84.0),
                            vec2(268.0, 89.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(268.0, 89.0),
                            vec2(272.0, 91.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(272.0, 91.0),
                            vec2(276.0, 89.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(276.0, 89.0),
                            vec2(278.2, 84.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(278.2, 84.0),
                            vec2(278.2, 80.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(272.0, 91.0),
                            vec2(272.0, 94.0), 0.65));
    mic = max(mic, lineMask(uv, vec2(268.0, 94.0),
                            vec2(276.0, 94.0), 0.65));

    float icons = max(wave, mic) * inset;

    colour = mix(colour, vec3(1.0), clamp(icons, 0.0, 1.0));

    // Alpha is transparent outside the pill and its soft shadow.
    fragColor = vec4(colour, clamp(alpha, 0.0, 1.0));
}
"""


class NovaWidget(QWidget):
    microphoneClicked = Signal()
    audioToggleRequested = Signal()

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Nova Widget")
        self.setWindowFlags(
            Qt.WindowType.Tool
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)

        self.setFixedSize(104, 104)
        self.setMouseTracking(True)

        self.program = None
        self.started = time.perf_counter()
        self.ui_mode = "idle"
        self.status_file = Path(__file__).with_name("nova_status.txt")


        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(16)

        screen = QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(
                area.center().x() - self.width() // 2,
                area.center().y() - self.height() // 2
            )

    def paintEvent(self, event):
        if self.ui_mode == "glass":
            self._paint_glass_bar(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        t = time.perf_counter() - self.started
        status = "idle"
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

        if active:
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

    def _draw_matching_ring(self, painter, t, cx, cy, size, state="idle"):
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
        radius = min(w, h) * (0.245 if active else 0.205)
        width = min(w, h) * (0.105 if active else 0.075)
        stretch = 1 + (0.20 * pulse if active else 0.035 * pulse)

        ax, ay, az = (t * 0.78 * motion, t * 0.93 * motion, t * 0.58 * motion)
        sx, cxr = math.sin(ax), math.cos(ax)
        sy, cyr = math.sin(ay), math.cos(ay)
        sz, czr = math.sin(az), math.cos(az)

        def project(u, v):
            wave = math.sin(u * 3 - t * 2 * motion) * (0.035 if active else 0.012)
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

        if active:
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
                    i / us + t * motion * (0.055 if active else 0.022)
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



    def _paint_active_plasma(self, t, state):
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



    def enterEvent(self, event):
        # Hover must never change the selected UI state.
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Keep the current UI state until the user clicks.
        super().leaveEvent(event)

    def _paint_glass_bar(self, event):
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

        # Same 3D ring geometry as the original idle animation.
        self._draw_matching_ring(
            painter, t, 82.0, 84.0, 104.0, state
        )

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

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.position()
            x, y = p.x(), p.y()

            if self.ui_mode == "glass":
                # Preserve the existing control hit areas.
                if 248 <= x <= 271 and 68 <= y <= 103:
                    self.ui_mode = "idle"
                    old_x, old_y = self.x(), self.y()
                    self.setFixedSize(104, 104)
                    self.move(
                        old_x + (390 - 104) // 2,
                        old_y + (170 - 104) // 2
                    )
                    self.update()
                elif 273 <= x <= 301 and 68 <= y <= 103:
                    self.audioToggleRequested.emit()
                elif 305 <= x <= 329 and 68 <= y <= 103:
                    self.microphoneClicked.emit()
                else:
                    self.ui_mode = "idle"
                    old_x, old_y = self.x(), self.y()
                    self.setFixedSize(104, 104)
                    self.move(
                        old_x + (390 - 104) // 2,
                        old_y + (170 - 104) // 2
                    )
                    self.update()
            else:
                old_x, old_y = self.x(), self.y()
                self.ui_mode = "glass"
                self.setFixedSize(390, 170)
                self.move(
                    old_x - (390 - 104) // 2,
                    old_y - (170 - 104) // 2
                )
                self.update()

        super().mouseReleaseEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton:
            offset = getattr(self, "_drag_offset", None)
            if offset is not None:
                self.move(event.globalPosition().toPoint() - offset)
        super().mouseMoveEvent(event)

    def toggle_visibility(self):
        if self.isVisible():
            self.hide()
        else:
            self.show()
            self.raise_()


class WinPoint(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long),
    ]


class WinMSG(ctypes.Structure):
    _fields_ = [
        ("hwnd", ctypes.c_void_p),
        ("message", ctypes.c_uint),
        ("wParam", ctypes.c_size_t),
        ("lParam", ctypes.c_ssize_t),
        ("time", ctypes.c_uint),
        ("pt", WinPoint),
    ]


class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, widget):
        super().__init__()
        self.widget = widget

    def nativeEventFilter(self, eventType, message):
        try:
            msg = ctypes.cast(
                int(message), ctypes.POINTER(WinMSG)
            ).contents

            if msg.message == 0x0312 and msg.wParam == 1:
                self.widget.toggle_visibility()
                return True, 0
        except (TypeError, ValueError, OSError):
            pass

        return False, 0


def make_tray_icon():
    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    painter.setPen(QPen(QColor("#00E5FF"), 4))
    painter.drawArc(9, 15, 46, 32, 30 * 16, 300 * 16)

    painter.setPen(QPen(QColor("#D500F9"), 4))
    painter.drawArc(9, 15, 46, 32, 210 * 16, 300 * 16)

    painter.end()
    return QIcon(pixmap)


def main():
    fmt = QSurfaceFormat()
    fmt.setRenderableType(QSurfaceFormat.RenderableType.OpenGL)
    fmt.setVersion(3, 3)
    fmt.setProfile(QSurfaceFormat.OpenGLContextProfile.CoreProfile)
    fmt.setAlphaBufferSize(8)
    fmt.setDepthBufferSize(0)
    fmt.setStencilBufferSize(0)
    fmt.setSwapBehavior(QSurfaceFormat.SwapBehavior.DoubleBuffer)
    QSurfaceFormat.setDefaultFormat(fmt)

    app = QApplication(sys.argv)
    app.setApplicationName("Nova Widget")
    app.setQuitOnLastWindowClosed(False)

    widget = NovaWidget()

    from pathlib import Path
    import subprocess

    assistant_process = [None]

    def launch_assistant():
        process = assistant_process[0]
        if process is None or process.poll() is not None:
            assistant_file = Path(__file__).with_name('main.py')
            assistant_process[0] = subprocess.Popen(
                [sys.executable, str(assistant_file), '--background'],
                cwd=str(assistant_file.parent)
            )

    def send_control(command):
        process = assistant_process[0]
        if process is None or process.poll() is not None:
            launch_assistant()
        control_file = Path(__file__).with_name("nova_ui_control.txt")
        control_file.write_text(command, encoding="utf-8")

    widget.microphoneClicked.connect(lambda: send_control("mic_toggle"))
    widget.audioToggleRequested.connect(lambda: send_control("audio_toggle"))

    launch_assistant()

    tray = QSystemTrayIcon(make_tray_icon(), app)
    tray.setToolTip("Nova Ã¢â‚¬â€ Floating Assistant")

    menu = QMenu()
    show_action = QAction("Show / Hide Nova", menu)
    show_action.triggered.connect(widget.toggle_visibility)
    menu.addAction(show_action)

    menu.addSeparator()
    quit_action = QAction("Exit Nova Widget", menu)
    quit_action.triggered.connect(app.quit)
    menu.addAction(quit_action)

    tray.setContextMenu(menu)
    tray.activated.connect(
        lambda reason: widget.toggle_visibility()
        if reason == QSystemTrayIcon.ActivationReason.Trigger else None
    )

    if QSystemTrayIcon.isSystemTrayAvailable():
        tray.show()
    else:
        print("Windows system tray is unavailable right now.")

    hotkey_filter = None
    hotkey_registered = False

    if sys.platform == "win32":
        # Alt + Space. Windows may reject this if another program owns it.
        user32 = ctypes.windll.user32
        hotkey_registered = bool(user32.RegisterHotKey(None, 1, 0x0001, 0x20))

        if hotkey_registered:
            hotkey_filter = NativeHotkeyFilter(widget)
            app.installNativeEventFilter(hotkey_filter)
            print("Global shortcut registered: Alt + Space")
        else:
            print("Alt + Space could not be registered; use the tray menu.")

    widget.show()

    def cleanup():
        process = assistant_process[0]
        if process is not None and process.poll() is None:
            process.terminate()
        if sys.platform == "win32" and hotkey_registered:
            ctypes.windll.user32.UnregisterHotKey(None, 1)
        tray.hide()

    app.aboutToQuit.connect(cleanup)

    print("Nova Widget running. Right-click the tray icon to exit.")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()








