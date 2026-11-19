import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, QTimer, QThread, Signal
from PySide6.QtGui import QAction, QPainter, QColor, QPen, QFont, QImage, QPixmap
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QListWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QSlider, QStatusBar, QToolBar, QStackedLayout, QComboBox, QCheckBox, QSpinBox,
    QDoubleSpinBox, QFormLayout, QMessageBox, QInputDialog, QColorDialog, QFontDialog, QGridLayout, QPlainTextEdit
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput, QVideoSink
from PySide6.QtMultimediaWidgets import QVideoWidget






# NOVA_STAGE4_BACKGROUND_WORKER
class NovaAIEditWorker(QThread):
    succeeded = Signal(str, str, object)
    failed = Signal(str)
    progress = Signal(str)

    def __init__(self, plan, source, request_text, parent=None):
        super().__init__(parent)
        self.plan = plan
        self.source = source
        self.request_text = request_text

    def run(self):
        try:
            plan = self.plan
            actions = plan.get('actions', [])
            source = self.source
            original_input = Path(source).resolve()
            current_input = original_input
            action_results = []
            self.progress.emit('Preparing exports...')
            import nova_video_editor as editor
            import re
            export_dir = Path(getattr(
                editor, 'EXPORT_DIR',
                Path(__file__).resolve().parent / 'Nova_Exports'
            ))
            export_dir.mkdir(parents=True, exist_ok=True)
            import re

            export_dir = Path(
                getattr(
                    editor, "EXPORT_DIR",
                    Path(__file__).resolve().parent / "Nova_Exports"
                )
            )
            export_dir.mkdir(parents=True, exist_ok=True)

            current_input = Path(source).resolve()
            original_input = current_input
            action_results = []

            def find_output(result, before):
                output = None

                # Prefer the exact path returned by the editor function.
                if isinstance(result, str) and "saved to:" in result.lower():
                    marker = result.lower().rfind("saved to:")
                    path_text = result[marker + len("saved to:"):].strip()
                    path_text = path_text.strip().strip('`"').strip("'")
                    possible = Path(path_text).expanduser()
                    if possible.is_file():
                        output = possible.resolve()

                # Fallback: find a newly created export.
                if output is None:
                    candidates = [
                        p.resolve() for p in export_dir.iterdir()
                        if p.is_file()
                        and str(p.resolve()) not in before
                        and p.stat().st_size > 0
                    ]
                    if candidates:
                        output = max(
                            candidates,
                            key=lambda p: p.stat().st_mtime
                        )

                if output is None or not output.is_file():
                    raise RuntimeError(
                        "Could not identify the exported file for this action."
                    )
                if output == original_input:
                    raise RuntimeError(
                        "An action unexpectedly returned the original source file."
                    )
                if output.stat().st_size == 0:
                    raise RuntimeError("The exported file is empty.")

                return output.resolve()

            # NOVA_STAGE3B_MULTI_ACTION
            for index, item in enumerate(actions, start=1):
                if not isinstance(item, dict):
                    raise ValueError(f"Action {index} has an invalid format.")

                action = item.get("action")
                params = item.get("parameters", {})
                if not isinstance(params, dict):
                    raise ValueError(f"Action {index} has invalid parameters.")

                input_path = current_input
                before = {
                    str(p.resolve())
                    for p in export_dir.iterdir() if p.is_file()
                }

                if action == "trim":
                    request_text = (
                        self.request_text.strip().lower()
                    )
                    opening_trim = re.search(
                        r"(?:trim|cut|remove|delete)\s+(?:the\s+)?"
                        r"(?:first|initial)\s+(\d+(?:\.\d+)?)\s*"
                        r"(seconds?|secs?|s)\b",
                        request_text
                    )
                    if not opening_trim:
                        opening_trim = re.search(
                            r"(?:trim|cut|remove|delete)\s+(?:the\s+)?"
                            r"(?:opening|beginning)\s+(\d+(?:\.\d+)?)\s*"
                            r"(seconds?|secs?|s)\b",
                            request_text
                        )

                    if opening_trim:
                        start_seconds = float(opening_trim.group(1))
                        metadata = editor.probe_video(str(input_path))
                        total_duration = float(
                            metadata.get("format", {}).get("duration", 0)
                        )
                        if total_duration <= start_seconds:
                            raise ValueError(
                                "The video must be longer than the opening "
                                "section being removed."
                            )
                        duration = total_duration - start_seconds
                    else:
                        start_seconds = float(params["start_seconds"])
                        duration = float(params["duration_seconds"])

                    if start_seconds < 0 or duration <= 0:
                        raise ValueError(
                            "Trim start must be >= 0 and duration > 0."
                        )
                    # NOVA_TRIM_DURATION_BOUNDS_V1
                    input_metadata = editor.probe_video(str(input_path))
                    total_duration = float(
                        input_metadata.get("format", {}).get("duration", 0)
                    )
                    if total_duration <= 0:
                        raise ValueError(
                            "Could not determine the input video's duration."
                        )
                    if start_seconds < 0 or start_seconds >= total_duration:
                        raise ValueError(
                            "Trim start must be within the video's duration."
                        )
                    if duration <= 0:
                        raise ValueError("Trim duration must be greater than zero.")
                    duration = min(duration, total_duration - start_seconds)
                    print(
                        "[TRIM DIAGNOSTIC] "
                        f"input={Path(input_path).resolve()} | "
                        f"start={start_seconds} | duration={duration}",
                        flush=True
                    )
                    input_metadata = editor.probe_video(str(input_path))
                    input_video = next(
                        (
                            stream for stream in input_metadata.get("streams", [])
                            if stream.get("codec_type") == "video"
                        ),
                        {}
                    )
                    print(
                        "[TRIM INPUT METADATA] "
                        f"resolution={input_video.get('width')}x"
                        f"{input_video.get('height')} | "
                        f"duration={input_metadata.get('format', {}).get('duration')}",
                        flush=True
                    )
                    result = editor.trim_video(
                        str(input_path), start_seconds, duration
                    )
                    print(
                        f"[TRIM RESULT] {result}",
                        flush=True
                    )

                elif action == "change_speed":
                    speed = float(params["speed"])
                    if not 0.25 <= speed <= 4.0:
                        raise ValueError("Speed must be between 0.25x and 4x.")
                    result = editor.change_speed(str(input_path), speed)

                elif action == "resize":
                    width, height = int(params["width"]), int(params["height"])
                    if not (2 <= width <= 7680 and 2 <= height <= 4320):
                        raise ValueError("Resize dimensions are outside supported limits.")
                    result = editor.resize_video(
                        str(input_path), width, height
                    )

                elif action == "crop":
                    width, height = int(params["width"]), int(params["height"])
                    x, y = int(params.get("x", 0)), int(params.get("y", 0))
                    if not (
                        2 <= width <= 7680 and 2 <= height <= 4320
                        and 0 <= x <= 7680 and 0 <= y <= 7680
                    ):
                        raise ValueError("Crop dimensions or offsets are invalid.")
                    result = editor.crop_video(
                        str(input_path), width, height, x, y
                    )

                elif action == "brightness":
                    brightness = float(params["brightness"])
                    if not -1.0 <= brightness <= 1.0:
                        raise ValueError("Brightness must be between -1 and 1.")
                    result = editor.adjust_brightness(
                        str(input_path), brightness
                    )

                elif action == "volume":
                    volume = float(params["volume"])
                    if not 0.0 <= volume <= 5.0:
                        raise ValueError("Volume must be between 0 and 5.")
                    result = editor.adjust_volume(str(input_path), volume)

                elif action == "contrast":
                    contrast = float(params["contrast"])
                    if not 0.0 <= contrast <= 3.0:
                        raise ValueError("Contrast must be between 0 and 3.")
                    result = editor.adjust_color(
                        str(input_path), contrast=contrast
                    )

                elif action == "saturation":
                    saturation = float(params["saturation"])
                    if not 0.0 <= saturation <= 3.0:
                        raise ValueError("Saturation must be between 0 and 3.")
                    result = editor.adjust_color(
                        str(input_path), saturation=saturation
                    )

                elif action == "normalize_audio":
                    result = editor.normalize_audio(str(input_path))

                elif action == "convert_mp4":
                    result = editor.convert_to_mp4(str(input_path))

                elif action == "extract_audio":
                    result = editor.extract_audio(str(input_path))

                else:
                    raise ValueError(
                        f"Action '{action}' is not supported by this editor."
                    )

                output = find_output(result, before)
                current_input = output
                action_results.append(
                    f"{index}. {action}: {result or 'Exported successfully'}"
                    f"\n   Output: {output}"
                )
            self.succeeded.emit(
                str(current_input), str(original_input), action_results
            )
        except Exception as exc:
            self.failed.emit(str(exc))



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
        self.text_clips = []
        self.selected_track = "video"
        self.selected_clip = None
        self.drag_mode = None
        self.drag_x = 0
        self.drag_snapshot = None
        self.setMinimumHeight(190)
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
        if self.selected_track == "text":
            return self.text_clips
        return self.video_clips if self.selected_track == "video" else self.audio_clips

    def set_track(self, track):
        if track in ("video", "audio", "text"):

            self.selected_track = track
            self.selected_clip = None
            self.update()

    def set_clip(self, name):
        self.clip_name = name
        self.video_clips = []
        self.audio_clips = []
        self.text_clips = []
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
        # Scale to the edited timeline, not the original source-file duration.
        latest = max([0] + [c["end"] for c in self.video_clips] + [c["end"] for c in self.text_clips])
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
                if self.selected_track == "text":
                    right_clip = clip.copy()
                    right_clip["start"] = position
                    clip["end"] = position
                else:
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
        painter.setPen(QColor("#ffffff" if self.selected_track == "text" else "#aeb8ca"))
        painter.drawText(14, 151, "T1")

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
        painter.drawRoundedRect(left, 130, width, 30, 4, 4)

        for track_name, clips, y, base_color in (
            ("video", self.video_clips, 45, "#147dba"),
            ("audio", self.audio_clips, 88, "#287b67"),
            ("text", self.text_clips, 131, "#8e5bd9"),
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
                    label = (f"V{i + 1}" if track_name == "video" else
                             f"A{i + 1}" if track_name == "audio" else
                             f"T{i + 1} {clip.get('text', 'Text').replace(chr(10), ' ')[:18]}")
                    painter.drawText(x1 + 5, y + 18, label)

        x = self._x_at(self.position_ms)
        painter.setPen(QPen(QColor("#58c3ff"), 2))
        painter.drawLine(x, 27, x, 164)
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
        elif 128 <= y <= 163:
            self.selected_track = "text"
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
            c["start"] = new_start
            if self.selected_track != "text":
                c["source_in"] = original["source_in"] + new_start - original["start"]
        elif self.drag_mode == "right":
            new_end = max(original["start"] + 100, original["end"] + delta)
            if self.selected_track == "text":
                c["end"] = new_end
            else:
                new_out = original["source_out"] + new_end - original["end"]
                if new_out <= self.duration_ms:
                    c["end"], c["source_out"] = new_end, new_out
        self.update()

    def mouseReleaseEvent(self, event):
        self.drag_mode = None
        self.drag_snapshot = None
        self.update()

class NovaStudioQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Studio")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 650)

        self.duration_ms = 0                 # original media/source duration
        self.timeline_duration_ms = 0         # duration after timeline edits
        self.is_seeking = False
        self.active_clip_index = None
        self._gap_playing = False
        self._gap_next_index = None
        self._gap_target_ms = 0
        self._gap_position_ms = 0
        self._gap_timer = QTimer(self)
        self._gap_timer.setInterval(30)
        self._gap_timer.timeout.connect(self._advance_gap)

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        self._build_ui()
        # Render frames into a QLabel so text can be composited reliably.
        self.video_sink = QVideoSink(self)
        self.player.setVideoSink(self.video_sink)
        self.video_sink.videoFrameChanged.connect(self._display_video_frame)
        self._show_video_preview()
        self.player.positionChanged.connect(self._position_changed)
        self.player.durationChanged.connect(self._duration_changed)
        self.player.playbackStateChanged.connect(self._playback_changed)
        self.player.errorOccurred.connect(self._playback_error)
        self.backspace_delete_action = QAction('Delete selected clip', self)
        self.backspace_delete_action.setShortcut('Backspace')
        self.backspace_delete_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.backspace_delete_action.triggered.connect(self.delete_selected_clip)
        self.addAction(self.backspace_delete_action)

    def _build_ui(self):
        self.setStyleSheet("""
            QMainWindow, QWidget {
                background: #0A0D14;
                color: #E8F2FF;
                font-family: "Segoe UI";
                font-size: 9pt;
            }
            QMainWindow { background: #080B11; }

            QMenuBar, QToolBar {
                background: #101622;
                color: #DDEBFF;
                border: none;
                border-bottom: 1px solid #26354A;
                padding: 7px;
                spacing: 7px;
            }
            QMenuBar::item {
                background: transparent;
                padding: 6px 11px;
                border-radius: 5px;
            }
            QMenuBar::item:selected, QMenu::item:selected {
                background: #16384A;
                color: #75F0FF;
            }
            QMenu {
                background: #111927;
                color: #E8F2FF;
                border: 1px solid #35435C;
                padding: 5px;
            }
            QMenu::item { padding: 7px 25px; }

            QFrame#panel {
                background: #111723;
                border: 1px solid #28364B;
                border-radius: 10px;
            }
            QLabel#heading {
                color: #78EFFF;
                font-weight: 800;
                letter-spacing: 1px;
            }
            QLabel#muted { color: #8497B2; }

            QPushButton {
                background: #1A2434;
                color: #E4F0FF;
                border: 1px solid #34445B;
                padding: 8px 13px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background: #24374B;
                border-color: #47CFEA;
                color: #FFFFFF;
            }
            QPushButton:pressed { background: #13202E; }
            QPushButton:disabled {
                background: #131923;
                color: #5F6E82;
                border-color: #222D3C;
            }
            QPushButton#primary {
                background: #123E55;
                color: #E9FCFF;
                border: 1px solid #28C8E8;
                font-weight: 700;
            }
            QPushButton#primary:hover {
                background: #17627B;
                border-color: #8AF5FF;
            }
            QPushButton#tool {
                min-width: 38px;
                min-height: 34px;
                padding: 4px;
                font-weight: 700;
            }

            QListWidget, QTreeWidget, QTableWidget,
            QTabWidget::pane {
                background: #0B111B;
                color: #DDEAFF;
                border: 1px solid #27364B;
                padding: 5px;
                outline: none;
                selection-background-color: #164457;
                selection-color: #8BF4FF;
            }
            QListWidget::item, QTreeWidget::item {
                padding: 7px;
                border-radius: 4px;
            }
            QListWidget::item:selected, QTreeWidget::item:selected {
                background: #15394A;
                color: #8AF2FF;
                border-left: 2px solid #39DDF5;
            }

            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox,
            QSpinBox, QDoubleSpinBox {
                background: #0B111B;
                color: #E8F2FF;
                border: 1px solid #303F55;
                border-radius: 6px;
                padding: 7px;
                selection-background-color: #164457;
            }
            QLineEdit:focus, QTextEdit:focus,
            QPlainTextEdit:focus, QComboBox:focus,
            QSpinBox:focus, QDoubleSpinBox:focus {
                border: 1px solid #45DDF4;
                background: #0D1622;
            }

            QTabWidget::pane {
                top: -1px;
                padding: 7px;
                border: 1px solid #2B3A50;
                border-radius: 7px;
            }
            QTabBar::tab {
                background: #151D2B;
                color: #91A2BA;
                padding: 9px 12px;
                border: 1px solid #29374B;
                margin-right: 3px;
            }
            QTabBar::tab:selected {
                background: #20223B;
                color: #B6A9FF;
                border-color: #7667D9;
                border-bottom: 2px solid #9A85FF;
            }

            QSlider::groove:horizontal {
                height: 5px;
                background: #2B394D;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #4AE5F5;
                width: 14px;
                margin: -5px 0;
                border-radius: 6px;
            }
            QCheckBox { spacing: 8px; }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
            }
            QCheckBox::indicator:unchecked {
                background: #0B111B;
                border: 1px solid #566A83;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background: #17617A;
                border: 1px solid #4AE5F5;
                border-radius: 4px;
            }

            QStatusBar {
                background: #090D14;
                color: #9DB0C9;
                border-top: 1px solid #28364B;
            }
            QSplitter::handle {
                background: #1D2B3D;
            }
            QSplitter::handle:hover {
                background: #3ACBE8;
            }
            QScrollBar:vertical {
                background: #0B111B;
                width: 10px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #34465D;
                min-height: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4A94AC;
            }
            QScrollBar::add-line:vertical,
            QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar:horizontal {
                background: #0B111B;
                height: 10px;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: #34465D;
                min-width: 24px;
                border-radius: 4px;
            }
            QScrollBar::handle:horizontal:hover {
                background: #4A94AC;
            }
            QScrollBar::add-line:horizontal,
            QScrollBar::sub-line:horizontal {
                width: 0;
            }
        """)

        menu = self.menuBar()
        file_menu = menu.addMenu("File")
        open_action = QAction("Import Video...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.import_video)
        file_menu.addAction(open_action)
        file_menu.addSeparator()
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        edit_menu = menu.addMenu("Edit")
        split_action = QAction("Split at Playhead", self)
        split_action.setShortcut("S")
        split_action.triggered.connect(self.split_at_playhead)
        edit_menu.addAction(split_action)
        delete_action = QAction("Delete Selected Clip", self)
        delete_action.triggered.connect(self.delete_selected_clip)
        edit_menu.addAction(delete_action)

        menu.addMenu("Clip")
        menu.addMenu("View")
        menu.addMenu("Help")

        toolbar = QToolBar("Main Toolbar")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        for label, callback in [
            ("Import", self.import_video),
            ("Play / Pause", self.toggle_play),
            ("Split", self.split_at_playhead),
            ("T  Add Text", self.add_text_overlay),
            ("Delete", self.delete_selected_clip),
        ]:
            action = QAction(label, self)
            action.triggered.connect(callback)
            toolbar.addAction(action)
        toolbar.addSeparator()
        toolbar.addWidget(QLabel("  NOVA STUDIO  /  VIDEO EDITOR"))

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(7, 6, 7, 6)
        root.setSpacing(6)

        # Workspace row: compact tool rail, media bin, preview, inspector.
        workspace = QSplitter(Qt.Horizontal)
        workspace.setChildrenCollapsible(False)
        root.addWidget(workspace, 7)

        tool_rail = QFrame()
        tool_rail.setObjectName("panel")
        rail_layout = QVBoxLayout(tool_rail)
        rail_layout.setContentsMargins(4, 8, 4, 8)
        rail_layout.setSpacing(5)
        for symbol, tooltip in [
            ("Select", "Select"), ("Split", "Split at playhead"),
            ("Clips", "Timeline clips"), ("T", "Text tools"),
            ("Audio", "Audio tools"), ("AI", "AI tools"),
        ]:
            button = QPushButton(symbol)
            button.setObjectName("tool")
            button.setToolTip(tooltip)
            if tooltip == "Split at playhead":
                button.clicked.connect(self.split_at_playhead)
            elif tooltip == "Text tools":
                button.clicked.connect(self.add_text_overlay)
            rail_layout.addWidget(button)
        rail_layout.addStretch()
        workspace.addWidget(tool_rail)

        media_panel = QFrame()
        media_panel.setObjectName("panel")
        media_layout = QVBoxLayout(media_panel)
        media_layout.setContentsMargins(9, 9, 9, 9)
        media_layout.addWidget(self._heading("PROJECT MEDIA"))
        self.media_list = QListWidget()
        self.media_list.itemDoubleClicked.connect(self._open_selected)
        media_layout.addWidget(self.media_list, 1)
        import_button = QPushButton("+ Import Video")
        import_button.setObjectName("primary")
        import_button.clicked.connect(self.import_video)
        media_layout.addWidget(import_button)
        media_layout.addWidget(QLabel("Double-click a file to load it into preview."))
        workspace.addWidget(media_panel)

        preview_panel = QFrame()
        preview_panel.setObjectName("panel")
        preview_layout = QVBoxLayout(preview_panel)
        preview_layout.setContentsMargins(10, 9, 10, 9)
        preview_header = QHBoxLayout()
        preview_header.addWidget(self._heading("PROGRAM MONITOR"))
        preview_header.addStretch()
        preview_header.addWidget(QLabel("FIT"))
        preview_layout.addLayout(preview_header)

        self.preview_stack_host = QWidget()
        self.preview_stack = QStackedLayout(self.preview_stack_host)
        self.preview_stack.setContentsMargins(0, 0, 0, 0)
        # Put the text label in a sibling overlay layer, not inside QVideoWidget.
        # On Windows, QVideoWidget may use a native video surface that covers child labels.
        self.video_page = QWidget()
        video_layers = QGridLayout(self.video_page)
        video_layers.setContentsMargins(0, 0, 0, 0)
        video_layers.setSpacing(0)
        self.video = QLabel()
        self.video.setMinimumSize(360, 240)
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setScaledContents(False)
        self.video.setStyleSheet("background: #08090c; border: 1px solid #30343e;")
        self.text_overlay = QLabel()
        self.text_overlay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_overlay.setWordWrap(True)
        self.text_overlay.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.text_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.text_overlay.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.text_overlay.setAttribute(Qt.WidgetAttribute.WA_AlwaysStackOnTop, True)
        self.text_overlay.setStyleSheet("QLabel { color: white; background: transparent; border: none; padding: 16px; }")
        self.text_overlay.hide()
        self.text_overlay.installEventFilter(self)
        video_layers.addWidget(self.video, 0, 0)
        video_layers.addWidget(self.text_overlay, 0, 0, Qt.AlignmentFlag.AlignCenter)
        self.black_overlay = QFrame()
        self.black_overlay.setStyleSheet("background: #000000; border: 1px solid #30343e;")
        self.preview_stack.addWidget(self.video_page)
        self.preview_stack.addWidget(self.black_overlay)
        self.preview_stack.setCurrentWidget(self.video_page)
        preview_layout.addWidget(self.preview_stack_host, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("Play")
        self.play_button.setObjectName("primary")
        self.play_button.clicked.connect(self.toggle_play)
        controls.addWidget(self.play_button)
        self.time_label = QLabel("00:00:00 / 00:00:00")
        controls.addWidget(self.time_label)
        controls.addStretch()
        controls.addWidget(QLabel("Playback"))
        preview_layout.addLayout(controls)

        self.seek_slider = QSlider(Qt.Horizontal)
        self.seek_slider.setRange(0, 0)
        self.seek_slider.sliderPressed.connect(self._begin_seek)
        self.seek_slider.sliderReleased.connect(self._finish_seek)
        self.seek_slider.valueChanged.connect(self._seek_preview)
        preview_layout.addWidget(self.seek_slider)
        workspace.addWidget(preview_panel)

        inspector = QFrame()
        inspector.setObjectName("panel")
        inspector_layout = QVBoxLayout(inspector)
        inspector_layout.setContentsMargins(8, 8, 8, 8)
        inspector_layout.addWidget(self._heading("INSPECTOR"))
        from PySide6.QtWidgets import QTabWidget
        inspector_tabs = QTabWidget()

        # Properties: useful controls operate on the current preview/player.
        properties_page = QWidget()
        properties_layout = QVBoxLayout(properties_page)
        properties_form = QFormLayout()
        self.position_spin = QDoubleSpinBox()
        self.position_spin.setRange(0, 999999)
        self.position_spin.setDecimals(2)
        self.position_spin.setSuffix(" s")
        self.position_spin.setToolTip("Seek to a timeline time")
        self.position_spin.valueChanged.connect(self._inspector_seek)
        properties_form.addRow("Playhead", self.position_spin)
        self.speed_combo = QComboBox()
        for speed in ("0.25Ãƒâ€”", "0.5Ãƒâ€”", "0.75Ãƒâ€”", "1.0Ãƒâ€”", "1.25Ãƒâ€”", "1.5Ãƒâ€”", "2.0Ãƒâ€”"):
            self.speed_combo.addItem(speed, float(speed.replace("Ãƒâ€”", "")))
        self.speed_combo.setCurrentIndex(3)
        self.speed_combo.currentIndexChanged.connect(self._apply_speed)
        properties_form.addRow("Playback speed", self.speed_combo)
        properties_layout.addLayout(properties_form)
        self.clip_info_label = QLabel("Select a clip on the timeline to inspect it.")
        self.clip_info_label.setWordWrap(True)
        self.clip_info_label.setObjectName("muted")
        properties_layout.addWidget(self.clip_info_label)
        properties_layout.addStretch()
        inspector_tabs.addTab(properties_page, "Properties")

        # Audio controls apply immediately to QAudioOutput.
        audio_page = QWidget()
        audio_layout = QVBoxLayout(audio_page)
        audio_form = QFormLayout()
        self.volume_slider = QSlider(Qt.Horizontal)
        self.volume_slider.setRange(0, 200)
        self.volume_slider.setValue(100)
        self.volume_slider.valueChanged.connect(self._apply_volume)
        self.volume_value_label = QLabel("100%")
        volume_row = QHBoxLayout()
        volume_row.addWidget(self.volume_slider, 1)
        volume_row.addWidget(self.volume_value_label)
        volume_wrap = QWidget()
        volume_wrap.setLayout(volume_row)
        audio_form.addRow("Volume", volume_wrap)
        self.mute_checkbox = QCheckBox("Mute audio")
        self.mute_checkbox.toggled.connect(self.audio.setMuted)
        audio_layout.addLayout(audio_form)
        audio_layout.addWidget(self.mute_checkbox)
        audio_reset = QPushButton("Reset audio")
        audio_reset.clicked.connect(self._reset_audio)
        audio_layout.addWidget(audio_reset)
        audio_layout.addStretch()
        inspector_tabs.addTab(audio_page, "Audio")

        # Real, available editing actions instead of decorative placeholder labels.
        effects_page = QWidget()
        effects_layout = QVBoxLayout(effects_page)
        effects_note = QLabel("Timeline edits affect the project cut. Export effects are not yet implemented.")
        effects_note.setWordWrap(True)
        effects_note.setObjectName("muted")
        effects_layout.addWidget(effects_note)
        split_button = QPushButton("Split at playhead")
        split_button.clicked.connect(self.split_at_playhead)
        effects_layout.addWidget(split_button)
        delete_button = QPushButton("Delete selected clip")
        delete_button.clicked.connect(self.delete_selected_clip)
        effects_layout.addWidget(delete_button)
        gap_button = QPushButton("Add 1-second gap at playhead")
        gap_button.clicked.connect(self.add_gap_at_playhead)
        effects_layout.addWidget(gap_button)
        effects_layout.addStretch()
        inspector_tabs.addTab(effects_page, "Editing")

        # AI Editing: creates a reviewable plan only; it does not execute edits.
        ai_page = QWidget()
        ai_layout = QVBoxLayout(ai_page)

        ai_intro = QLabel(
            "Describe the edit you want. Nova will prepare a plan for review."
        )
        ai_intro.setWordWrap(True)
        ai_intro.setObjectName("muted")
        ai_layout.addWidget(ai_intro)

        self.ai_request_input = QPlainTextEdit()
        self.ai_request_input.setPlaceholderText(
            "Example: Make this video play at 1.25x speed."
        )
        self.ai_request_input.setMaximumBlockCount(100)
        self.ai_request_input.setFixedHeight(90)
        ai_layout.addWidget(self.ai_request_input)

        self.ai_plan_button = QPushButton("Generate Edit Plan")
        self.ai_plan_button.clicked.connect(self.generate_ai_edit_plan)
        ai_layout.addWidget(self.ai_plan_button)

        self.ai_apply_button = QPushButton("Apply Edit")
        self.ai_apply_button.setEnabled(False)
        self.ai_apply_button.clicked.connect(self.apply_ai_edit)
        ai_layout.addWidget(self.ai_apply_button)

        self.ai_save_button = QPushButton("Save As...")
        self.ai_save_button.setEnabled(False)
        self.ai_save_button.clicked.connect(self.save_ai_result_as)
        ai_layout.addWidget(self.ai_save_button)

        self.ai_preview_button = QPushButton("Preview Result")
        self.ai_preview_button.setEnabled(False)
        self.ai_preview_button.clicked.connect(self.preview_ai_result)
        ai_layout.addWidget(self.ai_preview_button)

        self.ai_plan_output = QPlainTextEdit()
        self.ai_plan_output.setReadOnly(True)
        self.ai_plan_output.setPlaceholderText(
            "Your AI-generated plan will appear here."
        )
        ai_layout.addWidget(self.ai_plan_output, 1)

        self.ai_plan_data = None
        inspector_tabs.addTab(ai_page, "AI Editing")
        inspector_layout.addWidget(inspector_tabs, 1)
        workspace.addWidget(inspector)
        workspace.setSizes([52, 220, 790, 285, 245])

        timeline_panel = QFrame()
        timeline_panel.setObjectName("panel")
        timeline_layout = QVBoxLayout(timeline_panel)
        timeline_layout.setContentsMargins(9, 7, 9, 7)
        timeline_header = QHBoxLayout()
        timeline_header.addWidget(self._heading("TIMELINE"))
        timeline_header.addWidget(QLabel("V1  VIDEO  /  A1  AUDIO"))
        timeline_header.addStretch()
        timeline_header.addWidget(QLabel("Backspace: delete selected clip"))
        timeline_layout.addLayout(timeline_header)

        timeline_controls = QHBoxLayout()
        timeline_controls.addWidget(QLabel("00:00:00"))
        timeline_controls.addWidget(QLabel("Start"))
        timeline_controls.addWidget(QLabel("Playhead"))
        timeline_controls.addWidget(QLabel("Tracks"))
        timeline_controls.addStretch()
        timeline_controls.addWidget(QLabel("Separate video and audio tracks"))
        timeline_layout.addLayout(timeline_controls)

        self.timeline_widget = TimelineWidget(self._timeline_seek)
        timeline_layout.addWidget(self.timeline_widget)
        root.addWidget(timeline_panel, 3)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready - import a video to begin.")
    def add_text_overlay(self):
        """Create a text clip on T1; its visibility follows the timeline playhead."""
        text, ok = QInputDialog.getMultiLineText(self, "Text Tool", "Enter text:", "Your text here")
        if not ok or not text.strip():
            return
        color = QColorDialog.getColor(QColor("#ffffff"), self, "Choose text color")
        if not color.isValid():
            color = QColor("#ffffff")
        font_result = QFontDialog.getFont(QFont("Segoe UI", 32, QFont.Bold), self, "Choose text font")
        font = QFont("Segoe UI", 32, QFont.Bold)
        accepted = False
        if isinstance(font_result, tuple):
            for item in font_result:
                if isinstance(item, QFont):
                    font = item
                elif isinstance(item, bool):
                    accepted = item
        elif isinstance(font_result, QFont):
            font = font_result
            accepted = True
        if not accepted:
            font = QFont("Segoe UI", 32, QFont.Bold)

        timeline = self.timeline_widget
        start_ms = int(timeline.position_ms)
        end_ms = start_ms + 5000
        clip = {
            "name": "Text", "text": text, "start": start_ms, "end": end_ms,
            "color": color.name(), "font": font.toString(), "x": 0.5, "y": 0.5,
        }
        timeline.text_clips.append(clip)
        timeline.selected_track = "text"
        timeline.selected_clip = len(timeline.text_clips) - 1
        timeline.update()
        self._update_text_at_position(start_ms)
        self.statusBar().showMessage("Text added to T1 for 5 seconds. Drag the purple clip to change timing; drag text in the preview to reposition it.")

    def _display_video_frame(self, frame):
        image = frame.toImage()
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        self.video.setPixmap(pixmap.scaled(
            self.video.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        ))

    def _update_text_at_position(self, position_ms):
        if not hasattr(self, "text_overlay"):
            return
        timeline = self.timeline_widget
        clip = next((c for c in reversed(timeline.text_clips)
                     if c["start"] <= int(position_ms) < c["end"]), None)
        if clip is None:
            self.text_overlay.hide()
            return
        font = QFont()
        font.fromString(clip.get("font", QFont("Segoe UI", 32, QFont.Bold).toString()))
        self.text_overlay.setText(clip.get("text", "Text"))
        self.text_overlay.setFont(font)
        self.text_overlay.setStyleSheet(
            f"QLabel {{ color: {clip.get('color', '#ffffff')}; background: transparent; border: none; padding: 8px; }}"
        )
        self.text_overlay.adjustSize()
        self.text_overlay.show()
        self.text_overlay.raise_()
        max_x = max(0, self.video_page.width() - self.text_overlay.width())
        max_y = max(0, self.video_page.height() - self.text_overlay.height())
        self.text_overlay.move(int(clip.get("x", .5) * max_x), int(clip.get("y", .5) * max_y))

    def clear_text_overlay(self):
        timeline = self.timeline_widget
        idx = timeline.selected_clip if timeline.selected_track == "text" else None
        if idx is not None and 0 <= idx < len(timeline.text_clips):
            timeline.text_clips.pop(idx)
        elif timeline.text_clips:
            timeline.text_clips.pop()
        timeline.selected_clip = None
        timeline.update()
        self.text_overlay.clear()
        self.text_overlay.hide()
        self.statusBar().showMessage("Text clip removed from T1.")

    def generate_ai_edit_plan(self):
        request = self.ai_request_input.toPlainText().strip()
        if not request:
            QMessageBox.information(
                self, "AI Editing", "Enter an editing request first."
            )
            return

        self.ai_plan_button.setEnabled(False)
        self.ai_plan_output.setPlainText("Generating plan...")
        QApplication.processEvents()

        try:
            from nova_ai_editor import create_edit_plan
            plan = create_edit_plan(request)
            import json

            self.ai_plan_data = plan
            self.ai_apply_button.setEnabled(bool(plan.get("actions")))
            self.ai_plan_output.setPlainText(
                json.dumps(plan, indent=2, ensure_ascii=False)
            )
            self.statusBar().showMessage(
                "AI plan ready for review. No edits have been applied."
            )
        except Exception as exc:
            self.ai_plan_data = None
            self.ai_plan_output.setPlainText(
                f"Could not generate a plan:\n{exc}"
            )
        finally:
            self.ai_plan_button.setEnabled(True)
    def apply_ai_edit(self):
        """Run sequential AI edits off the GUI thread."""
        plan = getattr(self, "ai_plan_data", None)
        actions = plan.get("actions", []) if isinstance(plan, dict) else []

        if not isinstance(actions, list) or not actions:
            QMessageBox.information(
                self, "AI Editing",
                "Generate a plan with at least one edit action first."
            )
            return

        source = self.player.source().toLocalFile()
        if not source or not Path(source).is_file():
            QMessageBox.information(self, "AI Editing", "Import a video first.")
            return

        current_worker = getattr(self, "_ai_edit_worker", None)
        if current_worker is not None and current_worker.isRunning():
            return

        self.ai_apply_button.setEnabled(False)
        self.statusBar().showMessage("AI edit running in background...")
        self._ai_edit_worker = NovaAIEditWorker(
            plan,
            source,
            self.ai_request_input.toPlainText().strip().lower(),
            self
        )
        self._ai_edit_worker.progress.connect(
            self.statusBar().showMessage
        )
        self._ai_edit_worker.succeeded.connect(
            self._ai_edit_succeeded
        )
        self._ai_edit_worker.failed.connect(
            self._ai_edit_failed
        )
        self._ai_edit_worker.finished.connect(
            self._ai_edit_worker_finished
        )
        self._ai_edit_worker.start()

    def _ai_edit_succeeded(self, output_path, original_path, action_results):
        """Update the GUI only after background processing finishes."""
        self.ai_result_path = output_path
        self.ai_save_button.setEnabled(True)
        self.ai_preview_button.setEnabled(True)
        self.ai_plan_output.appendPlainText(
            "\\n\\nSequential edit results:\\n"
            + "\\n".join(action_results)
        )
        # NOVA_STAGE3F_AUTO_PREVIEW
        self.statusBar().showMessage(
            f"Loading AI result: {Path(output_path).name}"
        )
        self.load_video(output_path)
        self.statusBar().showMessage(
            f"AI result loaded: {Path(output_path).name}"
        )
        QMessageBox.information(
            self, "Edit Complete",
            f"All {len(action_results)} action(s) exported successfully.\\n\\n"
            f"Original: {original_path}\\n\\nFinal output: {output_path}"
        )

    def _ai_edit_failed(self, error):
        QMessageBox.warning(
            self, "AI Editing",
            f"Edit failed:\\n{error}\\n\\n"
            "Any completed intermediate exports have been left in Nova_Exports."
        )
        self.statusBar().showMessage("AI edit failed.")

    def _ai_edit_worker_finished(self):
        self.ai_apply_button.setEnabled(
            bool(getattr(self, "ai_plan_data", None)
                 and self.ai_plan_data.get("actions"))
        )
        worker = getattr(self, "_ai_edit_worker", None)
        if worker is not None:
            worker.deleteLater()
            self._ai_edit_worker = None

    def save_ai_result_as(self):
        """Copy the exported result to a user-chosen path without overwriting."""
        from shutil import copy2

        current = getattr(self, "ai_result_path", "")
        if not current or not Path(current).is_file():
            QMessageBox.information(self, "Save As", "Apply an edit first.")
            return

        source = Path(current).resolve()
        suggested = str(source.with_name(source.stem + "_saved" + source.suffix))
        destination, _ = QFileDialog.getSaveFileName(
            self, "Save Edited Video As", suggested,
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv);;All files (*)"
        )
        if not destination:
            return

        target = Path(destination).expanduser().resolve()
        if target == source:
            QMessageBox.warning(
                self, "Save As", "Choose a different filename from the export."
            )
            return
        if target.exists():
            answer = QMessageBox.question(
                self, "Replace Existing File?",
                f"{target.name} already exists. Replace it?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No
            )
            if answer != QMessageBox.Yes:
                return

        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            copy2(source, target)
            self.ai_result_path = str(target)
            self.ai_plan_output.appendPlainText(
                f"\nSaved copy to: {target}"
            )
            self.statusBar().showMessage(f"Saved edited video: {target}")
        except Exception as exc:
            QMessageBox.warning(self, "Save As", f"Could not save file:\n{exc}")

    def preview_ai_result(self):
        result = getattr(self, "ai_result_path", "")
        if result and Path(result).is_file():
            self.load_video(result)
        else:
            QMessageBox.information(
                self, "Preview Result", "Apply an edit first."
            )
    def _heading(self, text):
        label = QLabel(text)
        label.setObjectName("heading")
        return label

    def import_video(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Video", str(Path.home()),
            "Video files (*.mp4 *.mov *.mkv *.avi *.webm *.m4v *.wmv);;All files (*)"
        )
        if path:
            self.load_video(path)

    def load_video(self, path):
        file_path = Path(path)
        if not file_path.is_file():
            self.statusBar().showMessage("File not found.")
            return
        self._gap_timer.stop()
        self._gap_playing = False
        self._show_video_preview() if hasattr(self, "preview_stack") else None
        self.active_clip_index = None
        self.player.stop()
        self.player.setSource(QUrl.fromLocalFile(str(file_path.resolve())))
        self.media_list.addItem(str(file_path))
        self.media_list.setCurrentRow(self.media_list.count() - 1)
        self.timeline_widget.set_clip(file_path.name)
        self.timeline_widget.set_position(0)
        self.statusBar().showMessage(f"Loaded: {file_path.name}")

    def _open_selected(self, item):
        self.load_video(item.text())


    def toggle_play(self):
        if self.player.source().isEmpty():
            self.statusBar().showMessage("Import a video first.")
            return
        if self.player.playbackState() == QMediaPlayer.PlayingState or self._gap_playing:
            self.player.pause()
            self._gap_timer.stop()
            self._gap_playing = False
            return

        clips = sorted(self.timeline_widget.video_clips, key=lambda c: c["start"])
        if not clips:
            self.statusBar().showMessage("No video clips remain on the timeline.")
            return
        pos = self.timeline_widget.position_ms
        clip_index = next((i for i, c in enumerate(clips)
                           if c["start"] <= pos < c["end"]), None)
        if clip_index is None:
            next_item = next(((i, c) for i, c in enumerate(clips)
                              if c["start"] >= pos), None)
            if next_item is None:
                pos = 0
                next_item = (0, clips[0])
            clip_index, clip = next_item
            if pos < clip["start"]:
                self._start_gap(pos, clip["start"], clip_index)
                return
        clip = clips[clip_index]
        self._start_video_clip(clip_index, pos)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "text_overlay") and hasattr(self, "video_page"):
            self.text_overlay.setGeometry(self.video_page.rect())

    def _show_black_preview(self):
        """Display true black during empty timeline sections."""
        if hasattr(self, "text_overlay"):
            self.text_overlay.hide()
        if hasattr(self, "preview_stack") and hasattr(self, "black_overlay"):
            self.preview_stack.setCurrentWidget(self.black_overlay)

    def _show_video_preview(self):
        """Show the decoded video surface when positioned over a clip."""
        if hasattr(self, "preview_stack") and hasattr(self, "video"):
            self.preview_stack.setCurrentWidget(self.video_page)
        if hasattr(self, "text_overlay") and self.text_overlay.text().strip():
            self.text_overlay.setGeometry(self.video_page.rect())
            self.text_overlay.show()
            self.text_overlay.raise_()

    def _start_video_clip(self, index, timeline_position=None):
        clips = sorted(self.timeline_widget.video_clips, key=lambda c: c["start"])
        if not (0 <= index < len(clips)):
            self._finish_timeline()
            return
        clip = clips[index]
        timeline_position = clip["start"] if timeline_position is None else timeline_position
        source_pos = clip["source_in"] + max(0, timeline_position - clip["start"])
        self._gap_timer.stop()
        self._gap_playing = False
        self.active_clip_index = index
        self._show_video_preview()
        self.timeline_widget.set_position(timeline_position)
        self.player.setPosition(max(0, min(source_pos, clip["source_out"] - 1)))
        self.player.play()

    def _start_gap(self, start_ms, end_ms, next_index=None):
        self.player.pause()
        self.active_clip_index = None
        self._gap_playing = True
        self._gap_position_ms = int(start_ms)
        self._gap_target_ms = int(end_ms)
        self._gap_next_index = next_index
        self._show_black_preview()
        self.timeline_widget.set_position(start_ms)
        self._update_timeline_time(start_ms)
        self._gap_timer.start()

    def _advance_gap(self):
        if not self._gap_playing:
            self._gap_timer.stop()
            return
        self._gap_position_ms = min(self._gap_target_ms, self._gap_position_ms + self._gap_timer.interval())
        self.timeline_widget.set_position(self._gap_position_ms)
        self._sync_inspector_position(self._gap_position_ms)
        self._update_timeline_time(self._gap_position_ms)
        if self._gap_position_ms >= self._gap_target_ms:
            next_index = self._gap_next_index
            self._gap_timer.stop()
            self._gap_playing = False
            if next_index is not None:
                self._start_video_clip(next_index)
            else:
                self._finish_timeline()

    def _finish_timeline(self):
        self.player.pause()
        self._gap_timer.stop()
        self._gap_playing = False
        self.active_clip_index = None
        self._show_video_preview()
        self.timeline_widget.set_position(self.timeline_duration_ms)
        self._update_timeline_time(self.timeline_duration_ms)

    def eventFilter(self, watched, event):
        if watched is getattr(self, "text_overlay", None) and event.type() == event.Type.MouseMove:
            if event.buttons() & Qt.MouseButton.LeftButton:
                clip = next((c for c in reversed(self.timeline_widget.text_clips)
                             if c["start"] <= self.timeline_widget.position_ms < c["end"]), None)
                if clip:
                    pos = event.position().toPoint()
                    max_x = max(1, self.video_page.width() - self.text_overlay.width())
                    max_y = max(1, self.video_page.height() - self.text_overlay.height())
                    x = min(max_x, max(0, pos.x()))
                    y = min(max_y, max(0, pos.y()))
                    clip["x"], clip["y"] = x / max_x, y / max_y
                    self.text_overlay.move(x, y)
                return True
        if watched is self.video_page and event.type() == event.Type.Resize and hasattr(self, "timeline_widget"):
            self._update_text_at_position(self.timeline_widget.position_ms)
        return super().eventFilter(watched, event)

    def _playback_changed(self, state):
        self.play_button.setText(
            "Pause" if state == QMediaPlayer.PlayingState else "Play"
        )

    def _duration_changed(self, duration):
        self.duration_ms = max(0, int(duration))
        self.timeline_widget.set_duration(self.duration_ms)
        self._refresh_timeline_duration()
        self.seek_slider.setRange(0, self.timeline_duration_ms)
        self._update_timeline_time(self.timeline_widget.position_ms)

    def _refresh_timeline_duration(self):
        # Timeline length is based on the end of the remaining V1 clips.
        self.timeline_duration_ms = max(
            (int(c["end"]) for c in self.timeline_widget.video_clips),
            default=0,
        )
        self.seek_slider.setRange(0, self.timeline_duration_ms)
        self.timeline_widget.update()

    def _update_timeline_time(self, position):
        def stamp(ms):
            seconds = max(0, int(ms / 1000))
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.time_label.setText(
            f"{stamp(position)} / {stamp(self.timeline_duration_ms)}"
        )


    def _position_changed(self, position):
        self._update_text_at_position(self.timeline_widget.position_ms)
        if self._gap_playing:
            return
        clips = sorted(self.timeline_widget.video_clips, key=lambda c: c["start"])
        if self.active_clip_index is not None and clips:
            index = min(self.active_clip_index, len(clips) - 1)
            clip = clips[index]
            if position >= clip["source_out"] - 40:
                next_index = index + 1
                timeline_end = clip["end"]
                if next_index < len(clips):
                    next_clip = clips[next_index]
                    if next_clip["start"] > timeline_end:
                        self._start_gap(timeline_end, next_clip["start"], next_index)
                    else:
                        self._start_video_clip(next_index)
                else:
                    if timeline_end < self.timeline_duration_ms:
                        self._start_gap(timeline_end, self.timeline_duration_ms, None)
                    else:
                        self._finish_timeline()
                return
            timeline_pos = clip["start"] + (position - clip["source_in"])
        else:
            timeline_pos = self.timeline_widget.position_ms
        if not self.is_seeking:
            self.seek_slider.setValue(max(0, min(timeline_pos, self.timeline_duration_ms)))
        self.timeline_widget.set_position(max(0, timeline_pos))
        self._update_text_at_position(timeline_pos)
        self._sync_inspector_position(timeline_pos)
        self._update_timeline_time(timeline_pos)

    def _update_time(self, position):
        self._update_timeline_time(position)

    def _begin_seek(self):
        self.is_seeking = True

    def _seek_preview(self, position):
        if self.is_seeking:
            self._update_time(position)

    def _finish_seek(self):
        self.is_seeking = False
        self._timeline_seek(self.seek_slider.value())


    def _timeline_seek(self, position):
        position = max(0, int(position))
        self.timeline_widget.set_position(position)
        self._update_text_at_position(position)
        clips = sorted(self.timeline_widget.video_clips, key=lambda c: c["start"])
        self._gap_timer.stop()
        self._gap_playing = False
        self._gap_next_index = None
        clip_index = next((i for i, clip in enumerate(clips)
                           if clip["start"] <= position < clip["end"]), None)
        if clip_index is not None:
            self._start_video_clip(clip_index, position)
            return
        next_item = next(((i, clip) for i, clip in enumerate(clips)
                          if clip["start"] > position), None)
        if next_item:
            index, clip = next_item
            self._start_gap(position, clip["start"], index)
        else:
            self.player.pause()
            self.active_clip_index = None
            self._show_black_preview() if position < self.timeline_duration_ms else self._show_video_preview()
            self.timeline_widget.set_position(position)
            self._sync_inspector_position(position)
            self._update_timeline_time(position)

    def _apply_volume(self, value):
        self.audio.setVolume(max(0.0, min(2.0, value / 100.0)))
        if hasattr(self, "volume_value_label"):
            self.volume_value_label.setText(f"{value}%")

    def _reset_audio(self):
        self.volume_slider.setValue(100)
        self.mute_checkbox.setChecked(False)
        self.audio.setVolume(1.0)
        self.audio.setMuted(False)

    def _apply_speed(self, index):
        speed = self.speed_combo.itemData(index)
        if speed is not None:
            self.player.setPlaybackRate(float(speed))
            self.statusBar().showMessage(f"Playback speed: {speed:g}x")

    def _inspector_seek(self, seconds):
        if getattr(self, "_syncing_inspector", False):
            return
        self._timeline_seek(int(seconds * 1000))

    def _sync_inspector_position(self, position):
        if hasattr(self, "position_spin"):
            self._syncing_inspector = True
            self.position_spin.blockSignals(True)
            self.position_spin.setValue(max(0, position) / 1000.0)
            self.position_spin.blockSignals(False)
            self._syncing_inspector = False
        if hasattr(self, "clip_info_label"):
            track = self.timeline_widget.selected_track
            clips = self.timeline_widget.current_clips()
            idx = self.timeline_widget.selected_clip
            if idx is not None and 0 <= idx < len(clips):
                clip = clips[idx]
                self.clip_info_label.setText(
                    f"Track: {track.upper()}\nClip: {clip['name']}\n"
                    f"Timeline: {TimelineWidget._stamp(clip['start'])} - {TimelineWidget._stamp(clip['end'])}\n"
                    f"Length: {(clip['end'] - clip['start']) / 1000:.2f} s"
                )
            else:
                self.clip_info_label.setText("Select a clip on V1 or A1 to view its timing.")

    def add_gap_at_playhead(self):
        """Insert a one-second blank interval by shifting later video clips."""
        position = int(self.timeline_widget.position_ms)
        clips = self.timeline_widget.video_clips
        if not clips:
            self.statusBar().showMessage("Import a video and select a timeline position first.")
            return
        # Shift clips beginning at/after the playhead; split a clip if playhead is inside it.
        containing = next((i for i, c in enumerate(clips)
                           if c["start"] < position < c["end"]), None)
        if containing is not None:
            if not self.timeline_widget.add_split(position):
                self.statusBar().showMessage("Could not split clip at this position.")
                return
        for clip in clips:
            if clip["start"] >= position:
                clip["start"] += 1000
                clip["end"] += 1000
        self._refresh_timeline_duration()
        self.timeline_widget.update()
        self._show_black_preview()
        self.statusBar().showMessage("Inserted a 1-second gap. Playback will show black in this interval.")

    def split_at_playhead(self):
        if self.player.source().isEmpty() or self.duration_ms <= 0:
            self.statusBar().showMessage("Import a video before splitting.")
            return
        position = self.timeline_widget.position_ms
        if self.timeline_widget.add_split(position):
            self.active_clip_index = self.timeline_widget.selected_clip
            self._refresh_timeline_duration()
            self.statusBar().showMessage(
                f"Clip split at timeline time {TimelineWidget._stamp(position)}."
            )
        else:
            self.statusBar().showMessage(
                "Place the playhead inside a clip before splitting."
            )


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
            self._gap_timer.stop()
            self._gap_playing = False
            self._show_video_preview()
            self._refresh_timeline_duration()
            self.seek_slider.setValue(min(self.timeline_widget.position_ms, self.timeline_duration_ms))
            self._update_timeline_time(min(self.timeline_widget.position_ms, self.timeline_duration_ms))
        self.statusBar().showMessage(
            f"Deleted selected {self.timeline_widget.selected_track.upper()} clip only."
        )

    def _playback_error(self, error, message):
        if error != QMediaPlayer.NoError:
            self.statusBar().showMessage(f"Playback error: {message}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = NovaStudioQt()
    window.show()
    sys.exit(app.exec())





