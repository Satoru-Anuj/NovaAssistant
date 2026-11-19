
from pathlib import Path
import shutil

widget_path = Path("nova_widget.py")
main_path = Path("main.py")

w = widget_path.read_text(encoding="utf-8")
m = main_path.read_text(encoding="utf-8")

old_connections = (
    "    widget.microphoneClicked.connect(launch_assistant)\n"
    "    widget.audioToggleRequested.connect(launch_assistant)\n"
)

new_connections = '''    def send_control(command):
        process = assistant_process[0]
        if process is None or process.poll() is not None:
            launch_assistant()
            return
        control_file = Path(__file__).with_name("nova_ui_control.txt")
        control_file.write_text(command, encoding="utf-8")

    widget.microphoneClicked.connect(lambda: send_control("mic_toggle"))
    widget.audioToggleRequested.connect(lambda: send_control("audio_toggle"))
'''

old_listener = "    def listen_loop(self):\n"

new_listener = '''    def poll_widget_control(self):
        if self.closing:
            return

        control_file = Path(__file__).with_name("nova_ui_control.txt")
        try:
            if control_file.exists():
                command = control_file.read_text(encoding="utf-8").strip()
                control_file.unlink(missing_ok=True)

                if command == "mic_toggle":
                    self.mic_enabled = not self.mic_enabled
                    self.listening = self.mic_enabled
                    if self.mic_enabled:
                        self.ensure_listener_running()
                    else:
                        self.set_status("idle")
                    print("Nova microphone:", "on" if self.mic_enabled else "off")

                elif command == "audio_toggle":
                    audio_file = Path(__file__).with_name("nova_audio_state.txt")
                    current = (
                        audio_file.read_text(encoding="utf-8").strip().lower()
                        if audio_file.exists() else "on"
                    )
                    state = "off" if current != "off" else "on"
                    audio_file.write_text(state, encoding="utf-8")
                    print("Nova voice output:", state)

        except OSError as error:
            print("Nova control-file error:", error)

        if not self.closing:
            self.root.after(250, self.poll_widget_control)

    def listen_loop(self):
'''

old_start = (
    "        self.listener_thread = threading.Thread(target=self.listen_loop, daemon=True)\n"
    "        self.listener_thread.start()\n"
)

if old_connections not in w:
    raise SystemExit("Widget connection block not found; no changes made.")
if old_listener not in m:
    raise SystemExit("Listener method not found; no changes made.")
if old_start not in m:
    raise SystemExit("Listener startup block not found; no changes made.")
if "def poll_widget_control(self):" in m:
    raise SystemExit("Control polling already exists; no changes made.")

shutil.copy2(widget_path, "nova_widget_patch_backup.py")
shutil.copy2(main_path, "main_patch_backup.py")

w = w.replace(old_connections, new_connections, 1)
m = m.replace(old_start, old_start + "        self.root.after(250, self.poll_widget_control)\n", 1)
m = m.replace(old_listener, new_listener, 1)

widget_path.write_text(w, encoding="utf-8")
main_path.write_text(m, encoding="utf-8")

print("Patch applied successfully.")
