from pathlib import Path
import ast
import shutil

ROOT = Path(__file__).resolve().parent
WIDGET = ROOT / 'nova_widget.py'
MAIN = ROOT / 'main.py'

if not WIDGET.exists() or not MAIN.exists():
    raise SystemExit('Put nova_ui_upgrade.py inside your NovaAssistant folder beside nova_widget.py and main.py, then run it again.')

widget_src = WIDGET.read_text(encoding='utf-8-sig')
main_src = MAIN.read_text(encoding='utf-8-sig')
if 'import sys\n' not in main_src:
    main_src = main_src.replace('import os\n', 'import os\nimport sys\n', 1)
ast.parse(widget_src)
ast.parse(main_src)
if 'class NovaOrb:' not in main_src or '    def listen_loop(self):' not in main_src or '    def handle_command(self, command):' not in main_src:
    raise SystemExit('main.py does not match the expected NovaOrb structure. No changes made.')

# Back up both originals before changing either one.
for path in (WIDGET, MAIN):
    backup = path.with_name(path.stem + '_before_ui_upgrade' + path.suffix)
    if not backup.exists():
        shutil.copy2(path, backup)

# Patch the assistant to publish conversation/status data and accept UI controls.
if 'def _nova_publish_ui_state(self):' not in main_src:
    anchor = '    def extract_wake_command(self, spoken):'
    insert = '''    def _nova_publish_ui_state(self):
        try:
            state = {
                "status": getattr(self, "status", "idle"),
                "user": getattr(self, "ui_last_user", ""),
                "reply": getattr(self, "ui_last_reply", ""),
                "muted": bool(getattr(self, "ui_muted", False)),
                "mic_enabled": bool(getattr(self, "listening", True)),
            }
            target = BASE_DIR / "nova_ui_state.json"
            temp = BASE_DIR / "nova_ui_state.tmp"
            temp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
            temp.replace(target)
        except (OSError, TypeError, ValueError):
            pass

    def poll_ui_control(self):
        if self.closing:
            return
        control = BASE_DIR / "nova_ui_control.txt"
        try:
            command = control.read_text(encoding="utf-8").strip()
            if command:
                control.write_text("", encoding="utf-8")
                if command == "mic_toggle":
                    self.listening = not self.listening
                    self._nova_publish_ui_state()
                    if self.listening:
                        threading.Thread(target=self.listen_loop, daemon=True).start()
                elif command == "mute_toggle":
                    self.ui_muted = not bool(getattr(self, "ui_muted", False))
                    self._nova_publish_ui_state()
        except OSError:
            pass
        self.root.after(180, self.poll_ui_control)

'''
    if anchor not in main_src:
        raise SystemExit('Could not find load_memory method. No changes made.')
    main_src = main_src.replace(anchor, insert + anchor, 1)

startup = '        threading.Thread(target=self.listen_loop, daemon=True).start()'
if 'self.root.after(180, self.poll_ui_control)' not in main_src:
    if startup not in main_src:
        raise SystemExit('Could not find listener startup. No changes made.')
    main_src = main_src.replace(
        startup,
        '        self.ui_last_user = ""\n'
        '        self.ui_last_reply = ""\n'
        '        self.ui_muted = False\n'
        '        self._nova_publish_ui_state()\n'
        + startup + '\n'
        '        self.root.after(180, self.poll_ui_control)', 1
    )

old_status = '''    def set_status(self, status):
        if not self.closing:
            self.status = status
'''
new_status = '''    def set_status(self, status):
        if not self.closing:
            self.status = status
            self._nova_publish_ui_state()
'''
if old_status in main_src:
    main_src = main_src.replace(old_status, new_status, 1)

if '        self.ui_last_user = command' not in main_src:
    marker = '        print("You:", command)'
    if marker not in main_src:
        raise SystemExit('Could not find user-command marker. No changes made.')
    main_src = main_src.replace(marker, marker + '\n        self.ui_last_user = command\n        self._nova_publish_ui_state()', 1)

if '        self.ui_last_reply = reply' not in main_src:
    marker = '        print("Nova:", reply)'
    if marker not in main_src:
        raise SystemExit('Could not find reply marker. No changes made.')
    main_src = main_src.replace(marker, '        self.ui_last_reply = reply\n        self._nova_publish_ui_state()\n' + marker, 1)

if 'if getattr(self, "ui_muted", False):' not in main_src:
    marker = '            engine = pyttsx3.init()'
    if marker not in main_src:
        raise SystemExit('Could not find TTS marker. No changes made.')
    main_src = main_src.replace(marker, '            if getattr(self, "ui_muted", False):\n                return\n' + marker, 1)

# Hide the old Tk window when launched by the new UI.
if 'if "--background" in sys.argv:' not in main_src:
    old_guard = 'if __name__ == "__main__":\n    app = NovaOrb()\n    app.root.mainloop()'
    new_guard = 'if __name__ == "__main__":\n    app = NovaOrb()\n    if "--background" in sys.argv:\n        app.root.withdraw()\n    app.root.mainloop()'
    if old_guard not in main_src:
        raise SystemExit('Could not find main startup block. No changes made.')
    main_src = main_src.replace(old_guard, new_guard, 1)

# New PySide6 interface: animated compact pill, hover dock, state colors, controls.
widget_code = r'''import sys
import math
import json
import time
import ctypes
import subprocess
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QAbstractNativeEventFilter
from PySide6.QtGui import QGuiApplication, QIcon, QPainter, QPixmap, QColor, QPen, QAction, QPainterPath, QRadialGradient, QFont
from PySide6.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QWidget

BASE_DIR = Path(__file__).resolve().parent
STATE_FILE = BASE_DIR / 'nova_ui_state.json'
CONTROL_FILE = BASE_DIR / 'nova_ui_control.txt'

class NovaWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Nova')
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.expanded = False
        self.status = 'idle'
        self.last_user = ''
        self.last_reply = ''
        self.muted = False
        self.mic_enabled = True
        self.started = time.perf_counter()
        self.drag_offset = None
        self.setFixedSize(390, 150)
        screen = QGuiApplication.primaryScreen()
        if screen:
            area = screen.availableGeometry()
            self.move(area.center().x() - self.width() // 2, area.bottom() - 190)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.tick)
        self.timer.start(33)

    def tick(self):
        try:
            data = json.loads(STATE_FILE.read_text(encoding='utf-8'))
            self.status = data.get('status', self.status)
            self.last_user = data.get('user', self.last_user)
            self.last_reply = data.get('reply', self.last_reply)
            self.muted = bool(data.get('muted', self.muted))
            self.mic_enabled = bool(data.get('mic_enabled', self.mic_enabled))
        except (OSError, ValueError, TypeError):
            pass
        self.update()

    def send_control(self, command):
        try:
            CONTROL_FILE.write_text(command, encoding='utf-8')
        except OSError:
            pass

    def set_expanded(self, value):
        if self.expanded == value:
            return
        self.expanded = value
        g = self.geometry()
        if value:
            self.setFixedSize(560, 330)
            self.setGeometry(g.x() - 85, g.y() - 180, 560, 330)
        else:
            self.setFixedSize(390, 150)
            self.setGeometry(g.x() + 85, g.y() + 180, 390, 150)
        self.update()

    def enterEvent(self, event):
        self.set_expanded(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.set_expanded(False)
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            self.close()
        elif event.button() == Qt.MouseButton.LeftButton:
            self.drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if event.buttons() & Qt.MouseButton.LeftButton and self.drag_offset is not None:
            self.move(event.globalPosition().toPoint() - self.drag_offset)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.position()
            if self.expanded:
                if 30 <= p.x() <= 150 and 246 <= p.y() <= 292:
                    self.send_control('mic_toggle')
                elif 165 <= p.x() <= 285 and 246 <= p.y() <= 292:
                    self.send_control('mute_toggle')
                elif 300 <= p.x() <= 420 and 246 <= p.y() <= 292:
                    self.set_expanded(False)
            else:
                if 300 <= p.x() <= 345 and 48 <= p.y() <= 105:
                    self.send_control('mic_toggle')
                elif 200 <= p.x() <= 295 and 45 <= p.y() <= 112:
                    self.set_expanded(True)
        super().mouseReleaseEvent(event)

    def palette(self):
        return {
            'idle': ('#00D9FF', '#287BFF', '#9A5BFF'),
            'listening': ('#38F5C7', '#00C9FF', '#42A5FF'),
            'thinking': ('#B65CFF', '#6C70FF', '#00D6FF'),
            'speaking': ('#FF54D8', '#A45BFF', '#00D9FF'),
        }.get(self.status, ('#00D9FF', '#287BFF', '#9A5BFF'))

    def draw_orb(self, p, cx, cy, scale=1.0):
        cols = self.palette()
        t = time.perf_counter() - self.started
        speed = {'idle': .65, 'listening': 2.2, 'thinking': 2.8, 'speaking': 2.0}.get(self.status, .7)
        phase = t * speed
        pulse = math.sin(phase * 1.8)
        r = (20 + pulse * (2 if self.status == 'idle' else 4)) * scale
        grad = QRadialGradient(cx, cy, 50 * scale)
        grad.setColorAt(0, QColor(cols[0]))
        grad.setColorAt(.35, QColor(cols[1]))
        grad.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(grad)
        p.drawEllipse(int(cx-50*scale), int(cy-50*scale), int(100*scale), int(100*scale))
        p.setBrush(QColor('#08162B'))
        p.setPen(QPen(QColor(cols[0]), 1.5))
        p.drawEllipse(int(cx-r), int(cy-r), int(2*r), int(2*r))
        for i in range(3):
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.setPen(QPen(QColor(cols[i]), 1.3))
            rr = (r + 6 + i*3) * scale
            p.drawArc(int(cx-rr), int(cy-rr*.65), int(2*rr), int(1.3*rr), int((phase*40+i*110)%360*16), 245*16)
        path = QPainterPath()
        path.moveTo(cx-12*scale, cy)
        path.cubicTo(cx-24*scale, cy-15*scale, cx-29*scale, cy+12*scale, cx-14*scale, cy+8*scale)
        path.cubicTo(cx-6*scale, cy+5*scale, cx+6*scale, cy-8*scale, cx+14*scale, cy-8*scale)
        path.cubicTo(cx+29*scale, cy-12*scale, cx+24*scale, cy+15*scale, cx+12*scale, cy)
        path.cubicTo(cx+4*scale, cy-7*scale, cx-4*scale, cy+7*scale, cx-12*scale, cy)
        p.setPen(QPen(QColor('#E7FFFF'), 2.4*scale, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)

    def draw_wave(self, p, x, y, width, height):
        t = time.perf_counter() - self.started
        path = QPainterPath()
        for i in range(81):
            xx = x + width*i/80
            env = math.sin(math.pi*i/80)**.5
            amp = height*(.30 if self.status == 'idle' else .5)
            yy = y + math.sin(i*.24-t*4.5)*amp*env + math.sin(i*.11+t*2.1)*amp*.4*env
            if i == 0: path.moveTo(xx, yy)
            else: path.lineTo(xx, yy)
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.setPen(QPen(QColor(self.palette()[0]), 1.6))
        p.drawPath(path)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        w, h = self.width(), self.height()
        cols = self.palette()
        if self.expanded:
            panel = QPainterPath()
            panel.addRoundedRect(10, 10, w-20, h-20, 25, 25)
            p.fillPath(panel, QColor(5, 12, 28, 245))
            p.setPen(QPen(QColor(cols[0]), 1.2))
            p.drawPath(panel)
            self.draw_orb(p, 72, 70, .85)
            p.setPen(QColor('#E5FAFF')); p.setFont(QFont('Segoe UI', 15, QFont.Weight.Bold)); p.drawText(130, 43, 'N O V A')
            p.setPen(QColor(cols[0])); p.setFont(QFont('Consolas', 9, QFont.Weight.Bold)); p.drawText(130, 63, self.status.upper() + (' / MUTED' if self.muted else ''))
            p.setPen(QColor('#244257')); p.drawLine(28, 122, w-28, 122)
            p.setPen(QColor('#7E9DB6')); p.setFont(QFont('Segoe UI', 9)); p.drawText(30, 145, 'YOU')
            p.setPen(QColor('#CDEEFF')); p.drawText(30, 165, (self.last_user or 'Say â€œNovaâ€ followed by your command.')[:90])
            p.setPen(QColor('#7E9DB6')); p.drawText(30, 194, 'NOVA')
            p.setPen(QColor('#EAF6FF'))
            reply = self.last_reply or ('Thinkingâ€¦' if self.status == 'thinking' else 'Nova is ready when you are.')
            p.drawText(30, 216, reply[:185])
            p.setPen(QPen(QColor('#163A50'), 1)); p.setBrush(QColor('#0A1C30'))
            p.drawRoundedRect(30, 246, 120, 42, 14, 14); p.drawRoundedRect(165, 246, 120, 42, 14, 14); p.drawRoundedRect(300, 246, 120, 42, 14, 14)
            p.setPen(QColor(cols[0])); p.setFont(QFont('Segoe UI', 9, QFont.Weight.DemiBold))
            p.drawText(48, 272, 'MIC: ' + ('ON' if self.mic_enabled else 'OFF'))
            p.drawText(183, 272, 'SOUND: ' + ('OFF' if self.muted else 'ON'))
            p.setPen(QColor('#A9C4D6')); p.drawText(318, 272, 'MINIMIZE')
            self.draw_wave(p, 315, 87, 210, 14)
        else:
            pill = QPainterPath(); pill.addRoundedRect(28, 28, 334, 92, 46, 46)
            p.fillPath(pill, QColor(5, 14, 32, 244)); p.setPen(QPen(QColor(cols[0]), 1.5)); p.drawPath(pill)
            self.draw_orb(p, 73, 74, .82); self.draw_wave(p, 112, 75, 90, 14)
            p.setPen(QColor('#E5FAFF')); p.setFont(QFont('Segoe UI', 11, QFont.Weight.Bold)); p.drawText(116, 55, 'N O V A')
            p.setPen(QColor(cols[0])); p.setFont(QFont('Consolas', 8, QFont.Weight.Bold)); p.drawText(116, 96, self.status.upper())
            p.setPen(QPen(QColor('#24475C'), 1)); p.setBrush(QColor('#0B1B2C')); p.drawRoundedRect(240, 48, 104, 52, 25, 25)
            p.setPen(QPen(QColor('#E6FAFF'), 1.7)); p.drawRoundedRect(314, 61, 8, 16, 4, 4); p.drawArc(308, 65, 20, 20, 180*16, 180*16); p.drawLine(318, 85, 318, 90); p.drawLine(312, 90, 324, 90)
            p.setPen(QColor('#86A9C2')); p.setFont(QFont('Segoe UI', 7)); p.drawText(249, 113, 'VOICE / MEMORY')
        p.end()

    def toggle_visibility(self):
        if self.isVisible(): self.hide()
        else: self.show(); self.raise_()

class WinPoint(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]
class WinMSG(ctypes.Structure):
    _fields_ = [('hwnd', ctypes.c_void_p), ('message', ctypes.c_uint), ('wParam', ctypes.c_size_t), ('lParam', ctypes.c_ssize_t), ('time', ctypes.c_uint), ('pt', WinPoint)]
class NativeHotkeyFilter(QAbstractNativeEventFilter):
    def __init__(self, widget): super().__init__(); self.widget = widget
    def nativeEventFilter(self, eventType, message):
        try:
            msg = ctypes.cast(int(message), ctypes.POINTER(WinMSG)).contents
            if msg.message == 0x0312 and msg.wParam == 1:
                self.widget.toggle_visibility(); return True, 0
        except (TypeError, ValueError, OSError): pass
        return False, 0

def make_tray_icon():
    pixmap = QPixmap(64, 64); pixmap.fill(Qt.GlobalColor.transparent)
    p = QPainter(pixmap); p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setPen(QPen(QColor('#00E5FF'), 4)); p.drawArc(9, 15, 46, 32, 30*16, 300*16)
    p.setPen(QPen(QColor('#D500F9'), 4)); p.drawArc(9, 15, 46, 32, 210*16, 300*16); p.end()
    return QIcon(pixmap)

def main():
    app = QApplication(sys.argv); app.setApplicationName('Nova'); app.setQuitOnLastWindowClosed(False)
    widget = NovaWidget()
    flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0) if sys.platform == 'win32' else 0
    assistant_process = subprocess.Popen([sys.executable, str(BASE_DIR / 'main.py'), '--background'], cwd=str(BASE_DIR), creationflags=flags)
    tray = QSystemTrayIcon(make_tray_icon(), app); tray.setToolTip('Nova â€” Floating Assistant')
    menu = QMenu(); show_action = QAction('Show / Hide Nova', menu); show_action.triggered.connect(widget.toggle_visibility); menu.addAction(show_action)
    menu.addSeparator(); quit_action = QAction('Exit Nova', menu); quit_action.triggered.connect(app.quit); menu.addAction(quit_action)
    tray.setContextMenu(menu); tray.activated.connect(lambda reason: widget.toggle_visibility() if reason == QSystemTrayIcon.ActivationReason.Trigger else None)
    if QSystemTrayIcon.isSystemTrayAvailable(): tray.show()
    registered = False; hotkey_filter = None
    if sys.platform == 'win32':
        try:
            user32 = ctypes.windll.user32; registered = bool(user32.RegisterHotKey(None, 1, 0x0001, 0x20))
            if registered: hotkey_filter = NativeHotkeyFilter(widget); app.installNativeEventFilter(hotkey_filter); print('Nova shortcut: Alt + Space')
        except Exception: pass
    widget.show()
    def cleanup():
        if sys.platform == 'win32' and registered: ctypes.windll.user32.UnregisterHotKey(None, 1)
        tray.hide()
    app.aboutToQuit.connect(cleanup)
    print('Nova UI running. Hover to expand; right-click to close.')
    sys.exit(app.exec())
if __name__ == '__main__': main()
'''

# Validate both full patched sources before writing them.
ast.parse(main_src)
ast.parse(widget_code)
MAIN.write_text(main_src, encoding='utf-8')
WIDGET.write_text(widget_code, encoding='utf-8')
ast.parse(MAIN.read_text(encoding='utf-8-sig'))
ast.parse(WIDGET.read_text(encoding='utf-8-sig'))
print('Nova UI upgrade installed and syntax verified.')
print('Backups: main_before_ui_upgrade.py and nova_widget_before_ui_upgrade.py')
print('UI: compact pill, hover conversation dock, animated orb/wave, mic and mute controls.')



