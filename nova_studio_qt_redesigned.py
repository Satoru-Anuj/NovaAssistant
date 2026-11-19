import sys
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QAction, QPainter, QColor, QPen, QFont
from PySide6.QtWidgets import QSizePolicy
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QFrame, QLabel, QPushButton,
    QListWidget, QFileDialog, QVBoxLayout, QHBoxLayout, QSplitter,
    QSlider, QStatusBar, QToolBar
)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtMultimediaWidgets import QVideoWidget




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

class NovaStudioQt(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Nova Studio")
        self.resize(1440, 900)
        self.setMinimumSize(1000, 650)

        self.duration_ms = 0
        self.is_seeking = False
        self.active_clip_index = None

        self.player = QMediaPlayer(self)
        self.audio = QAudioOutput(self)
        self.player.setAudioOutput(self.audio)

        self._build_ui()
        self.player.setVideoOutput(self.video)
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
                background: #17191e; color: #e6e8ed;
                font-family: Segoe UI; font-size: 9pt;
            }
            QMenuBar { background: #20232a; color: #e6e8ed; padding: 4px; }
            QMenuBar::item:selected, QMenu::item:selected { background: #147dba; }
            QMenu { background: #20232a; border: 1px solid #3a414d; }
            QFrame#panel { background: #20232a; border: 1px solid #30343e; }
            QLabel#heading { color: #aeb8ca; font-weight: 700; letter-spacing: 1px; }
            QLabel#muted { color: #8994a7; }
            QPushButton {
                background: #303642; border: 1px solid #454c5b;
                padding: 6px 10px; border-radius: 4px;
            }
            QPushButton:hover { background: #3b4555; }
            QPushButton#primary { background: #147dba; border-color: #2998d5; }
            QPushButton#tool { min-width: 34px; min-height: 30px; padding: 4px; }
            QListWidget, QTabWidget::pane {
                background: #171a20; border: 1px solid #30343e;
                padding: 4px; outline: none;
            }
            QTabBar::tab { background: #252a33; padding: 7px 12px; border: 1px solid #30343e; }
            QTabBar::tab:selected { background: #147dba; }
            QSlider::groove:horizontal { height: 5px; background: #424957; }
            QSlider::handle:horizontal {
                background: #27a8f2; width: 12px; margin: -5px 0;
                border-radius: 6px;
            }
            QStatusBar { background: #111318; color: #aeb8ca; }
            QToolBar { background: #20232a; border: none; spacing: 6px; padding: 5px; }
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
            ("＋ Import", self.import_video),
            ("▶  Play / Pause", self.toggle_play),
            ("✂  Split", self.split_at_playhead),
            ("⌫  Delete", self.delete_selected_clip),
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
            ("↖", "Select"), ("✂", "Split at playhead"),
            ("◫", "Timeline clips"), ("T", "Text tools"),
            ("♪", "Audio tools"), ("✦", "AI tools"),
        ]:
            button = QPushButton(symbol)
            button.setObjectName("tool")
            button.setToolTip(tooltip)
            if tooltip == "Split at playhead":
                button.clicked.connect(self.split_at_playhead)
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
        preview_header.addWidget(QLabel("FIT  ▾"))
        preview_layout.addLayout(preview_header)

        self.video = QVideoWidget()
        self.video.setMinimumSize(360, 240)
        self.video.setStyleSheet("background: #08090c; border: 1px solid #30343e;")
        preview_layout.addWidget(self.video, 1)

        controls = QHBoxLayout()
        self.play_button = QPushButton("▶  Play")
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
        for tab_name, lines in [
            ("Properties", ["Clip properties", "Position", "Scale", "Opacity", "Speed"]),
            ("Audio", ["Volume", "Fade in / out", "Audio balance"]),
            ("Effects", ["Color correction", "Blur / sharpen", "Transitions"]),
        ]:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(8, 10, 8, 8)
            for line in lines:
                label = QLabel(line)
                label.setStyleSheet("padding: 7px; color: #b8c1d0; background: #252a33; border-radius: 3px;")
                page_layout.addWidget(label)
            page_layout.addStretch()
            inspector_tabs.addTab(page, tab_name)
        inspector_layout.addWidget(inspector_tabs, 1)
        ai_note = QLabel("AI EDITOR\nTools can be connected here as they are implemented.")
        ai_note.setWordWrap(True)
        ai_note.setStyleSheet("color: #8f9bad; padding: 8px;")
        inspector_layout.addWidget(ai_note)
        workspace.addWidget(inspector)
        workspace.setSizes([48, 210, 720, 275, 280])

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
        timeline_controls.addWidget(QLabel("◀"))
        timeline_controls.addWidget(QLabel("▶"))
        timeline_controls.addWidget(QLabel("▶▶"))
        timeline_controls.addStretch()
        timeline_controls.addWidget(QLabel("Separate video and audio tracks"))
        timeline_layout.addLayout(timeline_controls)

        self.timeline_widget = TimelineWidget(self._timeline_seek)
        timeline_layout.addWidget(self.timeline_widget)
        root.addWidget(timeline_panel, 3)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("Ready - import a video to begin.")
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
        if self.player.playbackState() == QMediaPlayer.PlayingState:
            self.player.pause()
            return

        clips = sorted(self.timeline_widget.clips, key=lambda c: c["start"])
        if not clips:
            self.statusBar().showMessage("No clips remain on the timeline.")
            return

        pos = self.timeline_widget.position_ms
        chosen = next((i for i, c in enumerate(clips)
                       if c["start"] <= pos < c["end"]), None)
        if chosen is None:
            chosen = next((i for i, c in enumerate(clips)
                           if c["start"] >= pos), 0)
            pos = clips[chosen]["start"]

        self.active_clip_index = chosen
        clip = clips[chosen]
        source_pos = clip["source_in"] + max(0, pos - clip["start"])
        self.player.setPosition(min(source_pos, clip["source_out"] - 1))
        self.player.play()
    def _playback_changed(self, state):
        self.play_button.setText(
            "Pause" if state == QMediaPlayer.PlayingState else "Play"
        )

    def _duration_changed(self, duration):
        self.duration_ms = max(0, duration)
        self.seek_slider.setRange(0, self.duration_ms)
        self.timeline_widget.set_duration(self.duration_ms)
        self._update_time(self.player.position())


    def _position_changed(self, position):
        clips = sorted(self.timeline_widget.clips, key=lambda c: c["start"])

        if self.active_clip_index is not None and clips:
            index = min(self.active_clip_index, len(clips) - 1)
            clip = clips[index]

            # Jump over the end of the current source segment.
            if position >= clip["source_out"] - 40:
                next_index = index + 1
                if next_index < len(clips):
                    next_clip = clips[next_index]
                    self.active_clip_index = next_index
                    self.player.setPosition(next_clip["source_in"])
                    self.timeline_widget.set_position(next_clip["start"])
                    return
                self.player.pause()
                self.active_clip_index = None
                self.timeline_widget.set_position(clip["end"])
                return

            timeline_pos = clip["start"] + (position - clip["source_in"])
        else:
            timeline_pos = position

        if not self.is_seeking:
            self.seek_slider.setValue(max(0, min(position, self.duration_ms)))
        self.timeline_widget.set_position(max(0, timeline_pos))
        self._update_time(position)
    def _update_time(self, position):
        def stamp(ms):
            seconds = max(0, int(ms / 1000))
            hours, remainder = divmod(seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        self.time_label.setText(
            f"{stamp(position)} / {stamp(self.duration_ms)}"
        )

    def _begin_seek(self):
        self.is_seeking = True

    def _seek_preview(self, position):
        if self.is_seeking:
            self._update_time(position)

    def _finish_seek(self):
        self.player.setPosition(self.seek_slider.value())
        self.is_seeking = False


    def _timeline_seek(self, position):
        clips = sorted(self.timeline_widget.clips, key=lambda c: c["start"])
        position = max(0, int(position))
        for i, clip in enumerate(clips):
            if clip["start"] <= position < clip["end"]:
                self.active_clip_index = i
                source_pos = clip["source_in"] + position - clip["start"]
                self.player.setPosition(max(0, min(source_pos, clip["source_out"] - 1)))
                return
        # If the playhead is in a gap, seek to the next clip.
        next_item = next(( (i, c) for i, c in enumerate(clips)
                           if c["start"] >= position), None)
        if next_item:
            i, clip = next_item
            self.active_clip_index = i
            self.player.setPosition(clip["source_in"])
            self.timeline_widget.set_position(clip["start"])
        else:
            self.player.pause()
            self.active_clip_index = None
            self.timeline_widget.set_position(position)

    def split_at_playhead(self):
        if self.player.source().isEmpty() or self.duration_ms <= 0:
            self.statusBar().showMessage("Import a video before splitting.")
            return
        position = self.player.position()
        if self.timeline_widget.add_split(position):
            self.active_clip_index = self.timeline_widget.selected_clip
            self.statusBar().showMessage(
                f"Clip split at source time {TimelineWidget._stamp(position)}."
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
