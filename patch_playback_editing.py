from pathlib import Path
from datetime import datetime
import shutil, py_compile, sys

p = Path("nova_studio_qt.py")
s = p.read_text(encoding="utf-8")

required = [
    "    def toggle_play(self):",
    "    def _position_changed(self, position):",
    "    def _timeline_seek(self, position):",
    "    def split_at_playhead(self):",
]
if not all(x in s for x in required):
    sys.exit("ERROR: Expected methods not found. No changes made.")

backup_dir = Path("studio_rebuild_backups")
backup_dir.mkdir(exist_ok=True)
backup = backup_dir / f"before_playback_editing_{datetime.now():%Y%m%d_%H%M%S}.py"
shutil.copy2(p, backup)

def replace_method(text, method_name, replacement):
    start = text.find(f"    def {method_name}(")
    if start < 0:
        raise RuntimeError(f"Could not find {method_name}")
    next_method = text.find("\n    def ", start + 5)
    if next_method < 0:
        next_method = text.find("\n\nif __name__")
    if next_method < 0:
        raise RuntimeError(f"Could not find end of {method_name}")
    return text[:start] + replacement.rstrip() + "\n" + text[next_method+1:]

# Add delete button to toolbar.
old = '            ("Split at Playhead", self.split_at_playhead),'
new = old + '\n            ("Delete Selected Clip", self.delete_selected_clip),'
if old not in s:
    sys.exit("ERROR: Toolbar entry not found. Original file unchanged.")
s = s.replace(old, new, 1)

# Track which source segment is currently being played.
needle = "        self.is_seeking = False"
if needle not in s:
    sys.exit("ERROR: Could not find player state initialization.")
s = s.replace(needle, needle + "\n        self.active_clip_index = None", 1)

s = replace_method(s, "toggle_play", '''
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
''')

s = replace_method(s, "_position_changed", '''
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
''')

s = replace_method(s, "_timeline_seek", '''
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
''')

s = replace_method(s, "split_at_playhead", '''
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
        index = self.timeline_widget.selected_clip
        if index is None or not (0 <= index < len(self.timeline_widget.clips)):
            self.statusBar().showMessage("Select a clip on the timeline first.")
            return
        removed = self.timeline_widget.clips.pop(index)
        if self.timeline_widget.clips:
            self.timeline_widget.selected_clip = min(index, len(self.timeline_widget.clips) - 1)
        else:
            self.timeline_widget.selected_clip = None
        self.active_clip_index = None
        self.timeline_widget.update()
        self.player.pause()
        self.statusBar().showMessage(
            f"Deleted timeline clip. Source file unchanged; "
            f"{len(self.timeline_widget.clips)} clip(s) remain."
        )
''')

tmp = p.with_suffix(".tmp.py")
tmp.write_text(s, encoding="utf-8")
try:
    py_compile.compile(str(tmp), doraise=True)
except Exception as e:
    tmp.unlink(missing_ok=True)
    print("SYNTAX ERROR — original file preserved:", e)
    sys.exit(1)

shutil.move(str(tmp), str(p))
print("Patch applied. Syntax check passed.")
print("Backup:", backup)
