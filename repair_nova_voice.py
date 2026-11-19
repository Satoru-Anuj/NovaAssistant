import ast
import re
import shutil
from pathlib import Path

base = Path(__file__).resolve().parent
main_file = base / "main.py"
widget_file = base / "nova_widget.py"
backup_file = base / "main_before_wakeword_fix2.py"

if not main_file.exists() or not widget_file.exists() or not backup_file.exists():
    raise SystemExit("Repair stopped: a required project file is missing.")

# Preserve another copy immediately before editing.
shutil.copy2(main_file, base / "main_pre_repair.py")
shutil.copy2(widget_file, base / "nova_widget_pre_repair.py")

current = main_file.read_text(encoding="utf-8-sig")
backup = backup_file.read_text(encoding="utf-8-sig")

def get_methods(source):
    tree = ast.parse(source)
    cls = next(n for n in tree.body
               if isinstance(n, ast.ClassDef) and n.name == "NovaOrb")
    lines = source.splitlines(keepends=True)
    return {
        n.name: "".join(lines[n.lineno - 1:n.end_lineno])
        for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

old_methods = get_methods(current)
original_methods = get_methods(backup)

# Restore only the proven original voice/command methods.
required = [
    "extract_wake_command", "listen_loop", "wake_response",
    "memory_context", "handle_memory_command", "open_desktop_app",
    "handle_command", "speak"
]
missing = [name for name in required if name not in original_methods]
if missing:
    raise SystemExit("Repair stopped: backup lacks methods: " + ", ".join(missing))

restored = {name: original_methods[name] for name in required}

# Let voice recognition work even when the AI API key is absent.
restored["listen_loop"] = re.sub(
    r'        if not API_KEY:\r?\n'
    r'            print\("GROQ_API_KEY is missing from \.env"\)\r?\n'
    r'            return\r?\n\r?\n',
    '',
    restored["listen_loop"],
    count=1
)

# Keep the listener alive while the microphone is toggled off and on.
restored["listen_loop"] = restored["listen_loop"].replace(
    "while self.listening and not self.closing:\n"
    "                    if self.busy:",
    "while not self.closing:\n"
    "                    if not self.listening:\n"
    "                        time.sleep(0.15)\n"
    "                        continue\n"
    "                    if self.busy:"
)
restored["listen_loop"] = restored["listen_loop"].replace(
    "while self.listening and not self.closing:\r\n"
    "                    if self.busy:",
    "while not self.closing:\r\n"
    "                    if not self.listening:\r\n"
    "                        time.sleep(0.15)\r\n"
    "                        continue\r\n"
    "                    if self.busy:"
)

# Preserve legacy saved memories and conversation history in one file.
custom_memory = '''    def load_memory(self):
        self.memories = []
        try:
            if not MEMORY_FILE.exists():
                return
            data = json.loads(MEMORY_FILE.read_text(encoding="utf-8"))
            if isinstance(data, list):
                # Legacy format: a list of saved facts.
                self.memories = [
                    item for item in data if isinstance(item, str)
                ]
            elif isinstance(data, dict):
                saved_memories = data.get("memories", [])
                if isinstance(saved_memories, list):
                    self.memories = [
                        item for item in saved_memories
                        if isinstance(item, str)
                    ]
                saved_history = data.get("history", [])
                if isinstance(saved_history, list):
                    self.history.extend([
                        item for item in saved_history[-24:]
                        if isinstance(item, dict)
                        and item.get("role") in ("user", "assistant")
                        and isinstance(item.get("content"), str)
                    ])
        except (OSError, ValueError, TypeError) as error:
            print("Memory load warning:", error)

    def save_memory(self):
        self.save_memories()

    def save_memories(self):
        try:
            turns = [
                item for item in self.history
                if item.get("role") in ("user", "assistant")
            ][-24:]
            data = {
                "memories": self.memories,
                "history": turns
            }
            temp = MEMORY_FILE.with_suffix(".tmp")
            temp.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
            temp.replace(MEMORY_FILE)
        except (OSError, ValueError, TypeError) as error:
            print("Memory save warning:", error)
'''

custom_control = '''    def poll_control_file(self):
        if self.closing:
            return
        control_file = BASE_DIR / "nova_ui_control.txt"
        try:
            if control_file.exists():
                command = control_file.read_text(encoding="utf-8").strip()
                control_file.unlink(missing_ok=True)
                if command == "mic_toggle":
                    self.listening = not self.listening
                    print("Microphone listening:", "ON" if self.listening else "OFF")
                    self.set_status("listening" if self.listening else "idle")
                elif command == "audio_toggle":
                    self.audio_enabled = not self.audio_enabled
                    print("Voice output:", "ON" if self.audio_enabled else "MUTED")
        except OSError as error:
            print("Control-file warning:", error)
        finally:
            if not self.closing:
                self.root.after(150, self.poll_control_file)
'''

# Make speech output respect the audio toggle.
restored["speak"] = restored["speak"].replace(
    "    def speak(self, message):\n        try:\n",
    "    def speak(self, message):\n        try:\n"
    "            if not self.audio_enabled:\n"
    "                print('Voice output is muted.')\n"
    "                return\n"
)

# Replace existing methods using AST line ranges, from bottom to top.
replacements = {
    "load_memory": custom_memory.split("    def save_memory(self):")[0].rstrip() + "\n",
    "save_memory": (
        "    def save_memory(self):\n"
        "        self.save_memories()\n"
    ),
    "handle_command": restored["handle_command"],
    "speak": restored["speak"],
}
tree = ast.parse(current)
cls = next(n for n in tree.body
           if isinstance(n, ast.ClassDef) and n.name == "NovaOrb")
lines = current.splitlines(keepends=True)
edits = []
for node in cls.body:
    if isinstance(node, ast.FunctionDef) and node.name in replacements:
        edits.append((node.lineno - 1, node.end_lineno, replacements[node.name]))
for start, end, replacement in sorted(edits, reverse=True):
    lines[start:end] = [replacement]
current = "".join(lines)

# Add the restored methods and control poller if not already present.
methods_to_add = [
    restored["extract_wake_command"],
    restored["listen_loop"],
    restored["wake_response"],
    restored["memory_context"],
    restored["handle_memory_command"],
    restored["open_desktop_app"],
    custom_memory.split("    def load_memory(self):")[1].split(
        "    def save_memory(self):"
    )[0].join([]) if False else "",
]
# Use the complete custom memory methods as a single insertion.
current_methods = get_methods(current)
additions = []
for name in [
    "extract_wake_command", "listen_loop", "wake_response",
    "memory_context", "handle_memory_command", "open_desktop_app"
]:
    if name not in current_methods:
        additions.append(restored[name])

if "save_memories" not in current_methods:
    additions.append(
        custom_memory[custom_memory.index("    def save_memories(self):"):]
    )
if "poll_control_file" not in current_methods:
    additions.append(custom_control)

if additions:
    marker = "    def close(self):"
    if marker not in current:
        raise SystemExit("Repair stopped: couldn't find NovaOrb.close().")
    current = current.replace(marker, "\n".join(additions) + "\n" + marker, 1)

# Add required fields and imports without touching the visual methods.
if "\nimport sys\n" not in current:
    current = current.replace("import os\n", "import os\nimport sys\n", 1)

current = current.replace(
    "        self.busy = False\n",
    "        self.busy = False\n"
    "        self.audio_enabled = True\n"
    "        self.speech_lock = threading.Lock()\n",
    1
)
current = current.replace(
    "        self.load_memory()\n",
    "        self.memories = []\n"
    "        self.load_memory()\n",
    1
)
current = current.replace(
    '        threading.Thread(target=self.listen_loop, daemon=True).start()\n',
    '        self.root.after(150, self.poll_control_file)\n'
    '        threading.Thread(target=self.listen_loop, daemon=True).start()\n',
    1
)

# Avoid an accidental second insertion of memory initialization.
current = current.replace(
    "        self.memories = []\n        self.memories = []\n",
    "        self.memories = []\n"
)

ast.parse(current)
main_file.write_text(current, encoding="utf-8")

# Fix widget startup/control delivery while preserving all drawing code.
widget = widget_file.read_text(encoding="utf-8-sig")
old_control = '''    def send_control(command):
        process = assistant_process[0]
        if process is None or process.poll() is not None:
            launch_assistant()
            return
        control_file = Path(__file__).with_name("nova_ui_control.txt")
        control_file.write_text(command, encoding="utf-8")
'''
new_control = '''    def send_control(command):
        process = assistant_process[0]
        if process is None or process.poll() is not None:
            launch_assistant()
        control_file = Path(__file__).with_name("nova_ui_control.txt")
        control_file.write_text(command, encoding="utf-8")
'''
if old_control not in widget:
    raise SystemExit(
        "Backend updated, but widget control block didn't match. "
        "Widget file left unchanged; use the backup if needed."
    )
widget = widget.replace(old_control, new_control, 1)

connect_marker = (
    '    widget.audioToggleRequested.connect(lambda: send_control("audio_toggle"))\n'
)
if connect_marker not in widget:
    raise SystemExit("Backend updated, but widget startup marker wasn't found.")
widget = widget.replace(
    connect_marker,
    connect_marker + "\n    launch_assistant()\n",
    1
)

widget = widget.replace(
    "    def cleanup():\n"
    "        if sys.platform == \"win32\" and hotkey_registered:\n",
    "    def cleanup():\n"
    "        process = assistant_process[0]\n"
    "        if process is not None and process.poll() is None:\n"
    "            process.terminate()\n"
    "        if sys.platform == \"win32\" and hotkey_registered:\n",
    1
)

ast.parse(current)
widget_file.write_text(widget, encoding="utf-8")

print("Repair applied.")
