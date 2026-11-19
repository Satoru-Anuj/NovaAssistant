@'
from pathlib import Path
import re

p = Path("nova_studio.py")
s = p.read_text(encoding="utf-8-sig")
pattern = r"(?s)    def play_preview\(self\):.*?(?=    def submit_command\(self\):)"

if not re.search(pattern, s):
    raise SystemExit("Could not find play_preview(); file unchanged.")

print("Found play_preview(). No changes made yet.")
'@ | Set-Content .\check_preview.py -Encoding utf8
.\.venv\Scripts\python.exe .\check_preview.py