from pathlib import Path
import shutil
import py_compile

p = Path("nova_studio_qt.py")
s = p.read_text(encoding="utf-8")

backup = Path("nova_studio_qt_before_trim_duration_fix.py")
if not backup.exists():
    shutil.copy2(p, backup)

old = '''            if action == "trim":
                start = float(params["start_seconds"])
                duration = float(params["duration_seconds"])
                if start < 0 or duration <= 0:
                    raise ValueError("Trim start must be >= 0 and duration > 0.")
                result = editor.trim_video(source, start, duration)
'''

new = '''            if action == "trim":
                import re

                # Infer a simple opening trim directly from the user's request.
                request_text = self.ai_request_input.toPlainText().strip().lower()
                opening_trim = re.search(
                    r"(?:trim|cut|remove|delete)\\\\s+(?:the\\\\s+)?(?:first|initial)\\\\s+(\\\\d+(?:\\\\.\\\\d+)?)\\\\s*(seconds?|secs?|s)\\\\b",
                    request_text
                )
                if not opening_trim:
                    opening_trim = re.search(
                        r"(?:trim|cut|remove|delete)\\\\s+(?:the\\\\s+)?(?:opening|beginning)\\\\s+(\\\\d+(?:\\\\.\\\\d+)?)\\\\s*(seconds?|secs?|s)\\\\b",
                        request_text
                    )

                if opening_trim:
                    start = float(opening_trim.group(1))
                    metadata = editor.probe_video(source)
                    total_duration = float(metadata.get("format", {}).get("duration", 0))
                    if total_duration <= start:
                        raise ValueError(
                            f"The video duration ({total_duration:.2f}s) must exceed the trim start ({start:.2f}s)."
                        )
                    duration = total_duration - start
                else:
                    start = float(params["start_seconds"])
                    duration = float(params["duration_seconds"])

                if start < 0 or duration <= 0:
                    raise ValueError("Trim start must be >= 0 and duration > 0.")
                result = editor.trim_video(source, start, duration)
'''

if old not in s:
    raise SystemExit("PATCH STOPPED: expected trim handler not found. No changes made.")

p.write_text(s.replace(old, new, 1), encoding="utf-8")
py_compile.compile(str(p), doraise=True)
print("SUCCESS: opening-trim duration fix applied; syntax check passed.")
print("Backup:", backup)
