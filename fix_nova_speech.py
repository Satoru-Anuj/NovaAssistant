from pathlib import Path
import ast
import py_compile
import re
import shutil
import time

path = Path("main.py")
source = path.read_text(encoding="utf-8")

if "def clean_for_speech(self, message):" in source:
    raise SystemExit(
        "A speech-cleaning method already exists. No changes made."
    )

tree = ast.parse(source)
speak_method = next(
    (n for n in ast.walk(tree)
     if isinstance(n, ast.FunctionDef) and n.name == "speak"),
    None
)

if speak_method is None:
    raise SystemExit("STOP: speak() not found. No changes made.")

if "engine.say(message)" not in source:
    raise SystemExit("STOP: Expected engine.say(message) not found.")

cleaner = '''    def clean_for_speech(self, message):
        """Remove Markdown formatting before text-to-speech playback."""
        text = str(message)

        # Do not read code blocks aloud.
        text = re.sub(
            r"```[\\\\s\\\\S]*?```",
            " The code is shown on screen. ",
            text
        )

        # Speak link labels, not Markdown or raw URLs.
        text = re.sub(
            r"!\\\\[([^\\\\]]*)\\\\]\\\\([^)]+\\\\)",
            r"\\\\1",
            text
        )
        text = re.sub(
            r"\\\\[([^\\\\]]+)\\\\]\\\\([^)]+\\\\)",
            r"\\\\1",
            text
        )
        text = re.sub(r"https?://\\\\S+", "", text)

        # Keep inline code words, but remove the backticks.
        text = re.sub(r"`([^`]*)`", r"\\\\1", text)

        # Remove Markdown headings, quotes, and list markers.
        text = re.sub(r"(?m)^\\\\s{0,3}#{1,6}\\\\s*", "", text)
        text = re.sub(r"(?m)^\\\\s*>\\\\s?", "", text)
        text = re.sub(r"(?m)^\\\\s*[-*+]\\\\s+", "", text)
        text = re.sub(r"(?m)^\\\\s*\\\\d+[.)]\\\\s+", "", text)

        # Remove bold, italic, strike-through and remaining markers.
        text = re.sub(r"[*_~#]+", "", text)
        text = re.sub(r"<[^>]+>", "", text)

        # Make spacing and punctuation more natural for speech.
        text = re.sub(r"\\\\s+", " ", text)
        text = re.sub(r"\\\\s+([,.!?;:])", r"\\\\1", text)
        return text.strip()

'''

updated = source.replace(
    "    def speak(self, message):",
    cleaner + "    def speak(self, message):",
    1
)
updated = updated.replace(
    "engine.say(message)",
    "engine.say(self.clean_for_speech(message))",
    1
)

# Verify the modified file before replacing the original.
check = Path("_main_speech_check.py")
check.write_text(updated, encoding="utf-8")
try:
    py_compile.compile(str(check), doraise=True)
finally:
    check.unlink(missing_ok=True)

backup = Path(
    "main_before_speech_cleanup_" +
    time.strftime("%Y%m%d_%H%M%S") + ".py"
)
shutil.copy2(path, backup)
path.write_text(updated, encoding="utf-8")

print("SUCCESS: Nova speech Markdown cleanup installed.")
print("AI response display and voice settings preserved.")
print("Backup created:", backup)
print("Syntax check passed.")
