from pathlib import Path
from datetime import datetime
import py_compile
import shutil
import sys

path = Path("nova_studio_qt.py")
if not path.is_file():
    sys.exit("ERROR: nova_studio_qt.py not found. Run this from the project folder.")

source = path.read_text(encoding="utf-8")
start = source.find("class TimelineWidget(QWidget):")
end = source.find("\nclass NovaStudioQt(QMainWindow):")

if start < 0 or end < 0 or end <= start:
    sys.exit("ERROR: Could not safely locate TimelineWidget. No changes made.")

backup_dir = Path("studio_rebuild_backups")
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"before_editable_timeline_{datetime.now():%Y%m%d_%H%M%S}.py"
shutil.copy2(path, backup)

new_class = r'''
class TimelineWidget(QWidget):
    """Editable visual clip timeline; source media remains unchanged."""

    def __init__(self, seek_callback, parent=None):
        super().__init__(parent)
        self.seek_callback = seek_callback
        self.duration_ms = 0
        self.position_ms = 0
        self.clip_name = "No clip loaded"
        self.clips = []
        self.selected_clip = None
        self.drag_mode = None
        self.drag_x = 0
        self.drag_snapshot = None
        self.setMinimumHeight(155)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    def set_clip(self, name):
        self.clip_name = name
        self.clips = []
        self.selected_clip = None
        self.drag_mode = None
        self.update()

    def set_duration(self, duration):
        self.duration_ms = max(0, int(duration))
        if self.duration_ms and not self.clips:
            self.clips = [{
                "name": self.clip_name,
                "start": 0,
                "end": self.duration_ms,
                "source_in": 0,
                "source_out": self.duration_ms,
            }]
            self.selected_clip = 0
        elif self.clips and self.duration_ms:
            for clip in self.clips:
                clip["source_out"] = min(clip["source_out"], self.duration_ms)
                clip["source_in"] = min(clip["source_in"], clip["source_out"])
        self.update()

    def set_position(self, position):
        self.position_ms = max(0, int(position))
        self.update()

    def _track_rect(self):
        return 100, max(101, self.width() - 18)

    def _scale_duration(self):
        latest = max((c["end"] for c in self.clips), default=0)
        return max(self.duration_ms, latest, 1)

    def _x_at(self, milliseconds):
        left, right = self._track_rect()
        return left + int(milliseconds / self._scale_duration() * (right - left))

    def _time_at_x(self, x):
        left, right = self._track_rect()
        ratio = min(1.0, max(0.0, (x - left) / max(1, right - left)))
        return int(ratio * self._scale_duration())

    def add_split(self, position):
        position = int(position)
        for index, clip in enumerate(self.clips):
            if clip["start"] < position < clip["end"]:
                offset = position - clip["start"]
                source_cut = clip["source_in"] + offset
                if source_cut <= clip["source_in"] or source_cut >= clip["source_out"]:
                    return False
                right_clip = {
                    "name": clip["name"],
                    "start": position,
                    "end": clip["end"],
                    "source_in": source_cut,
                    "source_out": clip["source_out"],
                }
                clip["end"] = position
                clip["source_out"] = source_cut
                self.clips.insert(index + 1, right_clip)
                self.selected_clip = index + 1
                self.update()
                return True
        return False

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), QColor("#171a20"))
        left, right = self._track_rect()
        width = max(1, right - left)
        total = self._scale_duration()

        painter.setPen(QColor("#aeb8ca"))
        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.drawText(14, 23, "TIME")
        painter.drawText(14, 65, "V1")
        painter.drawText(14, 108, "A1")
        painter.setPen(QPen(QColor("#424957"), 1))
        painter.drawLine(left, 33, right, 33)

        if self.duration_ms > 0:
            seconds_total = total / 1000
            step = 1 if seconds_total <= 20 else 5 if seconds_total <= 120 else 10 if seconds_total <= 600 else 30
            tick = 0
            while tick * 1000 <= total:
                x = left + int(tick / max(0.001, seconds_total) * width)
                painter.setPen(QPen(QColor("#626d7f"), 1))
                painter.drawLine(x, 29, x, 38)
                painter.setPen(QColor("#aeb8ca"))
                painter.setFont(QFont("Segoe UI", 8))
                painter.drawText(x + 3, 18, self._stamp(tick * 1000))
                tick += step

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#242a35"))
        painter.drawRoundedRect(left, 44, width, 30, 4, 4)
        painter.drawRoundedRect(left, 87, width, 30, 4, 4)

        for i, clip in enumerate(self.clips):
            x1, x2 = self._x_at(clip["start"]), self._x_at(clip["end"])
            w = max(3, x2 - x1 - 2)
            selected = i == self.selected_clip
            painter.setPen(QPen(QColor("#ffffff") if selected else QColor("#147dba"), 2 if selected else 1))
            painter.setBrush(QColor("#168dce") if selected else QColor("#147dba"))
            painter.drawRoundedRect(x1 + 1, 45, w, 28, 4, 4)
            painter.setPen(QColor("#e8f7ff"))
            painter.setFont(QFont("Segoe UI", 8, QFont.DemiBold))
            if w > 45:
                painter.drawText(x1 + 5, 63, f"Clip {i + 1}")
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor("#287b67"))
            painter.drawRoundedRect(x1 + 1, 88, w, 28, 4, 4)
            painter.setPen(QColor("#e5fff5"))
            if w > 65:
                painter.drawText(x1 + 5, 106, f"Audio {i + 1}")

        x = self._x_at(self.position_ms)
        painter.setPen(QPen(QColor("#58c3ff"), 2))
        painter.drawLine(x, 27, x, 121)
        painter.setBrush(QColor("#58c3ff"))
        painter.setPen(Qt.NoPen)
        QPoint = __import__("PySide6.QtCore", fromlist=["QPoint"]).QPoint
        painter.drawPolygon([QPoint(x - 5, 26), QPoint(x + 5, 26), QPoint(x, 33)])
        painter.end()

    @staticmethod
    def _stamp(milliseconds):
        seconds = max(0, int(milliseconds / 1000))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton or not self.clips:
            return
        x = event.position().x()
        y = event.position().y()
        t = self._time_at_x(x)

        hit = None
        for i in range(len(self.clips) - 1, -1, -1):
            c = self.clips[i]
            if c["start"] <= t <= c["end"] and 42 <= y <= 120:
                hit = i
                break

        if hit is None:
            self.drag_mode = "seek"
            self.seek_callback(min(t, self.duration_ms))
            return

        self.selected_clip = hit
        clip = self.clips[hit]
        edge_px = 8
        if abs(x - self._x_at(clip["start"])) <= edge_px:
            self.drag_mode = "left"
        elif abs(x - self._x_at(clip["end"])) <= edge_px:
            self.drag_mode = "right"
        else:
            self.drag_mode = "move"

        self.drag_x = x
        self.drag_snapshot = clip.copy()
        if self.drag_mode == "seek":
            self.seek_callback(min(t, self.duration_ms))
        self.update()

    def mouseMoveEvent(self, event):
        if not self.drag_mode:
            return
        x = event.position().x()
        if self.drag_mode == "seek":
            self.seek_callback(min(self._time_at_x(x), self.duration_ms))
            return
        if self.selected_clip is None or self.drag_snapshot is None:
            return

        c = self.clips[self.selected_clip]
        original = self.drag_snapshot
        delta = int((x - self.drag_x) / max(1, self._track_rect()[1] - self._track_rect()[0]) * self._scale_duration())

        if self.drag_mode == "move":
            length = original["end"] - original["start"]
            new_start = max(0, original["start"] + delta)
            c["start"] = new_start
            c["end"] = new_start + length
        elif self.drag_mode == "left":
            new_start = max(0, min(original["start"] + delta, original["end"] - 100))
            c["source_in"] = original["source_in"] + (new_start - original["start"])
            c["start"] = new_start
        elif self.drag_mode == "right":
            new_end = max(original["start"] + 100, original["end"] + delta)
            new_source_out = original["source_out"] + (new_end - original["end"])
            if new_source_out <= self.duration_ms:
                c["end"] = new_end
                c["source_out"] = new_source_out

        self.update()

    def mouseReleaseEvent(self, event):
        if self.drag_mode and self.drag_mode not in ("seek",):
            self.update()
        self.drag_mode = None
        self.drag_snapshot = None
'''

updated = source[:start] + new_class + source[end:]
temp = path.with_suffix(".tmp.py")
temp.write_text(updated, encoding="utf-8")

try:
    py_compile.compile(str(temp), doraise=True)
except Exception as exc:
    temp.unlink(missing_ok=True)
    print(f"ERROR: Syntax check failed. Original file untouched. {exc}")
    sys.exit(1)

shutil.move(str(temp), str(path))
print(f"Timeline patch applied. Backup: {backup}")
print("Syntax check passed.")
print("NOTE: Clip movement/trimming is currently a visual edit model; playback/export integration is next.")
