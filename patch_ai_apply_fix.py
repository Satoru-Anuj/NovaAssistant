from pathlib import Path
import re
import shutil
import py_compile

file = Path("nova_studio_qt.py")
source = file.read_text(encoding="utf-8")

start = source.find("    def apply_ai_edit(self):")
end = source.find("    def save_ai_result_as(self):", start)

if start < 0 or end < 0:
    raise SystemExit("PATCH STOPPED: Could not find both method boundaries. No changes made.")

backup = file.with_name("nova_studio_qt_before_apply_fix.py")
shutil.copy2(file, backup)

replacement = '''    def apply_ai_edit(self):
        """Run one validated AI action and reliably locate its exported result."""
        if not self.ai_plan_data or len(self.ai_plan_data.get("actions", [])) != 1:
            QMessageBox.information(
                self, "AI Editing",
                "Generate a plan containing exactly one edit action first."
            )
            return

        source = self.player.source().toLocalFile()
        if not source or not Path(source).is_file():
            QMessageBox.information(self, "AI Editing", "Import a video first.")
            return

        action_item = self.ai_plan_data["actions"][0]
        action = action_item.get("action")
        params = action_item.get("parameters", {})
        if not isinstance(params, dict):
            QMessageBox.warning(self, "AI Editing", "Invalid action parameters.")
            return

        try:
            import nova_video_editor as editor

            export_dir = Path(getattr(editor, "EXPORT_DIR", Path(__file__).resolve().parent / "Nova_Exports"))
            export_dir.mkdir(parents=True, exist_ok=True)

            # Record existing exports so we can identify the file created by this edit.
            before = {
                str(p.resolve())
                for p in export_dir.iterdir()
                if p.is_file()
            }

            if action == "trim":
                start = float(params["start_seconds"])
                duration = float(params["duration_seconds"])
                if start < 0 or duration <= 0:
                    raise ValueError("Trim start must be >= 0 and duration > 0.")
                result = editor.trim_video(source, start, duration)
            elif action == "change_speed":
                speed = float(params["speed"])
                if not 0.25 <= speed <= 4.0:
                    raise ValueError("Speed must be between 0.25x and 4x.")
                result = editor.change_speed(source, speed)
            elif action == "resize":
                width, height = int(params["width"]), int(params["height"])
                if not (2 <= width <= 7680 and 2 <= height <= 4320):
                    raise ValueError("Resize dimensions are outside supported limits.")
                result = editor.resize_video(source, width, height)
            elif action == "brightness":
                brightness = float(params["brightness"])
                if not -1.0 <= brightness <= 1.0:
                    raise ValueError("Brightness must be between -1 and 1.")
                result = editor.adjust_brightness(source, brightness)
            elif action == "volume":
                volume = float(params["volume"])
                if not 0.0 <= volume <= 5.0:
                    raise ValueError("Volume must be between 0x and 5x.")
                result = editor.adjust_volume(source, volume)
            elif action == "convert_mp4":
                result = editor.convert_to_mp4(source)
            elif action == "extract_audio":
                result = editor.extract_audio(source)
            else:
                raise ValueError("This edit action is not supported.")

            # Prefer a newly created file rather than relying on message wording.
            candidates = [
                p for p in export_dir.iterdir()
                if p.is_file() and str(p.resolve()) not in before and p.stat().st_size > 0
            ]

            output = max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None

            # Fallback for engines that export outside Nova_Exports.
            if output is None and isinstance(result, str):
                match = re.search(
                    r"(?:saved to|output(?: file)?(?: saved)?(?: to)?):?\\\\s*[\\\\"']?(.+?)[\\\\"']?\\\\s*$",
                    result,
                    re.IGNORECASE
                )
                if match:
                    possible = Path(match.group(1).strip().strip('"')).expanduser()
                    if possible.is_file():
                        output = possible

            if output is None or not output.is_file():
                raise RuntimeError(
                    "The edit action returned, but Nova could not identify a newly exported file. "
                    "Check the terminal output and Nova_Exports folder."
                )

            self.ai_result_path = str(output.resolve())
            self.ai_save_button.setEnabled(True)
            self.ai_preview_button.setEnabled(True)
            self.ai_plan_output.appendPlainText(
                "\\\\n\\\\n" + (str(result) if result else "Edit exported successfully.")
                + "\\\\nOutput: " + self.ai_result_path
            )
            QMessageBox.information(
                self, "Edit Complete",
                "Edit exported successfully.\\\\n\\\\n" + self.ai_result_path
            )

        except Exception as exc:
            QMessageBox.warning(self, "AI Editing", f"Edit failed:\\\\n{exc}")

'''

file.write_text(source[:start] + replacement + source[end:], encoding="utf-8")
py_compile.compile(str(file), doraise=True)
print("PATCH SUCCESSFUL: apply_ai_edit updated and Python syntax is valid.")
print(f"Backup: {backup}")
