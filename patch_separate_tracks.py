from pathlib import Path
from datetime import datetime
import shutil, py_compile, sys

p = Path("nova_studio_qt.py")
s = p.read_text(encoding="utf-8")

start = s.find("class TimelineWidget(QWidget):")
end = s.find("\nclass NovaStudioQt(QMainWindow):")
if start < 0 or end < 0:
    sys.exit("ERROR: TimelineWidget boundaries not found. No changes made.")

backup_dir = Path("studio_rebuild_backups")
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"before_separate_tracks_{datetime.now():%Y%m%d_%H%M%S}.py"
shutil.copy2(p, backup)

new_class = r'''
class TimelineWidget(QWidget):
    """Separate editable video and audio timeline tracks."""

    def __init__(self, seek_callback, parent=None):
        super().__init__(parent)
        self.seek_callback = seek_callback
        self.duration_ms = 0
        self.position_ms = 0
        self.clip_name = "No clip loaded"
        self.video_clips = []
        self.audio_clips = []
        self.selected_track = "video"
        self.selected_clip = None
        self.drag_mode = None
        self.drag_x = 0
        self.drag_snapshot = None
        self.setMinimumHeight(155)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.setMouseTracking(True)

    @property
    def clips(self):
        """Compatibility alias for existing video playback code."""
        return self.video_clips

    @clips.setter
    def clips(self, value):
        self.video_clips = value

    def current_clips(self):
        return self.video_clips if self.selected_track == "video" else self.audio_clips

    def set_track(self, track):
        if track in ("video", "audio"):
            self.selected_track = track
            self.selected_clip = None
            self.update()

    def set_clip(self, name):
        self.clip_name = name
        self.video_clips = []
        self.audio_clips = []
        self.selected_clip = None
        self.update()

    def set_duration(self, duration):
        self.duration_ms = max(0, int(duration))
        if self.duration_ms and not self.video_clips:
            base = {
                "name": self.clip_name,
                "start": 0,
                "end": self.duration_ms,
                "source_in": 0,
                "source_out": self.duration_ms,
            }
            self.video_clips = [base.copy()]
            self.audio_clips = [base.copy()]
            self.selected_clip = 0
        self.update()

    def set_position(self, position):
        self.position_ms = max(0, int(position))
        self.update()

    def _track_rect(self):
        return 100, max(101, self.width() - 18)

    def _scale_duration(self):
        latest = max(
            [self.duration_ms]
            + [c["end"] for c in self.video_clips]
            + [c["end"] for c in self.audio_clips]
        )
        return max(latest, 1)

    def _x_at(self, milliseconds):
        left, right = self._track_rect()
        return left + int(milliseconds / self._scale_duration() * (right - left))

    def _time_at_x(self, x):
        left, right = self._track_rect()
        ratio = min(1.0, max(0.0, (x - left) / max(1, right - left)))
        return int(ratio * self._scale_duration())

    def add_split(self, position):
        clips = self.current_clips()
        position = int(position)
        for index, clip in enumerate(clips):
            if clip["start"] < position < clip["end"]:
                source_cut = clip["source_in"] + position - clip["start"]
                if not clip["source_in"] < source_cut < clip["source_out"]:
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
                clips.insert(index + 1, right_clip)
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

        painter.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
        painter.setPen(QColor("#aeb8ca"))
        painter.drawText(14, 23, "TIME")
        painter.setPen(QColor("#ffffff" if self.selected_track == "video" else "#aeb8ca"))
        painter.drawText(14, 65, "V1")
        painter.setPen(QColor("#ffffff" if self.selected_track == "audio" else "#aeb8ca"))
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

        for track_name, clips, y, base_color in (
            ("video", self.video_clips, 45, "#147dba"),
            ("audio", self.audio_clips, 88, "#287b67"),
        ):
            for i, clip in enumerate(clips):
                x1, x2 = self._x_at(clip["start"]), self._x_at(clip["end"])
                w = max(3, x2 - x1 - 2)
                selected = track_name == self.selected_track and i == self.selected_clip
                painter.setPen(QPen(QColor("#ffffff") if selected else QColor(base_color), 2 if selected else 1))
                painter.setBrush(QColor("#168dce") if selected and track_name == "video" else QColor("#319b82") if selected else QColor(base_color))
                painter.drawRoundedRect(x1 + 1, y, w, 28, 4, 4)
                painter.setPen(QColor("#ffffff"))
                if w > 50:
                    label = f"V{i + 1}" if track_name == "video" else f"A{i + 1}"
                    painter.drawText(x1 + 5, y + 18, label)

        x = self._x_at(self.position_ms)
        painter.setPen(QPen(QColor("#58c3ff"), 2))
        painter.drawLine(x, 27, x, 121)
        painter.end()

    @staticmethod
    def _stamp(milliseconds):
        seconds = max(0, int(milliseconds / 1000))
        minutes, seconds = divmod(seconds, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return
        x, y = event.position().x(), event.position().y()
        if 42 <= y <= 76:
            self.selected_track = "video"
        elif 85 <= y <= 120:
            self.selected_track = "audio"
        else:
            self.drag_mode = "seek"
            self.seek_callback(self._time_at_x(x))
            return

        clips = self.current_clips()
        t = self._time_at_x(x)
        hit = next((i for i in range(len(clips) - 1, -1, -1)
                    if clips[i]["start"] <= t <= clips[i]["end"]), None)
        self.selected_clip = hit
        if hit is None:
            self.drag_mode = None
            self.update()
            return

        clip = clips[hit]
        if abs(x - self._x_at(clip["start"])) <= 8:
            self.drag_mode = "left"
        elif abs(x - self._x_at(clip["end"])) <= 8:
            self.drag_mode = "right"
        else:
            self.drag_mode = "move"
        self.drag_x = x
        self.drag_snapshot = clip.copy()
        self.update()

    def mouseMoveEvent(self, event):
        if not self.drag_mode:
            return
        x = event.position().x()
        if self.drag_mode == "seek":
            self.seek_callback(self._time_at_x(x))
            return
        clips = self.current_clips()
        if self.selected_clip is None or self.drag_snapshot is None:
            return
        c = clips[self.selected_clip]
        original = self.drag_snapshot
        delta = int((x - self.drag_x) / max(1, self._track_rect()[1] - self._track_rect()[0]) * self._scale_duration())
        if self.drag_mode == "move":
            length = original["end"] - original["start"]
            c["start"] = max(0, original["start"] + delta)
            c["end"] = c["start"] + length
        elif self.drag_mode == "left":
            new_start = max(0, min(original["start"] + delta, original["end"] - 100))
            c["source_in"] = original["source_in"] + new_start - original["start"]
            c["start"] = new_start
        elif self.drag_mode == "right":
            new_end = max(original["start"] + 100, original["end"] + delta)
            new_out = original["source_out"] + new_end - original["end"]
            if new_out <= self.duration_ms:
                c["end"], c["source_out"] = new_end, new_out
        self.update()

    def mouseReleaseEvent(self, event):
        self.drag_mode = None
        self.drag_snapshot = None
        self.update()
'''

s = s[:start] + new_class + s[end:]

# Make delete remove from the selected track only.
method_start = s.find("    def delete_selected_clip(self):")
method_end = s.find("\n    def _playback_error", method_start)
if method_start < 0 or method_end < 0:
    sys.exit("ERROR: delete_selected_clip method not found. Original file preserved.")

delete_method = '''
    def delete_selected_clip(self):
        clips = self.timeline_widget.current_clips()
        index = self.timeline_widget.selected_clip
        if index is None or not (0 <= index < len(clips)):
            self.statusBar().showMessage("Select a clip on V1 or A1 first.")
            return
        clips.pop(index)
        self.timeline_widget.selected_clip = (
            min(index, len(clips) - 1) if clips else None
        )
        self.timeline_widget.update()
        if self.timeline_widget.selected_track == "video":
            self.active_clip_index = None
            self.player.pause()
        self.statusBar().showMessage(
            f"Deleted selected {self.timeline_widget.selected_track.upper()} clip only."
        )
'''
s = s[:method_start] + delete_method + s[method_end:]

# Add explicit track-selection actions to the toolbar.
anchor = '            ("Delete Selected Clip", self.delete_selected_clip),'
if anchor not in s:
    sys.exit("ERROR: Delete toolbar action not found. Original file preserved.")
s = s.replace(anchor, anchor + '''
            ("Select Video", lambda: self.timeline_widget.set_track("video")),
            ("Select Audio", lambda: self.timeline_widget.set_track("audio")),''', 1)

tmp = p.with_suffix(".tmp.py")
tmp.write_text(s, encoding="utf-8")
try:
    py_compile.compile(str(tmp), doraise=True)
except Exception as exc:
    tmp.unlink(missing_ok=True)
    print("Syntax check failed; original file is unchanged:", exc)
    sys.exit(1)

shutil.move(str(tmp), str(p))
print("Separate video/audio timeline patch applied.")
print("Syntax check passed.")
print("Backup:", backup)
print("Note: This separates editing models; independent audio playback is a separate integration step.")
